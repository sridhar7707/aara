"""Measurement for the ETF overlay runner: runs_v2.csv rows on every account-reading invocation, and fills.csv times."""
import importlib.util
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "etf_paper_rebalance.py"
_spec = importlib.util.spec_from_file_location("etf_paper_rebalance_measure", _SCRIPT)
rb = importlib.util.module_from_spec(_spec)
sys.modules["etf_paper_rebalance_measure"] = rb
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
    stock_db = tmp_path / "stock_trades.db"
    con = sqlite3.connect(stock_db)
    con.execute("CREATE TABLE position_state (symbol TEXT PRIMARY KEY, entry_price REAL, shares REAL)")
    con.commit()
    con.close()
    monkeypatch.setattr(rb, "STOCK_DB", stock_db)


class FakeClient:
    def __init__(self, positions=(), by_id=None):
        self.positions, self.by_id = list(positions), by_id or {}
        self.account = SimpleNamespace(cash="100000", equity="100000", trading_blocked=False)
        self.submitted = []

    def get_account(self):
        return self.account

    def get_all_positions(self):
        return self.positions

    def get_orders(self, filter=None):
        return []

    def get_order_by_id(self, order_id):
        return self.by_id[order_id]

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        return SimpleNamespace(id=f"id-{order_data.symbol}")


def _pos(symbol, value, qty=1.0):
    return SimpleNamespace(symbol=symbol, market_value=str(value), qty=str(qty))


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


def _runs():
    return pd.read_csv(rb.RUNS, dtype=str, keep_default_na=False)


def _fills():
    return pd.read_csv(rb.FILLS, dtype=str, keep_default_na=False)


# --- sleeve_summary (pure) ---

def test_sleeve_summary_sums_overlay_market_values_and_lists_symbols():
    acct = SimpleNamespace(values={"XLK": 500.25, "XLE": 300.5}, held_symbols=["XLK", "XLE"], equity=98000.0,
                           cash=90000.0)
    assert rb.sleeve_summary(acct) == {"sleeve_value": 800.75, "account_equity": 98000.0, "cash": 90000.0,
                                       "held_symbols": ["XLE", "XLK"]}


def test_sleeve_summary_is_zero_only_when_nothing_is_held():
    acct = SimpleNamespace(values={}, held_symbols=[], equity=1.0, cash=1.0)
    assert rb.sleeve_summary(acct)["sleeve_value"] == 0.0 and rb.sleeve_summary(acct)["held_symbols"] == []


def test_sleeve_summary_from_a_read_account_ignores_non_overlay_positions():
    state = rb._read_account(FakeClient(positions=[_pos("XLK", 500), _pos("AAPL", 9999)]))
    assert rb.sleeve_summary(state)["sleeve_value"] == 500.0


# --- (a) refused runs are recorded with the real sleeve value ---

@pytest.mark.parametrize("execute", [False, True])
def test_refused_run_with_overlay_held_writes_a_refused_row_with_sleeve_value(monkeypatch, execute):
    closes = _closes()
    client = FakeClient(positions=[_pos("XLK", 500.5), _pos("XLE", 300.0), _pos("AAPL", 9999)])
    _wire(monkeypatch, client, closes, today=closes.index[-1].date() if execute else None)
    with pytest.raises(SystemExit) as exc:
        rb.main(["x", "--sleeve", "1000"] + (["--execute"] if execute else []))
    assert exc.value.code not in (None, 0)
    row = _runs().iloc[0]
    assert len(_runs()) == 1
    assert (row["status"], row["mode"]) == ("refused", "execute" if execute else "dry_run")
    assert row["sleeve_value"] == "800.5" and row["held_symbols"] == "XLE;XLK"
    assert row["account_equity"] == "100000.0" and row["cash"] == "100000.0"
    assert "already held" in row["refusal_reason"] and row["orders"] == ""
    assert client.submitted == []


def test_refused_execute_does_not_count_as_this_months_run(monkeypatch):
    closes = _closes()
    held = FakeClient(positions=[_pos("XLK", 500.0)])
    _wire(monkeypatch, held, closes, today=closes.index[-1].date())
    with pytest.raises(SystemExit):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    assert not rb._already_executed(str(closes.index[-1].date())[:7])
    clean = FakeClient()
    _wire(monkeypatch, clean, closes, today=closes.index[-1].date())
    assert rb.main(["x", "--sleeve", "1000", "--execute"]) == 0
    assert list(_runs()["status"]) == ["refused", "started", "executed"]


def test_execute_refused_before_the_close_is_logged_with_sleeve_value(monkeypatch):
    closes = _closes()
    client = FakeClient(positions=[])
    _wire(monkeypatch, client, closes, today=closes.index[-1].date())

    class _Early(rb.datetime):
        @classmethod
        def now(cls, tz=None):
            return rb.datetime.combine(closes.index[-1].date(), rb.time(10, 0), tzinfo=tz)
    monkeypatch.setattr(rb, "datetime", _Early)
    with pytest.raises(SystemExit, match="before 16:30"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    row = _runs().iloc[0]
    assert row["status"] == "refused" and "before 16:30" in row["refusal_reason"] and row["sleeve_value"] == "0.0"


def test_refusal_still_exits_when_the_row_cannot_be_written(monkeypatch, capsys):
    closes = _closes()
    _wire(monkeypatch, FakeClient(positions=[_pos("XLK", 500.0)]), closes)
    monkeypatch.setattr(rb, "_append", lambda path, row: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(SystemExit, match="already held"):
        rb.main(["x", "--sleeve", "1000"])
    assert "could not write" in capsys.readouterr().err


# --- (b) unreadable account ---

@pytest.mark.parametrize("execute", [False, True])
def test_unreadable_account_writes_unreadable_row_without_a_zero(monkeypatch, execute):
    closes = _closes()
    monkeypatch.setattr(rb, "_closes", lambda: closes)

    def unreadable():
        raise SystemExit("refusing: cannot read the paper account (ConnectionError: down).")
    monkeypatch.setattr(rb, "_account", unreadable)
    if execute:
        class _DT(rb.datetime):
            @classmethod
            def now(cls, tz=None):
                return rb.datetime.combine(closes.index[-1].date(), rb.time(17, 0), tzinfo=tz)
        monkeypatch.setattr(rb, "datetime", _DT)
    with pytest.raises(SystemExit) as exc:
        rb.main(["x", "--sleeve", "1000"] + (["--execute"] if execute else []))
    assert exc.value.code not in (None, 0)
    row = _runs().iloc[0]
    assert row["status"] == "unreadable"
    assert row["sleeve_value"] == "" and row["account_equity"] == "" and row["cash"] == ""
    assert "cannot read" in row["refusal_reason"]


# --- (c) dry run ---

def test_dry_run_writes_dry_run_row_with_sleeve_value(monkeypatch):
    closes = _closes()
    client = FakeClient(positions=[_pos("AAPL", 9999)])
    _wire(monkeypatch, client, closes)
    assert rb.main(["x", "--sleeve", "1000"]) == 0
    row = _runs().iloc[0]
    assert (row["status"], row["mode"], row["refusal_reason"]) == ("dry_run", "dry_run", "")
    assert row["sleeve_value"] == "0.0" and row["held_symbols"] == "" and row["orders"] == "buy:XLK"
    assert row["account_equity"] == "100000.0" and row["cash"] == "100000.0" and row["sleeve"] == "1000.0"
    assert row["run_utc"] and row["as_of"] == str(closes.index[-1].date())


def test_dry_run_never_fails_on_the_row_write(monkeypatch, capsys):
    closes = _closes()
    _wire(monkeypatch, FakeClient(), closes)
    monkeypatch.setattr(rb, "_append", lambda path, row: (_ for _ in ()).throw(OSError("disk full")))
    assert rb.main(["x", "--sleeve", "1000"]) == 0
    assert "could not write" in capsys.readouterr().err


def test_execute_rows_carry_held_symbols_and_sleeve_value(monkeypatch):
    closes = _closes()
    _wire(monkeypatch, FakeClient(), closes, today=closes.index[-1].date())
    assert rb.main(["x", "--sleeve", "1000", "--execute"]) == 0
    assert list(_runs()["status"]) == ["started", "executed"]
    assert set(_runs()["refusal_reason"]) == {""}


# --- existing runs_v2.csv / fills.csv with the older header ---

def test_older_runs_header_is_padded_not_refused():
    old = "run_utc,mode,as_of,sleeve,cash,status,error,held,orders,sleeve_value,account_equity\n"
    rb.RUNS.write_text(old + "t,dry_run,2026-10-30,1000.0,9.0,dry_run,,XLK,buy:XLK,0.0,100.0\n", encoding="utf-8")
    rb._append_log(rb.RUNS, rb._run_row("dry_run", "2026-11-06", 1000.0, 5.0, "refused", "", {}, [], 800.0, 99.0,
                                        refusal_reason="r", held_symbols=["XLK"]))
    runs = _runs()
    assert list(runs["status"]) == ["dry_run", "refused"]
    assert runs.loc[0, "refusal_reason"] == "" and runs.loc[1, "held_symbols"] == "XLK"
    assert runs.loc[0, "sleeve_value"] == "0.0"


def test_unrelated_runs_header_is_still_refused():
    rb.RUNS.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="header"):
        rb._append_log(rb.RUNS, rb._run_row("dry_run", "d", 1.0, 1.0, "dry_run", "", {}, [], 0.0, 1.0))


# --- (d) fills.csv times ---

def _log_submitted(oid, run_utc):
    rb._append(rb.ORDERS, {"run_utc": run_utc, "as_of": "2026-10-30", "symbol": "XLK", "side": "buy",
                           "notional": 500.0, "qty": None, "order_id": oid, "status": "submitted"})


def test_fill_row_carries_submitted_at_and_filled_at():
    _log_submitted("o1", "2026-10-30T21:05:00+00:00")
    filled_at = datetime(2026, 10, 30, 21, 5, 4, tzinfo=timezone.utc)
    order = SimpleNamespace(status="filled", filled_qty="2.5", filled_avg_price="101.25", filled_at=filled_at)
    rb._record_fills(FakeClient(by_id={"o1": order}))
    row = _fills().iloc[0]
    assert row["submitted_at"] == "2026-10-30T21:05:00+00:00"
    assert row["filled_at"] == filled_at.isoformat()
    assert (row["filled_qty"], row["filled_avg_price"], row["status"]) == ("2.5", "101.25", "filled")


def test_unfilled_order_has_empty_filled_at_and_is_rechecked_append_only():
    _log_submitted("o1", "2026-10-30T21:05:00+00:00")
    client = FakeClient(by_id={"o1": SimpleNamespace(status="accepted", filled_qty=None, filled_avg_price=None,
                                                     filled_at=None)})
    rb._record_fills(client)
    assert _fills().loc[0, "filled_at"] == "" and _fills().loc[0, "submitted_at"] == "2026-10-30T21:05:00+00:00"
    client.by_id["o1"] = SimpleNamespace(status="filled", filled_qty="1", filled_avg_price="10",
                                         filled_at="2026-10-30T21:05:09Z")
    rb._record_fills(client)
    rb._record_fills(client)
    assert _fills()["status"].tolist() == ["accepted", "filled"]
    assert _fills().loc[1, "filled_at"] == "2026-10-30T21:05:09Z"


def test_older_fills_header_is_padded():
    rb.FILLS.write_text("order_id,symbol,side,filled_qty,filled_avg_price,status,checked_utc\n"
                        "o0,XLE,buy,1,10,accepted,t\n", encoding="utf-8")
    _log_submitted("o0", "2026-10-30T21:05:00+00:00")
    rb._record_fills(FakeClient(by_id={"o0": SimpleNamespace(status="filled", filled_qty="1", filled_avg_price="10",
                                                             filled_at=None)}))
    fills = _fills()
    assert fills["status"].tolist() == ["accepted", "filled"] and fills.loc[0, "submitted_at"] == ""


# --- ADR-085 A1 D3 ordering: the stock-bot check runs before the price fetch and the account read ---

def test_d3_check_runs_before_price_fetch_and_account_read_and_writes_no_run_row(monkeypatch):
    called = []
    monkeypatch.setattr(rb, "_closes", lambda: called.append("_closes") or pytest.fail("_closes called before D3"))
    monkeypatch.setattr(rb, "_account", lambda: called.append("_account") or pytest.fail("_account called before D3"))

    def d3_refuses():
        called.append("d3")
        raise SystemExit("refusing to execute: the stock bot has position_state rows for overlay names ['XLK'].")
    monkeypatch.setattr(rb, "_refuse_if_stock_bot_holds_overlay", d3_refuses)
    monkeypatch.setattr(rb, "SHARED_ACCOUNT_EXECUTE_APPROVED", True)
    with pytest.raises(SystemExit, match="position_state"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    assert called == ["d3"]
    assert not rb.RUNS.exists()


# --- credential redaction in refusal_reason and stderr warnings ---

_KEY = "-".join(["dummy", "key", "value", "456"])
_SECRET = "-".join(["dummy", "credential", "value", "123"])   # fake; built so it is not a literal


def _set_creds(monkeypatch):
    import config
    monkeypatch.setattr(config, "ALPACA_KEY", _KEY)
    monkeypatch.setattr(config, "ALPACA_SECRET", _SECRET)


def test_redact_replaces_key_and_secret_and_skips_empty_values(monkeypatch):
    import config
    _set_creds(monkeypatch)
    assert rb.redact(f"bad {_SECRET} and {_KEY} end") == "bad [redacted] and [redacted] end"
    assert rb.redact("nothing here") == "nothing here"
    monkeypatch.setattr(config, "ALPACA_KEY", "")
    monkeypatch.setattr(config, "ALPACA_SECRET", "")
    assert rb.redact("unchanged text") == "unchanged text"   # empty values never replace the empty string


def test_unreadable_account_message_with_secret_is_redacted_in_row_and_stderr(monkeypatch, capsys):
    _set_creds(monkeypatch)
    closes = _closes()
    monkeypatch.setattr(rb, "_closes", lambda: closes)

    def boom(client):
        raise ConnectionError(f"401 for secret {_SECRET}")
    monkeypatch.setattr(rb, "_read_account", boom)
    import alpaca.trading.client as tc
    monkeypatch.setattr(tc, "TradingClient", lambda *a, **k: object())
    with pytest.raises(SystemExit):
        rb.main(["x", "--sleeve", "1000"])
    row = _runs().iloc[0]
    assert row["status"] == "unreadable" and "[redacted]" in row["refusal_reason"]
    assert _SECRET not in row["refusal_reason"] and _SECRET not in rb.RUNS.read_text(encoding="utf-8")
    assert _SECRET not in capsys.readouterr().err


def test_refusal_reason_from_a_systemexit_with_secret_is_redacted(monkeypatch):
    _set_creds(monkeypatch)
    closes = _closes()
    monkeypatch.setattr(rb, "_closes", lambda: closes)

    def unreadable():
        raise SystemExit(f"refusing: cannot read the paper account (HTTPError: bad {_SECRET}).")
    monkeypatch.setattr(rb, "_account", unreadable)
    with pytest.raises(SystemExit):
        rb.main(["x", "--sleeve", "1000"])
    assert _SECRET not in rb.RUNS.read_text(encoding="utf-8")
    assert "[redacted]" in _runs().loc[0, "refusal_reason"]


def test_row_write_warning_with_secret_is_redacted_on_stderr(monkeypatch, capsys):
    _set_creds(monkeypatch)
    _wire(monkeypatch, FakeClient(), _closes())
    monkeypatch.setattr(rb, "_append", lambda path, row: (_ for _ in ()).throw(OSError(f"locked {_SECRET}")))
    assert rb.main(["x", "--sleeve", "1000"]) == 0
    err = capsys.readouterr().err
    assert "could not write" in err and "[redacted]" in err and _SECRET not in err


def test_fill_lookup_and_post_run_warnings_with_secret_are_redacted_on_stderr(monkeypatch, capsys):
    _set_creds(monkeypatch)
    _log_submitted("o1", "2026-10-30T21:05:00+00:00")

    class Boom(FakeClient):
        def get_order_by_id(self, order_id):
            raise RuntimeError(f"nope {_SECRET}")

        def get_all_positions(self):
            raise RuntimeError(f"nope {_SECRET}")
    rb._record_fills(Boom())
    rb._verify_after(Boom(), 1000.0)
    err = capsys.readouterr().err
    assert "fill lookup failed" in err and "post-run position read failed" in err
    assert "[redacted]" in err and _SECRET not in err
