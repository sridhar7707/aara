"""End-to-end integration tests for Phase 1A Sprint 3: proves _handle_entry
(bot/_main_cycle.py) and _handle_exits (bot/_main_positions.py) actually
write decision_events rows when wired to a real ledger connection -- not
just that they tolerate ledger_ctx=None (already covered by the fact that
every existing tests/test_main.py test still passes unmodified)."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bot._main_db as main_db  # noqa: E402
import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
from bot._main_cycle import _handle_entry, EntryContext  # noqa: E402
from bot._main_positions import _handle_exits  # noqa: E402
from bot._main_trust_decisions import ExitLedgerContext  # noqa: E402
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
