"""Tests for dashboard.components.trust_scorecard -- the explicit,
user-approved partial unfreeze of Phase 1B analytics (2026-07-30, see
CURRENT_ARCHITECTURE.md). Real-ledger fixture, same pattern as
tests/test_decision_quality.py.

The core thing under test: analytics/scorecard.py, compliance.py, and
calibration.py stay pure real-query always; the dashboard layer supplies an
illustrative fallback only when a real result is empty, and that fallback
must disappear the moment real data exists -- this is the "plug in real
data automatically" contract the user asked for.
"""
import pytest

import ledger.db as ledger_db
import ledger.ledger as ledger_svc
import bot.trust_ledger.candidates as candidates
import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
import bot.trust_ledger.connection as ledger_connection
from bot.strategy.model_output_adapter import build_model_outputs
import dashboard.components.trust_scorecard as ts


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
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-01T00:00:00Z",
    })
    return conn


def _decision(conn, symbol, day, action="BUY", event_type="EXECUTED", confidence=0.65):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, symbol, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action=action,
        event_type=event_type, portfolio_snapshot={"portfolio_value": 10000.0}, market_context={},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2), risk_checks={"gate_trace": []},
        final_confidence=confidence, deployment_manifest_id="mani_v1",
        intent=decisions.build_intent(action), data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T10:00:00Z",
    )


def _constitution_pass(conn, decision_id, rule_id, rule_name):
    ledger_svc.append_ledger_row(conn, "constitution_enforcement_events", {
        "event_id": f"CE-{decision_id}-{rule_id}", "decision_id": decision_id,
        "rule_id": rule_id, "rule_name": rule_name, "check_timestamp": "2026-07-01T10:00:00Z",
        "check_result": "PASS", "action_taken": "advisory_only", "reason": None,
    })


def _risk_event(conn, day="2026-07-01"):
    ledger_svc.append_ledger_row(conn, "risk_evaluation_events", {
        "event_id": f"RE-{day}", "timestamp": f"{day}T09:00:00Z",
        "from_state": "NORMAL", "to_state": "NORMAL", "trigger_reason": "routine",
        "validation_mode": "NATURAL", "replay_scenario_id": None,
        "recommended_position_size": 100.0, "actual_position_size": 100.0,
    })


def test_scorecard_shows_awaiting_first_trade_with_zero_executed_decisions(ledger_conn):
    """On a brand-new ledger, Gates 1 (constitution -- 0/0 checks),
    2 (reproducibility -- 0 sampled), and 4 (risk controls -- no
    risk_evaluation_events) are all "no evidence yet," not failures --
    none of them may render FAIL. Gate 3 (ledger integrity) is the one
    gate that's genuinely PASS on an empty ledger."""
    html = ts.render_trust_scorecard()
    assert html.count("AWAITING FIRST TRADE") == 3
    assert "FAIL" not in html
    assert "Evidence still accumulating" in html


def test_scorecard_shows_real_numbers_once_a_trade_executes(ledger_conn):
    _risk_event(ledger_conn)
    row = _decision(ledger_conn, "AAPL", "2026-07-01")
    _constitution_pass(ledger_conn, row["decision_id"], "rule_1", "Risk Governor Authority")
    ledger_conn.commit()
    html = ts.render_trust_scorecard()
    assert "AWAITING FIRST TRADE" not in html
    assert ">1<" in html  # Decisions Collected stat card


def test_constitution_compliance_empty_state(ledger_conn):
    html = ts.render_constitution_compliance()
    assert "No constitution checks recorded yet" in html


def test_constitution_compliance_shows_real_per_rule_breakdown(ledger_conn):
    row = _decision(ledger_conn, "AAPL", "2026-07-01")
    _constitution_pass(ledger_conn, row["decision_id"], "rule_1", "Risk Governor Authority")
    _constitution_pass(ledger_conn, row["decision_id"], "rule_2", "Position Sizing Discipline")
    ledger_conn.commit()
    html = ts.render_constitution_compliance()
    assert "rule_1" in html
    assert "Risk Governor Authority" in html
    assert "100%" in html


def test_calibration_shows_illustrative_example_when_no_outcomes(ledger_conn):
    _decision(ledger_conn, "AAPL", "2026-07-01")
    ledger_conn.commit()
    html = ts.render_calibration_buckets()
    assert "Illustrative example" in html


def test_calibration_plugs_in_real_data_once_outcome_exists(ledger_conn):
    """The actual proof of the user's ask: once decision_outcome_events has a
    real row, the illustrative banner must disappear and real bucket numbers
    must appear instead -- automatically, with no code change."""
    row = _decision(ledger_conn, "AAPL", "2026-07-01", confidence=0.75)
    outcomes.write_decision_outcome_event(
        ledger_conn, "AAPL", row["decision_id"], "2026-07-05T15:00:00Z", 0.05, 4,
    )
    ledger_conn.commit()
    html = ts.render_calibration_buckets()
    assert "Illustrative example" not in html
    assert "0.7-0.9" in html  # real confidence bucket for 0.75
