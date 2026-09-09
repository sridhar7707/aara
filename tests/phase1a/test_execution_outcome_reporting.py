"""ADR-065: tests for _handle_entry's (bot/_main_cycle.py) additive
Sentinel execution-outcome reporting.

Uses the same real-trust-ledger fixture pattern as
test_decision_capture_integration.py (a fresh, independent file, not a
modification of it) to prove: a successful fill, a RiskManager rejection,
and an executor/order failure are each reported to Sentinel Engine using
the exact Trust Ledger decision_id EntryDecisionRecorder already wrote,
without ever touching RiskManager, PaperExecutor/client, or the existing
Trust Ledger write path itself, and that a Sentinel-reporting failure never
affects an already-completed trade.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bot._main_db as main_db  # noqa: E402
import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot._main_cycle as main_cycle  # noqa: E402
from bot._main_cycle import _handle_entry, EntryContext  # noqa: E402
from bot.risk.risk_manager import RiskManager  # noqa: E402
from sentinel_engine.composition.execution import (  # noqa: E402
    get_decision_service_for_execution_reporting,
    _ledger_repository as _execution_ledger_repository,
)
from sentinel_engine.events.event_types import EventType  # noqa: E402


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


class _AlwaysApproveRealRisk(RiskManager):
    def approve_buy(self, *args, **kwargs):
        return True


class _AlwaysRejectRealRisk(RiskManager):
    def approve_buy(self, *args, **kwargs):
        return False


class _FakeFillClient:
    def buy(self, symbol, notional, limit_price=None):
        return {"order_id": "ord-1"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 10.0

    def get_fill_price(self, order_id):
        return 100.0


class _FakeNoFillClient:
    """client.buy() succeeds (order accepted) but it never fills."""
    def buy(self, symbol, notional, limit_price=None):
        return {"order_id": "ord-timeout"}

    def wait_for_fill(self, order_id, timeout_secs=15):
        return 0.0


class _FakeRejectingBrokerClient:
    """client.buy() itself fails (e.g. broker rejects the order)."""
    def buy(self, symbol, notional, limit_price=None):
        return None


class _FakeXgb:
    def explain(self, row):
        return [("rsi", 0.1)]


def _latest_decision_id(conn, asset):
    row = conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset=? "
        "ORDER BY sequence_number DESC LIMIT 1", (asset,),
    ).fetchone()
    return row[0] if row else None


def _execution_events_for(decision_id):
    return [
        event for event in _execution_ledger_repository.get_events()
        if event.event_type == EventType.DECISION_EXECUTED
        and event.payload.get("decision_id") == decision_id
    ]


# -- 5/6. Successful paper execution reported as success, identity preserved -

def test_successful_fill_reports_filled_outcome_with_preserved_decision_identity(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRealRisk(),
                   symbol="AAPL", ctx=ctx)

    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    assert decision_id is not None

    events = _execution_events_for(decision_id)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["decision_id"] == decision_id  # identity preserved end-to-end
    assert payload["symbol"] == "AAPL"
    assert payload["action"] == "BUY"
    assert payload["side"] == "buy"
    assert payload["outcome"] == "FILLED"
    assert payload["is_paper"] is True
    assert payload["order_id"] == "ord-1"
    assert payload["fill_price"] == 100.0


# -- 3. RiskManager rejection prevents execution and is reported as such ----

def test_risk_rejection_prevents_execution_and_is_reported(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )
    client = _FakeFillClient()

    result_cash = _handle_entry(trades_db, client=client, risk=_AlwaysRejectRealRisk(),
                                 symbol="AAPL", ctx=ctx)

    assert result_cash == ctx.available_cash  # no cash spent -- no execution occurred
    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    assert decision_id is not None
    events = _execution_events_for(decision_id)
    assert len(events) == 1
    assert events[0].payload["outcome"] == "REJECTED"
    assert "risk.approve_buy" in events[0].payload["reason"]


# -- 4. Executor/order failure is represented as failure ---------------------

def test_order_fill_timeout_is_reported_as_failed(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeNoFillClient(), risk=_AlwaysApproveRealRisk(),
                   symbol="AAPL", ctx=ctx)

    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    events = _execution_events_for(decision_id)
    assert len(events) == 1
    assert events[0].payload["outcome"] == "FAILED"


def test_order_submission_failure_is_reported_as_failed(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    _handle_entry(trades_db, client=_FakeRejectingBrokerClient(), risk=_AlwaysApproveRealRisk(),
                   symbol="AAPL", ctx=ctx)

    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    events = _execution_events_for(decision_id)
    assert len(events) == 1
    assert events[0].payload["outcome"] == "FAILED"


# -- 2. Missing Sentinel correlation (no matching row) preserves behavior ---

def test_gate_rejection_with_no_trust_conn_does_not_raise(trades_db, ledger_conn, chain):
    """trust_conn=None (a caller/test not wired to the ledger) must remain a
    silent no-op -- identical to EntryDecisionRecorder's own best-effort
    philosophy, and existing behavior for every caller that never set up a
    trust_conn."""
    ctx = _minimal_entry_ctx(ledger_conn, chain, macro_halt=True, trust_conn=None,
                              candidate_event_id=None, deployment_manifest_id=None)

    result_cash = _handle_entry(trades_db, client=None, risk=None, symbol="AAPL", ctx=ctx)

    assert result_cash == ctx.available_cash


# -- 7/9. Reporting cannot trigger a second trade; a reporting failure ------
# -- does not undo a completed trade -----------------------------------------

def test_reporting_failure_does_not_affect_an_already_completed_trade(monkeypatch, trades_db, ledger_conn, chain):
    def _boom(decision_id, payload):
        raise RuntimeError("simulated Sentinel outage")

    class _BoomService:
        record_execution = staticmethod(_boom)

    monkeypatch.setattr(main_cycle, "get_decision_service_for_execution_reporting", lambda: _BoomService())

    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )

    result_cash = _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRealRisk(),
                                 symbol="AAPL", ctx=ctx)

    # The trade itself completed exactly as it would have without the
    # reporting failure -- cash was spent, decision_events row exists.
    assert result_cash < ctx.available_cash
    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    assert decision_id is not None
    # No Sentinel event exists (the report call raised before saving), but
    # that failure never propagated out of _handle_entry.
    assert _execution_events_for(decision_id) == []


# -- 8. Duplicate cycle/retry does not duplicate the Sentinel-side record --

def test_reporting_the_same_decision_twice_does_not_duplicate(trades_db, ledger_conn, chain):
    ctx = _minimal_entry_ctx(
        ledger_conn, chain, current_atr=2.0, xgb=_FakeXgb(),
        tradeable_capital=5000.0, available_cash=5000.0, portfolio_value=10000.0,
    )
    _handle_entry(trades_db, client=_FakeFillClient(), risk=_AlwaysApproveRealRisk(),
                   symbol="AAPL", ctx=ctx)
    decision_id = _latest_decision_id(ledger_conn, "AAPL")
    assert len(_execution_events_for(decision_id)) == 1

    # Simulate a retried report call for the same already-recorded decision
    # (e.g. a scheduler retry re-running the report step) directly against
    # the composition accessor -- record_execution() itself must no-op.
    from sentinel_engine.adapters.execution_adapter import to_execution_outcome
    import datetime
    payload = to_execution_outcome({
        "decision_id": decision_id, "symbol": "AAPL", "action": "BUY", "side": "buy",
        "outcome": "FILLED", "is_paper": True,
        "timestamp": datetime.datetime.now(datetime.timezone.utc), "fill_price": 100.0,
    })
    result = get_decision_service_for_execution_reporting().record_execution(decision_id, payload)

    assert result is None
    assert len(_execution_events_for(decision_id)) == 1
