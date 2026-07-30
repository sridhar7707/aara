"""Tests for dashboard.components.timeline.

Reads the Trust Ledger (decision_events), not the retired decision_log
(phase0_decisions.md #17/#18) -- fixtures build a minimal ledger reference
chain, same pattern as tests/test_decision_quality.py. Regression coverage
for the staleness bug where this component was left querying decision_log
after the write-path cutover (2026-07-28), silently freezing forever.
"""
import pytest

import ledger.db as ledger_db
import bot.trust_ledger.candidates as candidates
import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.connection as ledger_connection
from bot.strategy.model_output_adapter import build_model_outputs
import dashboard.components.timeline as timeline


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def ledger_conn(tmp_path, monkeypatch):
    ledger_path = str(tmp_path / "ledger_test.db")
    monkeypatch.setattr(ledger_connection, "DEFAULT_LEDGER_DB_PATH", ledger_path)

    conn = ledger_db.init_db(ledger_path)
    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-01T00:00:00Z')"
    )
    conn.commit()
    return conn


def _buy(conn, symbol, day, fill_price, fill_shares, confidence=0.65):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, symbol, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="BUY",
        event_type="EXECUTED", portfolio_snapshot={"portfolio_value": 10000.0, "available_cash": 5000.0},
        market_context={}, model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gate_trace": [], "notional": fill_price * fill_shares,
                     "fill_price": fill_price, "fill_shares": fill_shares},
        final_confidence=confidence, deployment_manifest_id="mani_v1",
        intent=decisions.build_intent("BUY", thesis=f"{symbol}: strong setup"),
        data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T10:00:00Z",
    )


def _sell(conn, symbol, day, current_price, reason="RISK_MANAGEMENT_EXIT", confidence=0.55):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, symbol, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="SELL",
        event_type="EXECUTED", portfolio_snapshot={"portfolio_value": 10500.0, "current_price": current_price},
        market_context={}, model_outputs=build_model_outputs(0.4, 0.5, -0.1),
        risk_checks={"exit_reason": reason}, final_confidence=confidence,
        deployment_manifest_id="mani_v1", intent=decisions.build_intent("SELL"),
        data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T15:00:00Z",
    )


def _reject(conn, symbol, day):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, symbol, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="REJECT",
        event_type="QUALIFIED_REJECTION", portfolio_snapshot={"portfolio_value": 10000.0},
        market_context={}, model_outputs=build_model_outputs(0.3, 0.4, 0.0),
        risk_checks={"gate_trace": [{"gate": "confidence", "passed": False}]}, final_confidence=0.3,
        deployment_manifest_id="mani_v1", intent=decisions.build_intent("REJECT"),
        data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T10:00:00Z",
    )


def test_no_history_shows_empty_state(ledger_conn):
    html = timeline.render_decision_timeline("AAPL")
    assert "No history for AAPL" in html


def test_no_symbol_prompts_selection(ledger_conn):
    html = timeline.render_decision_timeline(None)
    assert "Select a symbol" in html


def test_buy_entry_shows_price_reasoning_and_confidence(ledger_conn):
    _buy(ledger_conn, "AAPL", "2026-07-01", 150.0, 10.0, confidence=0.72)
    html = timeline.render_decision_timeline("AAPL")
    assert "Buy" in html
    assert "$150.00" in html
    assert "AAPL: strong setup" in html
    assert "72% confidence" in html


def test_sell_entry_uses_exit_reason_not_thesis(ledger_conn):
    _buy(ledger_conn, "AAPL", "2026-07-01", 150.0, 10.0)
    _sell(ledger_conn, "AAPL", "2026-07-05", 160.0, reason="target hit")
    html = timeline.render_decision_timeline("AAPL")
    assert "Sell" in html
    assert "target hit" in html


def test_total_return_computed_from_buy_and_sell_prices(ledger_conn):
    _buy(ledger_conn, "AAPL", "2026-07-01", 100.0, 10.0)
    _sell(ledger_conn, "AAPL", "2026-07-11", 110.0)
    html = timeline.render_decision_timeline("AAPL")
    assert "+10.0%" in html
    assert "10 days" in html


def test_qualified_rejection_excluded_from_timeline(ledger_conn):
    """A REJECT/QUALIFIED_REJECTION doesn't change the position -- it must
    not appear (or count) in a symbol's decision timeline."""
    _reject(ledger_conn, "AAPL", "2026-07-01")
    html = timeline.render_decision_timeline("AAPL")
    assert "No history for AAPL" in html


def test_all_timelines_empty_state_when_no_executed_decisions(ledger_conn):
    html = timeline.render_all_timelines()
    assert "No decisions logged yet" in html


def test_all_timelines_lists_symbols_with_executed_decisions(ledger_conn):
    _buy(ledger_conn, "AAPL", "2026-07-01", 150.0, 10.0)
    _buy(ledger_conn, "MSFT", "2026-07-02", 300.0, 5.0)
    html = timeline.render_all_timelines()
    assert "AAPL" in html
    assert "MSFT" in html
    assert "2 symbols with decision history" in html


def test_all_timelines_excludes_qualified_rejections(ledger_conn):
    _reject(ledger_conn, "TSLA", "2026-07-01")
    html = timeline.render_all_timelines()
    assert "No decisions logged yet" in html
