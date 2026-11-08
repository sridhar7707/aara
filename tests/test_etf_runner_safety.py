"""Risk-officer conditions C2-C7 for the ETF overlay runner (scripts/etf_paper_rebalance.py)."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "etf_paper_rebalance.py"
_spec = importlib.util.spec_from_file_location("etf_paper_rebalance", _SCRIPT)
rb = importlib.util.module_from_spec(_spec)
sys.modules["etf_paper_rebalance"] = rb
_spec.loader.exec_module(rb)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "LOG_DIR", tmp_path)
    monkeypatch.setattr(rb, "RUNS", tmp_path / "runs_v2.csv")
    monkeypatch.setattr(rb, "ORDERS", tmp_path / "orders.csv")
    monkeypatch.setattr(rb, "FILLS", tmp_path / "fills.csv")
    monkeypatch.setattr(rb, "HALT_FILE", tmp_path / "HALT_TRADING")
    monkeypatch.setattr(rb, "ALPACA_BASE_URL", ep.PAPER_URL)
    monkeypatch.setattr(rb, "SHARED_ACCOUNT_EXECUTE_APPROVED", True)


class FakeClient:
    def __init__(self, positions=(), orders=(), fail_symbols=(), account=None):
        self.positions, self.orders, self.fail_symbols = list(positions), list(orders), set(fail_symbols)
        self.account = account or SimpleNamespace(cash="100000", equity="100000", trading_blocked=False)
        self.submitted, self.order_filters = [], []

    def get_account(self):
        return self.account

    def get_all_positions(self):
        return self.positions

    def get_orders(self, filter=None):
        self.order_filters.append(filter)
        return self.orders

    def submit_order(self, order_data):
        if order_data.symbol in self.fail_symbols:
            raise RuntimeError("rejected")
        self.submitted.append(order_data)
        return SimpleNamespace(id=f"id-{order_data.symbol}")


def _pos(symbol, value, qty=1.0):
    return SimpleNamespace(symbol=symbol, market_value=str(value), qty=str(qty))


def _closes(up=("XLK",)):
    idx = pd.bdate_range("2024-01-01", periods=300)
    cols = {s: (np.linspace(50, 150, 300) if s in up else np.linspace(150, 50, 300)) for s in ep.ETF_UNIVERSE}
    return pd.DataFrame(cols, index=idx)


def _wire(monkeypatch, client, closes=None, today=None):
    closes = _closes() if closes is None else closes
    monkeypatch.setattr(rb, "_closes", lambda: closes)
    monkeypatch.setattr(rb, "_account", lambda: rb._read_account(client))
    if today is not None:  # make "now" 17:00 New York on the last bar's date, after the close
        class _DT(rb.datetime):
            @classmethod
            def now(cls, tz=None):
                return rb.datetime.combine(today, rb.time(17, 0), tzinfo=tz)
        monkeypatch.setattr(rb, "datetime", _DT)


def _last_date(closes=None):
    return (_closes() if closes is None else closes).index[-1].date()


def _runs():
    return pd.read_csv(rb.RUNS, dtype=str)


# --- C2 ---

def test_every_order_carries_the_deterministic_client_order_id():
    client = FakeClient()
    plan = [{"symbol": "XLK", "side": "buy", "notional": 500.0, "qty": None},
            {"symbol": "XLE", "side": "sell", "notional": 100.0, "qty": 2.0}]
    status, error = rb._execute_plan(client, plan, "2026-11", "2026-11-06")
    assert (status, error) == ("executed", "")
    assert [r.client_order_id for r in client.submitted] == ["etf-2026-11-XLK-buy", "etf-2026-11-XLE-sell"]
    assert list(pd.read_csv(rb.ORDERS, dtype=str)["order_id"]) == ["id-XLK", "id-XLE"]


def test_open_overlay_orders_are_read_with_open_status_and_refused():
    from alpaca.trading.enums import QueryOrderStatus
    client = FakeClient(orders=[SimpleNamespace(symbol="XLK"), SimpleNamespace(symbol="AAPL")])
    state = rb._read_account(client)
    assert client.order_filters[0].status == QueryOrderStatus.OPEN
    assert state.open_order_symbols == ["XLK"]          # the AAPL order is not the overlay's
    with pytest.raises(SystemExit, match="open orders"):
        rb._refuse_if_unsafe(state, 1_000.0)


def test_started_row_is_written_before_first_submit_and_final_row_after(monkeypatch):
    closes = _closes()
    client = FakeClient()
    seen = {}
    real = client.submit_order

    def spy(order_data):
        seen.setdefault("rows_at_first_submit", list(_runs()["status"]))
        return real(order_data)
    client.submit_order = spy
    _wire(monkeypatch, client, closes, today=_last_date(closes))
    assert rb.main(["x", "--sleeve", "1000", "--execute"]) == 0
    assert seen["rows_at_first_submit"] == ["started"]
    assert list(_runs()["status"]) == ["started", "executed"]


def test_order_log_failure_after_submit_prints_order_id_and_reraises(monkeypatch, capsys):
    client = FakeClient()
    real_append = rb._append

    def boom(path, row):
        if path == rb.ORDERS:
            raise OSError("disk full")
        return real_append(path, row)
    monkeypatch.setattr(rb, "_append", boom)
    plan = [{"symbol": "XLK", "side": "buy", "notional": 500.0, "qty": None}]
    with pytest.raises(OSError, match="disk full"):
        rb._execute_plan(client, plan, "2026-11", "2026-11-06")
    assert "order_id=id-XLK" in capsys.readouterr().err
    assert len(client.submitted) == 1


def test_failed_submit_is_recorded_with_empty_id_and_stops():
    client = FakeClient(fail_symbols={"XLK"})
    plan = [{"symbol": "XLK", "side": "buy", "notional": 500.0, "qty": None},
            {"symbol": "QQQ", "side": "buy", "notional": 500.0, "qty": None}]
    status, error = rb._execute_plan(client, plan, "2026-11", "2026-11-06")
    assert status == "failed" and "XLK" in error
    assert client.submitted == []
    assert pd.read_csv(rb.ORDERS, dtype=str, keep_default_na=False)["order_id"].tolist() == [""]


@pytest.mark.parametrize("status", ["started", "executed", "failed"])
def test_already_executed_counts_any_execute_row_for_the_month(status):
    rb._append(rb.RUNS, {"run_utc": "t", "mode": "execute", "as_of": "2026-11-06", "sleeve": 1, "cash": 1,
                         "status": status, "error": "", "held": "", "orders": ""})
    assert rb._already_executed("2026-11")
    assert not rb._already_executed("2026-12")


def test_dry_run_rows_do_not_count_as_executed():
    rb._append(rb.RUNS, {"run_utc": "t", "mode": "dry_run", "as_of": "2026-11-06", "sleeve": 1, "cash": 1,
                         "status": "dry_run", "error": "", "held": "", "orders": ""})
    assert not rb._already_executed("2026-11")


# --- C3 ---

def test_runs_file_name_in_the_script_is_v2():
    assert 'RUNS = LOG_DIR / "runs_v2.csv"' in _SCRIPT.read_text(encoding="utf-8")


def test_already_executed_reads_a_current_schema_file():
    cols = "run_utc,mode,as_of,sleeve,cash,status,error,held,orders\n"
    rb.RUNS.write_text(cols + "2026-11-06T22:00:00+00:00,execute,2026-11-06,1000.0,9000.0,executed,,XLK,buy:XLK\n",
                       encoding="utf-8")
    assert rb._already_executed("2026-11")


def test_legacy_runs_csv_is_ignored(tmp_path):
    (tmp_path / "runs.csv").write_text("run_utc,mode,as_of,equity,held,orders\n"
                                       "t,execute,2026-11-06,10000.0,XLK,buy:XLK\nbad,row,with,extra,cols,here,x\n",
                                       encoding="utf-8")
    assert not rb._already_executed("2026-11")


def test_runs_file_missing_required_columns_fails_closed():
    rb.RUNS.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing columns"):
        rb._already_executed("2026-11")


# --- C5 / C6 ---

def test_overlay_holdings_are_refused_before_planning():
    client = FakeClient(positions=[_pos("XLK", 500.0), _pos("AAPL", 100.0)])
    state = rb._read_account(client)
    assert state.held_symbols == ["XLK"] and "AAPL" not in state.values
    with pytest.raises(SystemExit, match="already held"):
        rb._refuse_if_unsafe(state, 1_000.0)


def test_trading_blocked_account_is_refused():
    client = FakeClient(account=SimpleNamespace(cash="1", equity="1", trading_blocked=True))
    with pytest.raises(SystemExit, match="trading_blocked"):
        rb._refuse_if_unsafe(rb._read_account(client), 1_000.0)


def test_post_run_warning_when_overlay_value_exceeds_sleeve(capsys):
    rb._verify_after(FakeClient(positions=[_pos("XLK", 2_000.0)]), 1_000.0)
    assert "WARNING" in capsys.readouterr().err
    rb._verify_after(FakeClient(positions=[_pos("XLK", 900.0)]), 1_000.0)
    assert capsys.readouterr().err == ""


def test_post_run_read_failure_warns_instead_of_raising(capsys):
    client = FakeClient()
    client.get_all_positions = lambda: (_ for _ in ()).throw(RuntimeError("down"))
    rb._verify_after(client, 1_000.0)
    assert "not verified" in capsys.readouterr().err


def test_halt_file_refuses_both_modes():
    rb.HALT_FILE.write_text("", encoding="utf-8")
    for extra in ([], ["--execute"]):
        with pytest.raises(SystemExit, match="HALT_TRADING"):
            rb.main(["x", "--sleeve", "1000", *extra])


# --- C7 and the approval flag ---

def test_dry_run_reads_the_account_and_plans_with_real_cash(monkeypatch, capsys):
    client = FakeClient(account=SimpleNamespace(cash="50000", equity="100000", trading_blocked=False))
    _wire(monkeypatch, client)
    assert rb.main(["x", "--sleeve", "2000"]) == 0
    out = capsys.readouterr().out
    assert "cash $50,000.00" in out and "buy  XLK" in out
    assert client.order_filters and client.submitted == []
    assert list(_runs()["mode"]) == ["dry_run"]


def test_dry_run_does_not_plan_when_the_account_read_fails(monkeypatch):
    client = FakeClient()
    client.get_account = lambda: (_ for _ in ()).throw(ConnectionError("no network"))
    _wire(monkeypatch, client)
    with pytest.raises(ConnectionError):
        rb.main(["x", "--sleeve", "1000"])
    assert not rb.RUNS.exists()


def test_account_read_failure_becomes_a_refusal(monkeypatch):
    import alpaca.trading.client as tc
    import config

    class Boom:
        def __init__(self, *a, **k):
            pass

        def get_account(self):
            raise ConnectionError("no network")
    monkeypatch.setattr(tc, "TradingClient", Boom)
    monkeypatch.setattr(config, "ALPACA_KEY", "k", raising=False)
    monkeypatch.setattr(config, "ALPACA_SECRET", "s", raising=False)
    with pytest.raises(SystemExit, match="cannot read"):
        rb._account()


def test_dry_run_refuses_an_oversized_sleeve(monkeypatch):
    _wire(monkeypatch, FakeClient())
    with pytest.raises(SystemExit, match="exceeds"):
        rb.main(["x", "--sleeve", "50000"])     # 50% of a 100k account


def test_execute_is_refused_until_the_owner_accepts_adr085(monkeypatch):
    monkeypatch.setattr(rb, "SHARED_ACCOUNT_EXECUTE_APPROVED", False)
    client = FakeClient()
    _wire(monkeypatch, client)
    with pytest.raises(SystemExit, match="ADR-085 open item 1"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    assert client.submitted == [] and not rb.RUNS.exists()


def test_shipped_approval_flag_is_false():
    assert "\nSHARED_ACCOUNT_EXECUTE_APPROVED = False" in _SCRIPT.read_text(encoding="utf-8")


def test_execute_second_run_in_the_same_month_is_refused(monkeypatch):
    closes = _closes()
    client = FakeClient()
    _wire(monkeypatch, client, closes, today=_last_date(closes))
    assert rb.main(["x", "--sleeve", "1000", "--execute"]) == 0
    n = len(client.submitted)
    with pytest.raises(SystemExit, match="already executed"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    assert len(client.submitted) == n


def test_reserve_pct_comes_from_config():
    import config
    assert rb.MIN_CASH_RESERVE_PCT == config.MIN_CASH_RESERVE_PCT
