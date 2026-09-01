"""End-to-end integration tests for Phase 1A Sprint 3: proves _handle_entry
(bot/_main_cycle.py) and _handle_exits (bot/_main_positions.py) actually
write decision_events rows when wired to a real ledger connection -- not
just that they tolerate ledger_ctx=None (already covered by the fact that
every existing tests/test_main.py test still passes unmodified)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bot._main_db as main_db  # noqa: E402
import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
from bot._main_cycle import _handle_entry, EntryContext  # noqa: E402
from bot._main_positions import _handle_exits  # noqa: E402
from bot._main_trust_decisions import ExitDecisionRecorder, ExitLedgerContext  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def trades_db():
    con = main_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def ledger_conn():
    con = ledger_db.init_db(":memory:")
    yield con
    con.close()


@pytest.fixture
def chain(ledger_conn):
    ledger_conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    ledger_conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    ledger_conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    ledger_conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    ledger_conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    ledger_conn.commit()
    ledger_svc.append_ledger_row(ledger_conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    row = candidates.record_candidate_evaluation_if_concluded(
        ledger_conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _minimal_entry_ctx(ledger_conn, chain, **overrides) -> EntryContext:
    defaults = dict(
        positions={}, buy_order_syms=set(), earnings_map={}, bars_map={},
        sig_bars=__import__("pandas").DataFrame(), latest={}, current_price=100.0, current_atr=1.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, available_cash=5000.0,
        xgb_prob=0.7, lstm_prob=0.6, macro_score=0.5, macro_cap=1.0,
        macro_halt=False, spy_5bar_return=None, vs_spy_today=0.0, sentiments={},
        ensemble_size=0.12, xgb=None, stop_fired_today=set(), volume_ratio=1.0,
        tradeable_capital=5000.0,
        trust_conn=ledger_conn, candidate_event_id=chain["candidate_event_id"],
        deployment_manifest_id=chain["manifest_id"],
    )
    defaults.update(overrides)
    return EntryContext(**defaults)


class _AlwaysApproveRisk:
    def approve_buy(self, *args, **kwargs):
        return True


class _AlwaysApproveRealRisk(RiskManager):
    """Like _AlwaysApproveRisk, but a real RiskManager subclass -- carries
    the halted/portfolio_high/daily_start_value attributes
    bot.trust_ledger.constitution reads, unlike the bare fake above (whose
    AttributeError would be silently swallowed by record_decision_safe's
    best-effort try/except, meaning zero constitution rows get written)."""
    def approve_buy(self, *args, **kwargs):
        return True


class _FakeFillClient:
    def buy(self, symbol, notional, limit_price=None):
        return {"order_id": "ord-1"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 10.0

    def get_fill_price(self, order_id):
        return 100.0


class _FakeXgb:
    def explain(self, row):
        return [("rsi", 0.1)]


def _latest_decision(conn, asset):
    row = conn.execute(
        "SELECT decision_id, action, event_type, risk_checks, model_outputs FROM decision_events "
        "WHERE asset=? ORDER BY sequence_number DESC LIMIT 1", (asset,),
    ).fetchone()
    return row


def test_handle_entry_gate_rejection_writes_qualified_rejection(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(ledger_conn, chain, macro_halt=True)

    _handle_entry(trades_db, client=None, risk=None, symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    _, action, event_type, risk_checks, model_outputs = row
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"
    trace = json.loads(risk_checks)["gate_trace"]
    assert trace[-1]["gate"] == "vix_halt"
    assert trace[-1]["passed"] is False
    outputs = json.loads(model_outputs)
    assert set(outputs.keys()) == {"xgboost", "lstm", "finbert"}


def test_handle_entry_executed_buy_writes_executed_decision(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    _, action, event_type, risk_checks, model_outputs = row
    assert action == "BUY"
    assert event_type == "EXECUTED"
    trace_payload = json.loads(risk_checks)
    assert trace_payload["notional"] > 0
    assert trace_payload["fill_price"] == 100.0
    # Regression: record_executed() used to reuse the __init__-time
    # model_outputs, which never has SHAP drivers (computing them for
    # every rejected gate would waste SHAP calls) -- an EXECUTED buy must
    # carry the real drivers computed just before the fill, not an empty list.
    outputs = json.loads(model_outputs)
    assert outputs["xgboost"]["metadata"]["shap_drivers"] == [{"feature": "rsi", "shap_value": 0.1}]


def test_handle_entry_executed_buy_passes_constitution_rule_3(trades_db, ledger_conn, chain):
    """End-to-end proof that the real entry path populates
    intent.thesis/invalidation_point/expected_return_basis_points (not just
    a unit test of constitution.py in isolation) -- and that Rule 3 (Trade
    Structure Requirement) actually reads PASS for a genuine executed BUY,
    closing the gap noted in CURRENT_ARCHITECTURE.md."""
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRealRisk(), symbol="AAPL", ctx=ctx)

    decision_id, action, event_type, _, _ = _latest_decision(ledger_conn, "AAPL")
    assert action == "BUY" and event_type == "EXECUTED"

    intent = json.loads(ledger_conn.execute(
        "SELECT intent FROM decision_events WHERE decision_id=?", (decision_id,),
    ).fetchone()[0])
    assert intent["thesis"]
    assert intent["invalidation_point"]
    assert intent["expected_return_basis_points"] is not None

    rule3 = ledger_conn.execute(
        "SELECT check_result FROM constitution_enforcement_events "
        "WHERE decision_id=? AND rule_id='rule_3'", (decision_id,),
    ).fetchone()
    assert rule3 == ("PASS",)


def test_handle_entry_executed_buy_carries_news_data_timestamp(trades_db, ledger_conn, chain):
    """Phase 1A prerequisite #1 (CURRENT_ARCHITECTURE.md): market_context
    must carry news_data_timestamp when available. bot/main.py threads it
    from _load_premarket_sentiment()'s saved_at through EntryContext."""
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
        news_data_timestamp="2026-07-29T12:00:00+00:00",
    )

    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRealRisk(), symbol="AAPL", ctx=ctx)

    decision_id, action, event_type, _, _ = _latest_decision(ledger_conn, "AAPL")
    assert action == "BUY" and event_type == "EXECUTED"
    market_context = json.loads(ledger_conn.execute(
        "SELECT market_context FROM decision_events WHERE decision_id=?", (decision_id,),
    ).fetchone()[0])
    assert market_context["news_data_timestamp"] == "2026-07-29T12:00:00+00:00"


def test_handle_entry_correlation_gate_carries_specific_reason(trades_db, ledger_conn, chain):
    """Regression: the correlation gate used to write a generic placeholder
    ('correlated with an existing held position') to the ledger instead of
    the specific coefficient/symbol _passes_correlation_gate already
    computes -- every other gate carries its real computed detail."""
    import pandas as pd
    from bot._main_positions import BarData

    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    aapl_bars = pd.DataFrame({"close": [100 + i for i in range(30)]}, index=dates)
    msft_bars = pd.DataFrame({"close": [200 + i for i in range(30)]}, index=dates)  # perfectly correlated

    class _FakePosition:
        market_value = 1000.0

    ctx = _minimal_entry_ctx(
        ledger_conn, chain,
        positions={"MSFT": _FakePosition()},
        bars_map={"AAPL": BarData(pd.DataFrame(), aapl_bars), "MSFT": BarData(pd.DataFrame(), msft_bars)},
    )

    _handle_entry(trades_db, client=None, risk=None, symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    trace = json.loads(row[3])["gate_trace"]
    assert trace[-1]["gate"] == "correlation"
    assert "correlation with held MSFT" in trace[-1]["detail"]


def test_bot_main_passes_ledger_ctx_to_handle_exits():
    """Regression test for a real bug caught by code review: bot/main.py's
    production call to _handle_exits() previously omitted ledger_ctx
    entirely, so every exit-side write (7 branches, all individually unit-
    and integration-tested) was silently dead in production. A full
    bot/main.py::run() mock is disproportionate (needs a mocked Alpaca
    account and full market-data pipeline) -- this cheap source check
    guards against the same class of regression recurring."""
    import inspect
    import bot.main as main_mod

    source = inspect.getsource(main_mod.run)
    call_start = source.index("_handle_exits(")
    call_text = source[call_start:source.index("\n\n", call_start)]
    assert "ledger_ctx=" in call_text


def test_handle_entry_order_never_fills_writes_qualified_rejection(trades_db, ledger_conn, chain):
    class _NoBuyClient:
        def buy(self, symbol, notional, limit_price=None):
            return None

    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0,
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_NoBuyClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=ctx)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "REJECT"
    assert row[2] == "QUALIFIED_REJECTION"


class _NeverExitRisk:
    def check_stop_loss(self, *a, **k):
        return False

    def check_trailing_stop(self, *a, **k):
        return False

    def check_pdt(self, *a, **k):
        return True


class _FakePosition:
    def __init__(self, avg_entry_price, qty, unrealized_plpc):
        self.avg_entry_price = avg_entry_price
        self.qty = qty
        self.unrealized_plpc = unrealized_plpc


def _exit_ledger_ctx(ledger_conn, chain, **overrides):
    defaults = dict(
        trust_conn=ledger_conn, candidate_event_id=chain["candidate_event_id"],
        deployment_manifest_id=chain["manifest_id"], xgb_prob=0.6, lstm_prob=0.55,
        sentiment=0.1, macro_score=0.5,
    )
    defaults.update(overrides)
    return ExitLedgerContext(**defaults)


def test_handle_exits_hold_writes_hold_decision(trades_db, ledger_conn, chain):
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=None, risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=100.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=0, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )
    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "HOLD"
    assert row[2] == "QUALIFIED_REJECTION"


def test_handle_exits_carries_news_data_timestamp(trades_db, ledger_conn, chain):
    """Same Phase 1A prerequisite as the entry-path test, on the exit path:
    ExitLedgerContext.news_data_timestamp -> market_context.news_data_timestamp."""
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=None, risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=100.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=0, pdt_exempt=True,
        stop_fired_today=set(),
        ledger_ctx=_exit_ledger_ctx(ledger_conn, chain, news_data_timestamp="2026-07-29T12:00:00+00:00"),
    )
    decision_id = _latest_decision(ledger_conn, "AAPL")[0]
    market_context = json.loads(ledger_conn.execute(
        "SELECT market_context FROM decision_events WHERE decision_id=?", (decision_id,),
    ).fetchone()[0])
    assert market_context["news_data_timestamp"] == "2026-07-29T12:00:00+00:00"


def test_handle_exits_ensemble_sell_writes_executed_sell(trades_db, ledger_conn, chain):
    class _FakeSellClient:
        def sell(self, symbol, qty, limit_price=None):
            return {"order_id": "ord-2"}

        def wait_for_fill(self, order_id, timeout_secs=12):
            return 1.0

    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=_FakeSellClient(), risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=110.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=2, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )
    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "SELL"
    assert row[2] == "EXECUTED"


def test_handle_exits_sells_when_fred_macro_unavailable(trades_db, ledger_conn, chain, monkeypatch):
    """ADR-010 invariant: FRED/macro availability cannot affect an existing
    position's exit path. _handle_exits() takes no macro/halt parameter and
    has no macro import, so an exit must complete unchanged even when the
    macro accessor would raise -- and that accessor must never be touched."""
    macro_mock = Mock(side_effect=RuntimeError("FRED unavailable"))
    monkeypatch.setattr("bot.db.macro_cache.get_macro", macro_mock)

    class _FakeSellClient:
        def sell(self, symbol, qty, limit_price=None):
            return {"order_id": "ord-fred-down"}

        def wait_for_fill(self, order_id, timeout_secs=12):
            return 1.0

    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    _handle_exits(
        trades_db, client=_FakeSellClient(), risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=110.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=2, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )
    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    assert row[1] == "SELL"
    assert row[2] == "EXECUTED"
    macro_mock.assert_not_called()


def test_handle_exits_none_ledger_ctx_is_noop(trades_db):
    """No ledger_ctx passed -- must behave exactly as before Sprint 3."""
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=1.0, unrealized_plpc=0.0)}
    result = _handle_exits(
        trades_db, client=None, risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=100.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=0, pdt_exempt=True,
        stop_fired_today=set(),
    )
    assert result is True  # no exception, no ledger write attempted


def test_full_buy_then_sell_writes_outcome_event_and_closes_decision_state(
    trades_db, ledger_conn, chain,
):
    """Phase 1A Sprint 5 end-to-end: a real BUY through _handle_entry,
    followed by a real SELL through _handle_exits, produces a
    decision_outcome_events row referencing the ORIGINAL BUY's decision_id
    (not the SELL's) and flips decision_state from OPEN to CLOSED."""
    entry_ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )
    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=entry_ctx)

    buy_row = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' AND action='BUY' "
        "ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()
    assert buy_row is not None
    buy_decision_id = buy_row[0]
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "OPEN"

    class _FakeSellClient:
        def sell(self, symbol, qty, limit_price=None):
            return {"order_id": "ord-sell-1"}

        def wait_for_fill(self, order_id, timeout_secs=12):
            return qty_sold

    qty_sold = 1.0
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=qty_sold, unrealized_plpc=0.05)}
    _handle_exits(
        trades_db, client=_FakeSellClient(), risk=_NeverExitRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=105.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10000.0, action=2, pdt_exempt=True,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )

    outcome = ledger_conn.execute(
        "SELECT decision_id, gross_return FROM decision_outcome_events WHERE decision_id=?",
        (buy_decision_id,),
    ).fetchone()
    assert outcome is not None
    assert outcome[0] == buy_decision_id
    assert outcome[1] == 0.05
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "CLOSED"


# ─────────────────────────────────────────────────────────────────────────────
# Zero-fill SELL: a broker-accepted SELL that never fills (filled_qty == 0)
# must not persist a trade, delete position_state, record a PDT day-trade,
# mutate stop_fired_today, or write a Trust-Ledger EXECUTED / outcome event.
# (Fill-quantity fake clients only -- no network, no broker.)
# ─────────────────────────────────────────────────────────────────────────────


class _ZeroFillRisk(_NeverExitRisk):
    """Never triggers an exit gate; PDT day-trades land in an inspectable list."""

    def __init__(self):
        self.day_trade_log = []

    def record_day_trade(self):
        self.day_trade_log.append(1)


class _ZeroFillSellClient:
    """sell()/sell_market() are accepted by the broker; nothing ever fills."""

    def sell(self, symbol, qty, limit_price=None):
        return {"order_id": "ord-zero-limit"}

    def sell_market(self, symbol, qty):
        return {"order_id": "ord-zero-market"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 0.0


class _StopLossRisk(_NeverExitRisk):
    def check_stop_loss(self, *a, **k):
        return True


def test_handle_exits_time_exit_zero_fill_no_pdt_no_ledger_executed(trades_db, ledger_conn, chain):
    """A time-exit SELL the broker accepts but never fills (filled_qty == 0)
    must leave everything untouched: no trades row, position_state intact, no
    PDT record; on the Trust Ledger a QUALIFIED_REJECTION (not EXECUTED), no
    decision_outcome_events row, and the BUY's decision_state still OPEN."""
    from config import MAX_HOLD_DAYS

    # real BUY -> OPEN decision_state + position_state for AAPL
    entry_ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )
    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=entry_ctx)

    buy_decision_id = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' AND action='BUY' "
        "ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "OPEN"

    entry_px, held_qty = trades_db.execute(
        "SELECT entry_price, shares FROM position_state WHERE symbol='AAPL'"
    ).fetchone()

    # Age the position past MAX_HOLD_DAYS so the time-exit gate fires, and pin
    # high_water_mark/shares so _handle_exits' housekeeping upsert (which would
    # otherwise reset opened_at) does not run.
    old_open = (datetime.now(timezone.utc) - timedelta(days=MAX_HOLD_DAYS + 5)).isoformat()
    trades_db.execute(
        "UPDATE position_state SET opened_at=?, high_water_mark=?, shares=? WHERE symbol='AAPL'",
        (old_open, 1_000_000.0, held_qty),
    )
    trades_db.commit()

    ps_before = trades_db.execute("SELECT * FROM position_state WHERE symbol='AAPL'").fetchone()
    trades_before = trades_db.execute("SELECT COUNT(*) FROM trades WHERE symbol='AAPL'").fetchone()[0]
    outcomes_before = ledger_conn.execute("SELECT COUNT(*) FROM decision_outcome_events").fetchone()[0]

    risk = _ZeroFillRisk()
    processed = _handle_exits(
        trades_db, client=_ZeroFillSellClient(), risk=risk, symbol="AAPL",
        positions={"AAPL": _FakePosition(avg_entry_price=entry_px, qty=held_qty, unrealized_plpc=-0.005)},
        sell_order_syms=set(), current_price=98.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10_000.0, action=0, pdt_exempt=False,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )

    assert processed is True
    # zero-fill time exit leaves trades absent
    assert trades_db.execute(
        "SELECT COUNT(*) FROM trades WHERE symbol='AAPL'"
    ).fetchone()[0] == trades_before
    assert trades_db.execute(
        "SELECT COUNT(*) FROM trades WHERE symbol='AAPL' AND action LIKE 'SELL%'"
    ).fetchone()[0] == 0
    # position_state is unchanged
    assert trades_db.execute("SELECT * FROM position_state WHERE symbol='AAPL'").fetchone() == ps_before
    # no PDT record is created
    assert risk.day_trade_log == []
    # Trust Ledger records QUALIFIED_REJECTION rather than EXECUTED
    _, action, event_type, _, _ = _latest_decision(ledger_conn, "AAPL")
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"
    # no decision_outcome_events row is created
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events"
    ).fetchone()[0] == outcomes_before
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == 0
    # decision_state remains OPEN
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "OPEN"


def test_handle_exits_stop_loss_zero_fill_does_not_set_stop_fired_today(trades_db, ledger_conn, chain):
    """A stop-loss whose limit AND market-escalation orders are both accepted
    but fill zero must NOT add the symbol to stop_fired_today (the stop never
    executed), must write no SELL trades row, and must record a
    QUALIFIED_REJECTION on the Trust Ledger."""
    stop_fired_today: set = set()
    positions = {"AAPL": _FakePosition(avg_entry_price=100.0, qty=3.0, unrealized_plpc=-0.05)}

    processed = _handle_exits(
        trades_db, client=_ZeroFillSellClient(), risk=_StopLossRisk(), symbol="AAPL", positions=positions,
        sell_order_syms=set(), current_price=95.0, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10_000.0, action=0, pdt_exempt=False,
        stop_fired_today=stop_fired_today, ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )

    assert processed is True
    # zero-fill stop-loss does not add the symbol to stop_fired_today
    assert "AAPL" not in stop_fired_today
    assert stop_fired_today == set()
    # no SELL trades row
    assert trades_db.execute(
        "SELECT COUNT(*) FROM trades WHERE symbol='AAPL' AND action LIKE 'SELL%'"
    ).fetchone()[0] == 0
    # Trust Ledger: QUALIFIED_REJECTION, not EXECUTED
    _, action, event_type, _, _ = _latest_decision(ledger_conn, "AAPL")
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"


def test_handle_exits_gap_down_zero_fill_does_not_phantom_close(trades_db, ledger_conn, chain):
    """The gap-down hard floor market-sells and, pre-fix, persisted + deleted
    position_state on order *submission* (wait_for_fill discarded). A gap-down
    market order the broker accepts but never fills (halt / LULD pause /
    post-accept rejection) must NOT phantom-close the position: no trades row,
    position_state intact, no PDT record, Trust-Ledger QUALIFIED_REJECTION (not
    EXECUTED), no decision_outcome_events row, BUY decision_state still OPEN."""
    # real BUY -> OPEN decision_state + position_state for AAPL
    entry_ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )
    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRisk(), symbol="AAPL", ctx=entry_ctx)

    buy_decision_id = ledger_conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' AND action='BUY' "
        "ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "OPEN"

    entry_px, held_qty = trades_db.execute(
        "SELECT entry_price, shares FROM position_state WHERE symbol='AAPL'"
    ).fetchone()

    ps_before = trades_db.execute("SELECT * FROM position_state WHERE symbol='AAPL'").fetchone()
    trades_before = trades_db.execute("SELECT COUNT(*) FROM trades WHERE symbol='AAPL'").fetchone()[0]
    outcomes_before = ledger_conn.execute("SELECT COUNT(*) FROM decision_outcome_events").fetchone()[0]

    risk = _ZeroFillRisk()
    processed = _handle_exits(
        trades_db, client=_ZeroFillSellClient(), risk=risk, symbol="AAPL",
        positions={"AAPL": _FakePosition(avg_entry_price=entry_px, qty=held_qty, unrealized_plpc=-0.15)},
        sell_order_syms=set(), current_price=entry_px * 0.85, current_atr=0.0,
        regime_name="TRENDING_UP", portfolio_value=10_000.0, action=0, pdt_exempt=False,
        stop_fired_today=set(), ledger_ctx=_exit_ledger_ctx(ledger_conn, chain),
    )

    assert processed is True
    # no SELL_GAP_DOWN / trade row is created
    assert trades_db.execute(
        "SELECT COUNT(*) FROM trades WHERE symbol='AAPL'"
    ).fetchone()[0] == trades_before
    assert trades_db.execute(
        "SELECT COUNT(*) FROM trades WHERE symbol='AAPL' AND action LIKE 'SELL%'"
    ).fetchone()[0] == 0
    # position_state remains unchanged
    assert trades_db.execute("SELECT * FROM position_state WHERE symbol='AAPL'").fetchone() == ps_before
    # PDT / day_trade_log remains unchanged
    assert risk.day_trade_log == []
    # Trust Ledger records REJECT / QUALIFIED_REJECTION
    _, action, event_type, _, _ = _latest_decision(ledger_conn, "AAPL")
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"
    # no decision_outcome_events row is created
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events"
    ).fetchone()[0] == outcomes_before
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == 0
    # original decision_state remains OPEN
    assert ledger_conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (buy_decision_id,)
    ).fetchone()[0] == "OPEN"


def test_exit_decision_recorder_sell_false_writes_qualified_rejection_no_outcome(ledger_conn, chain):
    """Unit test of ExitDecisionRecorder.sell(success=False): it must append a
    REJECT / QUALIFIED_REJECTION decision_events row (reason: '<r> sell order
    failed to fill') and must NOT run _record_outcome -- no
    decision_outcome_events row is written."""
    rec = ExitDecisionRecorder(
        _exit_ledger_ctx(ledger_conn, chain), "AAPL",
        portfolio_value=10_000.0, current_price=98.0, regime_name="TRENDING_UP",
    )
    outcomes_before = ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events"
    ).fetchone()[0]

    rec.sell(False, "time-exit", pnl_pct=-0.02, holding_days=45)

    row = _latest_decision(ledger_conn, "AAPL")
    assert row is not None
    _, action, event_type, risk_checks, _ = row
    assert action == "REJECT"
    assert event_type == "QUALIFIED_REJECTION"
    assert json.loads(risk_checks) == {"exit_reason": "time-exit sell order failed to fill"}
    # _record_outcome was not invoked
    assert ledger_conn.execute(
        "SELECT COUNT(*) FROM decision_outcome_events"
    ).fetchone()[0] == outcomes_before
