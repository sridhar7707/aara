"""Forward-test measurement for the ETF overlay runner: fills.csv and the sleeve_value/account_equity columns."""
import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "etf_paper_rebalance.py"
_spec = importlib.util.spec_from_file_location("etf_paper_rebalance_fills", _SCRIPT)
rb = importlib.util.module_from_spec(_spec)
sys.modules["etf_paper_rebalance_fills"] = rb
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
    stock_db = tmp_path / "stock_trades.db"   # ADR-085 A1 D3: an empty position_state, so the check passes
    con = sqlite3.connect(stock_db)
    con.execute("CREATE TABLE position_state (symbol TEXT PRIMARY KEY, entry_price REAL, shares REAL)")
    con.commit()
    con.close()
    monkeypatch.setattr(rb, "STOCK_DB", stock_db)


class FakeClient:
    def __init__(self, positions=(), by_id=None, fail_ids=()):
        self.positions, self.by_id, self.fail_ids = list(positions), by_id or {}, set(fail_ids)
        self.account = SimpleNamespace(cash="100000", equity="100000", trading_blocked=False)
        self.lookups, self.submitted = [], []

    def get_account(self):
        return self.account

    def get_all_positions(self):
        return self.positions

    def get_orders(self, filter=None):
        return []

    def get_order_by_id(self, order_id):
        self.lookups.append(order_id)
        if order_id in self.fail_ids:
            raise ConnectionError("lookup down")
        return self.by_id[order_id]

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        return SimpleNamespace(id=f"id-{order_data.symbol}")


def _order(status="filled", qty="2.5", price="101.25"):
    return SimpleNamespace(status=status, filled_qty=qty, filled_avg_price=price)


def _log_submitted(*rows):
    for oid, sym, side in rows:
        rb._append(rb.ORDERS, {"run_utc": "t", "as_of": "2026-10-30", "symbol": sym, "side": side,
                               "notional": 500.0, "qty": None, "order_id": oid, "status": "submitted"})


def _fills():
    return pd.read_csv(rb.FILLS, dtype=str, keep_default_na=False)


def test_filled_order_is_recorded_in_fills_csv():
    _log_submitted(("o1", "XLK", "buy"))
    rb._record_fills(FakeClient(by_id={"o1": _order()}))
    row = _fills().iloc[0]
    assert (row["order_id"], row["symbol"], row["side"], row["status"]) == ("o1", "XLK", "buy", "filled")
    assert (row["filled_qty"], row["filled_avg_price"]) == ("2.5", "101.25")
    assert row["checked_utc"]


def test_enum_style_status_is_normalised():
    _log_submitted(("o1", "XLK", "buy"))
    rb._record_fills(FakeClient(by_id={"o1": _order(status="OrderStatus.FILLED")}))
    assert _fills()["status"].tolist() == ["filled"]


def test_rerun_does_not_duplicate_a_recorded_fill():
    _log_submitted(("o1", "XLK", "buy"))
    client = FakeClient(by_id={"o1": _order()})
    rb._record_fills(client)
    rb._record_fills(client)
    assert len(_fills()) == 1 and client.lookups == ["o1"]


def test_non_terminal_order_is_checked_again_until_final():
    _log_submitted(("o1", "XLK", "buy"))
    client = FakeClient(by_id={"o1": _order(status="accepted", qty=None, price=None)})
    rb._record_fills(client)
    client.by_id["o1"] = _order()
    rb._record_fills(client)
    rb._record_fills(client)
    assert _fills()["status"].tolist() == ["accepted", "filled"]


def test_failed_lookup_is_logged_and_the_rest_continue(capsys):
    _log_submitted(("o1", "XLK", "buy"), ("o2", "XLE", "sell"))
    rb._record_fills(FakeClient(by_id={"o2": _order()}, fail_ids={"o1"}))
    assert _fills()["order_id"].tolist() == ["o2"]
    assert "fill lookup failed for order o1" in capsys.readouterr().err


def test_failed_orders_and_missing_log_are_skipped():
    rb._record_fills(FakeClient())                     # no orders.csv at all
    rb._append(rb.ORDERS, {"run_utc": "t", "as_of": "d", "symbol": "XLK", "side": "buy", "notional": 1,
                           "qty": None, "order_id": "", "status": "error: boom"})
    client = FakeClient()
    rb._record_fills(client)
    assert client.lookups == [] and not rb.FILLS.exists()


def test_existing_fills_file_is_only_appended_to():
    _log_submitted(("o1", "XLK", "buy"), ("o2", "XLE", "buy"))
    client = FakeClient(by_id={"o1": _order(), "o2": _order()})
    rb._record_fills(FakeClient(by_id={"o1": _order()}, fail_ids={"o2"}))
    first = rb.FILLS.read_text(encoding="utf-8")
    rb._record_fills(client)
    assert rb.FILLS.read_text(encoding="utf-8").startswith(first)
    assert client.lookups == ["o2"]


def _closes():
    idx = pd.bdate_range("2024-01-01", periods=300)
    cols = {s: (np.linspace(50, 150, 300) if s == "XLK" else np.linspace(150, 50, 300)) for s in ep.ETF_UNIVERSE}
    return pd.DataFrame(cols, index=idx)


def _wire(monkeypatch, client, closes, today=None):
    monkeypatch.setattr(rb, "_closes", lambda: closes)
    monkeypatch.setattr(rb, "_account", lambda: rb._read_account(client))
    if today is not None:
        class _DT(rb.datetime):
            @classmethod
            def now(cls, tz=None):
                return rb.datetime.combine(today, rb.time(17, 0), tzinfo=tz)
        monkeypatch.setattr(rb, "datetime", _DT)


def test_execute_run_records_earlier_fills_first_and_carries_sleeve_value(monkeypatch):
    closes = _closes()
    _log_submitted(("o1", "XLK", "buy"))
    client = FakeClient(by_id={"o1": _order()})
    _wire(monkeypatch, client, closes, today=closes.index[-1].date())
    assert rb.main(["x", "--sleeve", "1000", "--execute"]) == 0
    assert _fills()["order_id"].tolist() == ["o1"]
    runs = pd.read_csv(rb.RUNS, dtype=str)
    assert list(runs["status"]) == ["started", "executed"]
    assert (runs["sleeve_value"] == "0.0").all() and (runs["account_equity"] == "100000.0").all()


def test_dry_run_records_sleeve_value_and_equity_and_does_no_fill_lookup(monkeypatch):
    closes = _closes()
    _log_submitted(("o1", "XLK", "buy"))
    client = FakeClient(by_id={"o1": _order()},
                        positions=[SimpleNamespace(symbol="AAPL", market_value="9999", qty="1")])
    _wire(monkeypatch, client, closes)
    assert rb.main(["x", "--sleeve", "1000"]) == 0
    runs = pd.read_csv(rb.RUNS, dtype=str)
    assert runs.loc[0, "sleeve_value"] == "0.0" and runs.loc[0, "account_equity"] == "100000.0"
    assert client.lookups == [] and not rb.FILLS.exists()


def test_sleeve_value_is_the_sum_of_overlay_market_values():
    row = rb._run_row("dry_run", "2026-11-06", 1000.0, 5.0, "dry_run", "", {}, [], 1234.567, 98765.4321)
    assert row["sleeve_value"] == 1234.57 and row["account_equity"] == 98765.43


def test_append_refuses_a_misaligned_header():
    rb._append(rb.RUNS, {"a": 1, "b": 2})
    with pytest.raises(RuntimeError, match="header"):
        rb._append(rb.RUNS, {"a": 1, "b": 2, "c": 3})
