"""ADR-085 amendment A1: overlay names the stock bot holds keep their EXIT rules and never get entries."""
import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from loguru import logger

import bot.main as m
from bot import _main_cycle
from bot._main_cycle import EntryContext, _handle_entry, position_placeholder
from bot._main_db import init_db as _init_db_core
from bot._main_overlay import (
    exit_position_for, exit_view, net_trade_shares, stock_held_overlay_symbols,
)
from bot._main_positions import _handle_exits
from bot.execution import etf_paper as ep
from bot.risk.risk_manager import RiskManager
from tests.test_intra_cycle_live_loop import _LSTM, _XGB, _bars, _Client, _hermetic, _Regime

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "etf_paper_rebalance.py"
_spec = importlib.util.spec_from_file_location("etf_paper_rebalance_overlay_a1", _SCRIPT)
rb = importlib.util.module_from_spec(_spec)
sys.modules["etf_paper_rebalance_overlay_a1"] = rb
_spec.loader.exec_module(rb)

SYM = "XLK"
NOW = "2026-11-05T15:00:00+00:00"


def _seed(con, entry=100.0, shares=5.0, buys=(5.0,), sells=()):
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, atr_at_entry, opened_at, shares) "
                "VALUES (?,?,?,?,?,?)", (SYM, entry, entry, 3.0, NOW, shares))
    for q in buys:
        con.execute("INSERT INTO trades (timestamp, symbol, action, shares, price, notional) VALUES (?,?,?,?,?,?)",
                    (NOW, SYM, "BUY", q, entry, q * entry))
    for q in sells:
        con.execute("INSERT INTO trades (timestamp, symbol, action, shares, price, notional) VALUES (?,?,?,?,?,?)",
                    (NOW, SYM, "SELL_STOP", q, entry, q * entry))
    con.commit()


@pytest.fixture
def con():
    c = _init_db_core(":memory:")
    yield c
    c.close()


def _broker(qty=15.0, avg=95.0):
    return position_placeholder(SYM, qty=qty, market_value=qty * 91.0, avg_entry_price=avg)


class _SellClient:
    """Records sells and fills them completely; any buy is a test failure."""
    def __init__(self):
        self.sells, self.buy = [], Mock(name="buy")

    def sell(self, symbol, qty, limit_price=None):
        self.sells.append((symbol, qty))
        return {"order_id": "o1"}

    def sell_market(self, symbol, qty):
        self.sells.append((symbol, qty))
        return {"order_id": "o2"}

    def wait_for_fill(self, order_id, timeout_secs=12):
        return self.sells[-1][1]


def _risk():
    return RiskManager(settings_fn=lambda key, default: default)


# --- (i) the clamp --------------------------------------------------------------------------

@pytest.mark.parametrize("broker_qty,state_shares,buys,sells,expected", [
    (15.0, 5.0, (5.0,), (), 5.0),        # broker blended with overlay shares: the stock lot only
    (15.0, 6.0, (4.0,), (), 4.0),        # trades say less than state: trades win
    (15.0, 6.0, (10.0,), (3.0,), 6.0),   # net trades 7, state 6: state wins
    (3.0, 6.0, (6.0,), (), 3.0),         # broker holds less than the lot: broker wins
])
def test_clamped_quantity_never_exceeds_state_or_net_trades(con, broker_qty, state_shares, buys, sells, expected):
    _seed(con, shares=state_shares, buys=buys, sells=sells)
    net = net_trade_shares(con, SYM)
    pos = exit_position_for(SYM, _broker(qty=broker_qty), (100.0, state_shares), net, 91.0)
    assert pos.qty == expected
    assert pos.qty <= state_shares and pos.qty <= net and pos.qty <= broker_qty


def test_sell_sent_by_exit_rules_is_the_clamped_quantity(con, monkeypatch):
    _seed(con, shares=5.0, buys=(5.0,))
    client = _SellClient()
    view = exit_view(con, SYM, {SYM: _broker(qty=15.0)}, 91.0)
    _handle_exits(con, client, _risk(), SYM, view, set(), 91.0, 3.0, "TRENDING_UP", 100_000.0, 0, True, set())
    assert client.sells and all(q <= 5.0 for _, q in client.sells)
    assert con.execute("SELECT shares FROM trades WHERE symbol=? AND action='SELL_STOP'", (SYM,)).fetchone()[0] == 5.0


def test_net_trade_shares_nets_every_non_buy_action(con):
    _seed(con, buys=(10.0,), sells=(3.0,))
    con.execute("INSERT INTO trades (timestamp, symbol, action, shares, price, notional) VALUES (?,?,?,?,?,?)",
                (NOW, SYM, "SELL_RECONCILE", 2.0, 100.0, 200.0))
    assert net_trade_shares(con, SYM) == 5.0


# --- (ii) shares 0 / NULL -> nothing sent, no entry ---------------------------------------------

@pytest.mark.parametrize("state_row", [(100.0, 0.0), (100.0, None), (None, 5.0), (0.0, 5.0), None])
def test_unusable_state_drops_the_lot_with_a_warning(state_row):
    seen = []
    sink = logger.add(lambda msg: seen.append(msg.record["message"]), level="WARNING")
    try:
        assert exit_position_for(SYM, _broker(), state_row, 5.0, 91.0) is None
    finally:
        logger.remove(sink)
    assert any("NOT managed this cycle" in s for s in seen)


@pytest.mark.parametrize("net,price", [(0.0, 91.0), (-2.0, 91.0), (float("nan"), 91.0), (5.0, float("nan")), (5.0, 0.0)])
def test_dust_negative_or_nan_inputs_drop_the_lot(net, price):
    assert exit_position_for(SYM, _broker(), (100.0, 5.0), net, price) is None


@pytest.mark.parametrize("shares", [0.0, None])
def test_dropped_lot_is_absent_from_the_view_so_no_sell_is_sent(con, shares):
    _seed(con, shares=shares)
    client = _SellClient()
    view = exit_view(con, SYM, {SYM: _broker(qty=15.0)}, 50.0)
    assert SYM not in view
    assert _handle_exits(con, client, _risk(), SYM, view, set(), 50.0, 3.0, "TRENDING_UP",
                         100_000.0, 0, True, set()) is False
    assert client.sells == []


# --- (iii) blended basis ---------------------------------------------------------------------

def test_stop_fires_on_the_stock_lots_own_basis_not_the_blended_average(con):
    _seed(con, entry=100.0, shares=5.0, buys=(5.0,))
    broker = _broker(qty=15.0, avg=95.0)          # 5 @ 100 (stock) + 10 @ 90 (overlay)
    pos = exit_view(con, SYM, {SYM: broker}, 91.0)[SYM]
    assert pos.avg_entry_price == 100.0
    assert pos.unrealized_plpc == pytest.approx(-0.09)
    risk = _risk()
    assert risk.check_stop_loss(SYM, 91.0, pos.avg_entry_price, atr=3.0, pnl_pct=pos.unrealized_plpc) is True
    assert risk.check_stop_loss(SYM, 91.0, 95.0, atr=3.0) is False    # the blended basis would not stop
    client = _SellClient()
    assert _handle_exits(con, client, risk, SYM, {SYM: pos}, set(), 91.0, 3.0, "TRENDING_UP",
                         100_000.0, 0, True, set()) is True
    assert client.sells == [(SYM, 5.0)]
    assert con.execute("SELECT COUNT(*) FROM trades WHERE action='SELL_STOP'").fetchone()[0] == 1


def test_exit_view_does_not_mutate_the_broker_positions(con):
    _seed(con)
    broker = _broker(qty=15.0, avg=95.0)
    positions = {SYM: broker, "AAPL": position_placeholder("AAPL", 1, 100.0, 100.0)}
    view = exit_view(con, SYM, positions, 91.0)
    assert positions[SYM] is broker and broker.qty == 15.0 and broker.avg_entry_price == 95.0
    assert view[SYM] is not broker and view["AAPL"] is positions["AAPL"]


def test_stock_held_overlay_symbols_needs_state_row_and_broker_position(con):
    _seed(con)
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('AAPL',1,1,1)")
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('GLD',1,1,1)")
    con.commit()
    held = {SYM: _broker(), "AAPL": _broker(), "QQQ": _broker()}   # GLD: state row but no broker position
    assert stock_held_overlay_symbols(con, held) == [SYM]          # QQQ: broker position but no state row


# --- (iv)(v)(vi) through the real run() cycle -----------------------------------------------------

class _OverlayClient(_Client):
    def __init__(self, xlk_close=91.0, qty=15.0, avg=95.0):
        super().__init__()
        self.sells = []
        self._xlk_close, self._pos = xlk_close, {SYM: position_placeholder(SYM, qty, qty * xlk_close, avg)}

    def get_positions(self):
        return self._pos

    def get_bars(self, symbol, timeframe="5Min", limit=100):
        if symbol != SYM:
            return super().get_bars(symbol, timeframe, limit)
        df = _bars(300)
        df[["open", "high", "low", "close"]] = self._xlk_close
        return df

    def sell(self, symbol, qty, limit_price=None):
        self.sells.append((symbol, qty))
        return {"order_id": f"s-{len(self.sells)}"}

    def sell_market(self, symbol, qty):
        return self.sell(symbol, qty)

    def wait_for_fill(self, order_id, timeout_secs=15):
        return self.sells[-1][1] if order_id.startswith("s-") else 10.0


def _run(monkeypatch, tmp_path, client, seed=None, **seed_kw):
    _hermetic(monkeypatch, tmp_path, ["AAPL"])
    monkeypatch.setattr(_main_cycle, "MODEL_ENTRIES_ENABLED", True)
    if seed is not False:
        db = _init_db_core(str(tmp_path / "t.db"))
        _seed(db, **seed_kw)
        db.close()
    captured = []
    real_entry = m._handle_entry

    def spy(con, cl, risk, symbol, ctx):
        captured.append((symbol, ctx))
        return real_entry(con, cl, risk, symbol, ctx)
    monkeypatch.setattr(m, "_handle_entry", spy)
    m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    return captured


def test_exit_only_name_is_stopped_on_its_own_lot_and_never_buys(monkeypatch, tmp_path):
    client = _OverlayClient()
    captured = _run(monkeypatch, tmp_path, client, shares=5.0, buys=(5.0,))
    assert client.sells == [(SYM, 5.0)], "stop must sell only the stock lot (5), not the blended 15"
    assert SYM not in client.buys and all(s != SYM for s, _ in captured)


def test_exit_only_name_with_zero_shares_sends_no_sell_and_reaches_no_entry(monkeypatch, tmp_path):
    # NULL shares is covered at the exit_view level above: a NULL row aborts run() earlier, at the
    # pre-existing invested-cost-basis sum in bot/main.py (float(None)), before any order is possible.
    client = _OverlayClient()
    captured = _run(monkeypatch, tmp_path, client, shares=0.0, buys=(5.0,))
    assert client.sells == []
    assert SYM not in client.buys and all(s != SYM for s, _ in captured)


def test_entry_context_positions_keeps_the_full_broker_quantity(monkeypatch, tmp_path):
    client = _OverlayClient(xlk_close=120.0)     # no stop: exit rules hold
    captured = _run(monkeypatch, tmp_path, client, shares=5.0, buys=(5.0,))
    ctx = next(c for s, c in captured if s == "AAPL")
    assert ctx.positions[SYM].qty == 15.0 and ctx.positions[SYM].avg_entry_price == 95.0
    assert client.buys == ["AAPL"]


def test_exit_only_name_with_no_bars_warns_instead_of_skipping_silently(monkeypatch, tmp_path):
    real_prepare = m.prepare_cycle_context

    def no_xlk_bars(*a, **k):
        out = list(real_prepare(*a, **k))
        out[5] = {s: b for s, b in out[5].items() if s != SYM}     # bars_map
        return tuple(out)
    monkeypatch.setattr(m, "prepare_cycle_context", no_xlk_bars)
    seen, client = [], _OverlayClient()
    sink = logger.add(lambda msg: seen.append(msg.record["message"]), level="WARNING")
    try:
        _run(monkeypatch, tmp_path, client, shares=5.0, buys=(5.0,))
    finally:
        logger.remove(sink)
    assert any(SYM in s and "stop protection NOT evaluated" in s for s in seen)
    assert client.sells == [] and SYM not in client.buys


def test_handle_entry_returns_before_the_recorder_for_overlay_names(monkeypatch):
    monkeypatch.setattr(_main_cycle, "MODEL_ENTRIES_ENABLED", True)
    monkeypatch.setattr(_main_cycle, "EntryDecisionRecorder", Mock(side_effect=AssertionError("recorder created")))
    client = SimpleNamespace(buy=Mock())
    ctx = EntryContext(
        positions={}, buy_order_syms=set(), earnings_map={}, bars_map={}, sig_bars=pd.DataFrame(),
        latest=None, current_price=100.0, current_atr=1.0, regime_name="TRENDING_UP", portfolio_value=1e5,
        available_cash=4321.0, xgb_prob=0.9, lstm_prob=0.9, macro_score=0.5, macro_cap=1.0, macro_halt=False,
        spy_5bar_return=None, vs_spy_today=0.0, sentiments={}, ensemble_size=1.0, xgb=None,
        stop_fired_today=set(), volume_ratio=2.0, tradeable_capital=1e5)
    assert _handle_entry(None, client, _risk(), SYM, ctx) == 4321.0
    client.buy.assert_not_called()


# --- risk-officer conditions R1-R5 -------------------------------------------------------------

def _capture_logs(level="WARNING"):
    seen = []
    return seen, logger.add(lambda msg: seen.append(msg.record["message"]), level=level)


def test_cost_basis_skips_null_or_text_rows_and_names_the_field(con):
    from bot._main_db import position_state_cost_basis
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('AAA',10,10,3)")
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('NULLSH',10,10,NULL)")
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('NULLPX',NULL,10,4)")
    con.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, shares) VALUES ('TXT','abc',10,4)")
    con.commit()
    seen, sink = _capture_logs("ERROR")
    try:
        assert position_state_cost_basis(con) == 30.0      # only AAA counted; bad rows are skipped, not zero-filled
    finally:
        logger.remove(sink)
    assert any("NULLSH" in s and "shares" in s for s in seen)
    assert any("NULLPX" in s and "entry_price" in s for s in seen)
    assert any("TXT" in s and "entry_price" in s for s in seen)


def test_null_shares_row_does_not_abort_run_and_other_exit_is_still_evaluated(monkeypatch, tmp_path):
    """R3: one NULL-shares position_state row must not stop the cycle; JPM's stop still fires."""
    client = _OverlayClient(xlk_close=120.0)
    jpm = position_placeholder("JPM", 10, 800.0, 100.0)
    jpm.unrealized_plpc = -0.20                      # well past the stop
    ko = position_placeholder("KO", 10, 600.0, 60.0)
    client._pos = {"JPM": jpm, "KO": ko}
    _hermetic(monkeypatch, tmp_path, ["AAPL", "JPM", "KO"])
    db = _init_db_core(str(tmp_path / "t.db"))
    db.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, atr_at_entry, opened_at, shares) "
               "VALUES ('JPM',100,100,3,?,10)", (NOW,))
    db.execute("INSERT INTO position_state (symbol, entry_price, high_water_mark, atr_at_entry, opened_at, shares) "
               "VALUES ('KO',60,60,1,?,NULL)", (NOW,))
    db.execute("INSERT INTO trades (timestamp, symbol, action, shares, price, notional) VALUES (?,?,?,?,?,?)",
               (NOW, "JPM", "BUY", 10, 100.0, 1000.0))
    db.commit()
    db.close()
    evaluated = []
    real_exits = m._handle_exits

    def spy(con, cl, risk, symbol, *a, **k):
        evaluated.append(symbol)
        return real_exits(con, cl, risk, symbol, *a, **k)
    monkeypatch.setattr(m, "_handle_exits", spy)
    seen, sink = _capture_logs("ERROR")
    try:
        m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    finally:
        logger.remove(sink)
    assert any("KO" in s and "shares" in s and "skipped" in s for s in seen), seen
    assert "JPM" in evaluated, "exit for another held stock must still be evaluated"
    assert any(sym == "JPM" for sym, _ in client.sells), "the JPM stop must have sold"


def test_exit_only_name_with_five_consecutive_errors_is_still_evaluated_and_alerted(monkeypatch, tmp_path):
    """R1/R2/R5: no 5-error skip, an operator alert, and no candidate event for an exit-only name."""
    client = _OverlayClient()                        # XLK at 91 vs entry 100: stop fires once evaluation works
    _hermetic(monkeypatch, tmp_path, ["AAPL"])
    monkeypatch.setattr(_main_cycle, "MODEL_ENTRIES_ENABLED", True)
    db = _init_db_core(str(tmp_path / "t.db"))
    _seed(db, shares=5.0, buys=(5.0,))
    db.close()
    monkeypatch.setattr(m, "_sym_errors", {})
    monkeypatch.setattr(m, "_unprotected_alerted", set())
    alerts, candidates = [], []
    monkeypatch.setattr(m.tg, "_send", lambda msg, *a, **k: alerts.append(msg))
    real_candidate = m.record_candidate_safe

    def spy_candidate(tc, symbol, *a, **k):
        candidates.append(symbol)
        return real_candidate(tc, symbol, *a, **k)
    monkeypatch.setattr(m, "record_candidate_safe", spy_candidate)
    real_view, state = m.exit_view, {"fail": True}

    def flaky_view(*a, **k):
        if state["fail"]:
            raise RuntimeError("feed blew up <5>")
        return real_view(*a, **k)
    monkeypatch.setattr(m, "exit_view", flaky_view)
    for _ in range(5):
        m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    assert m._sym_errors[SYM] == 5 and not [x for x in client.sells if x[0] == SYM]
    assert SYM not in candidates, "no candidate evaluation event for an exit-only name"
    xlk_alerts = [a for a in alerts if SYM in a and "NOT evaluated" in a]
    assert len(xlk_alerts) == 1, "alert is rate limited to once per symbol per day"
    assert "&lt;5&gt;" in xlk_alerts[0], "error text must be HTML-escaped for Telegram"
    state["fail"] = False                            # feed recovers; the 6th cycle must NOT skip XLK
    m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    assert [x for x in client.sells if x[0] == SYM] == [(SYM, 5.0)], "exit must be evaluated on the cycle after five errors"
    assert SYM not in candidates


def test_exit_only_name_with_no_bars_sends_an_operator_alert(monkeypatch, tmp_path):
    real_prepare = m.prepare_cycle_context

    def no_xlk_bars(*a, **k):
        out = list(real_prepare(*a, **k))
        out[5] = {s: b for s, b in out[5].items() if s != SYM}
        return tuple(out)
    monkeypatch.setattr(m, "prepare_cycle_context", no_xlk_bars)
    monkeypatch.setattr(m, "_unprotected_alerted", set())
    alerts = []
    client = _OverlayClient()
    _hermetic(monkeypatch, tmp_path, ["AAPL"])
    monkeypatch.setattr(m.tg, "_send", lambda msg, *a, **k: alerts.append(msg))
    db = _init_db_core(str(tmp_path / "t.db"))
    _seed(db, shares=5.0, buys=(5.0,))
    db.close()
    m.run("paper", _client=client, _regime_clf=_Regime(), _xgb=_XGB(), _lstm=_LSTM())
    assert any(SYM in a and "no price bars" in a for a in alerts)


def test_alert_helper_is_once_per_symbol_per_key_set():
    from bot._main_overlay import alert_exit_unevaluated
    sent, alerted = [], set()
    assert alert_exit_unevaluated(SYM, "r", alerted, sent.append) is True
    assert alert_exit_unevaluated(SYM, "r", alerted, sent.append) is False
    assert alert_exit_unevaluated("XLF", "r", alerted, sent.append) is True and len(sent) == 2


def test_shares_rewritten_lower_logs_a_warning_with_all_clamp_inputs(con):
    _seed(con, shares=6.0, buys=(4.0,))              # state 6, net trades 4, broker 15 -> clamps to 4
    view = exit_view(con, SYM, {SYM: _broker(qty=15.0)}, 104.0)
    seen, sink = _capture_logs()
    try:
        _handle_exits(con, _SellClient(), _risk(), SYM, view, set(), 104.0, 3.0, "TRENDING_UP",
                      100_000.0, 0, True, set())
    finally:
        logger.remove(sink)
    msg = next(s for s in seen if "position_state.shares rewritten" in s)
    assert SYM in msg and "6.0 -> 4.0" in msg
    assert "'broker_qty': 15.0" in msg and "'net_trade_shares': 4.0" in msg and "'position_state_shares': 6.0" in msg
    assert con.execute("SELECT shares FROM position_state WHERE symbol=?", (SYM,)).fetchone()[0] == 4.0


def test_no_shares_warning_when_quantity_is_unchanged_or_higher(con):
    _seed(con, shares=5.0, buys=(5.0,))
    view = exit_view(con, SYM, {SYM: _broker(qty=15.0)}, 104.0)
    seen, sink = _capture_logs()
    try:
        _handle_exits(con, _SellClient(), _risk(), SYM, view, set(), 104.0, 3.0, "TRENDING_UP",
                      100_000.0, 0, True, set())
    finally:
        logger.remove(sink)
    assert not any("rewritten" in s for s in seen)


# --- (vii) the runner refuses --execute while the stock bot holds an overlay name ------------------

@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(rb, "LOG_DIR", tmp_path)
    monkeypatch.setattr(rb, "RUNS", tmp_path / "runs_v2.csv")
    monkeypatch.setattr(rb, "ORDERS", tmp_path / "orders.csv")
    monkeypatch.setattr(rb, "FILLS", tmp_path / "fills.csv")
    monkeypatch.setattr(rb, "HALT_FILE", tmp_path / "HALT_TRADING")
    monkeypatch.setattr(rb, "ALPACA_BASE_URL", ep.PAPER_URL)
    monkeypatch.setattr(rb, "SHARED_ACCOUNT_EXECUTE_APPROVED", True)
    monkeypatch.setattr(rb, "_closes", Mock(side_effect=AssertionError("must refuse before any data fetch")))
    db = tmp_path / "stock.db"
    monkeypatch.setattr(rb, "STOCK_DB", db)
    return db


def _stock_db(path, symbols):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE position_state (symbol TEXT PRIMARY KEY, entry_price REAL, shares REAL)")
    c.executemany("INSERT INTO position_state VALUES (?, 1.0, 1.0)", [(s,) for s in symbols])
    c.commit()
    c.close()


def test_runner_refuses_execute_when_an_overlay_name_has_a_position_state_row(runner):
    _stock_db(runner, ["XLK", "AAPL"])
    with pytest.raises(SystemExit, match=r"position_state rows for overlay names \['XLK'\]"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    assert not rb.RUNS.exists() and not rb.ORDERS.exists()


def test_runner_refuses_execute_when_the_stock_database_is_missing_or_unreadable(runner):
    with pytest.raises(SystemExit, match="not found"):
        rb.main(["x", "--sleeve", "1000", "--execute"])
    runner.write_bytes(b"not a sqlite file at all")
    with pytest.raises(SystemExit, match="cannot read position_state"):
        rb.main(["x", "--sleeve", "1000", "--execute"])


def test_runner_check_passes_when_only_stock_names_are_in_position_state(runner):
    _stock_db(runner, ["AAPL", "MSFT"])
    rb._refuse_if_stock_bot_holds_overlay()   # does not raise
