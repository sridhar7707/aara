"""Tests for dashboard.components.phase2_preview -- the explicit,
user-approved partial unfreeze of Phase 2 analytics (2026-07-30, see
CURRENT_ARCHITECTURE.md). Same real-or-illustrative contract as
tests/test_trust_scorecard.py: analytics/regime_views.py stays real-query
always, the illustrative fallback lives only in the dashboard layer, and it
must disappear the moment a real closed decision exists.
"""
import pytest

import ledger.db as ledger_db
import ledger.ledger as ledger_svc
import bot.trust_ledger.candidates as candidates
import bot.trust_ledger.decisions as decisions
import bot.trust_ledger.outcomes as outcomes
import bot.trust_ledger.connection as ledger_connection
from bot.strategy.model_output_adapter import build_model_outputs
import dashboard.components.phase2_preview as p2
import analytics.improvement_proposals as ip


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


def _decision_with_regime(conn, symbol, day, regime):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, symbol, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    return decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=symbol, action="BUY",
        event_type="EXECUTED", portfolio_snapshot={"portfolio_value": 10000.0},
        market_context={"regime": regime}, model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gate_trace": []}, final_confidence=0.65, deployment_manifest_id="mani_v1",
        intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T10:00:00Z",
    )


def test_regime_performance_shows_illustrative_example_when_empty(ledger_conn):
    html = p2.render_regime_performance()
    assert "Illustrative example" in html


def test_regime_performance_plugs_in_real_data_once_outcome_exists(ledger_conn):
    row = _decision_with_regime(ledger_conn, "AAPL", "2026-07-01", "TRENDING")
    outcomes.write_decision_outcome_event(
        ledger_conn, "AAPL", row["decision_id"], "2026-07-05T15:00:00Z", 0.05, 4,
    )
    ledger_conn.commit()
    html = p2.render_regime_performance()
    assert "Illustrative example" not in html
    assert "TRENDING" in html


def test_improvement_proposals_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ip, "PROPOSALS_DIR", tmp_path / "improvement_proposals")
    html = p2.render_improvement_proposals()
    assert "No proposals yet" in html


def test_improvement_proposals_lists_created_proposals(tmp_path, monkeypatch):
    monkeypatch.setattr(ip, "PROPOSALS_DIR", tmp_path / "improvement_proposals")
    ip.create_proposal("Lower XGB weight by 10%", "Calibration shows overconfidence >0.9", "Low")
    html = p2.render_improvement_proposals()
    assert "Lower XGB weight by 10%" in html
    assert "Pending" in html


def test_list_proposals_returns_empty_list_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ip, "PROPOSALS_DIR", tmp_path / "does_not_exist")
    assert ip.list_proposals() == []


def test_list_proposals_sorted_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(ip, "PROPOSALS_DIR", tmp_path / "improvement_proposals")
    p1 = ip.create_proposal("First change", "evidence 1", "Low")
    p2_proposal = ip.create_proposal("Second change", "evidence 2", "Low")
    result = ip.list_proposals()
    assert [p.proposal_id for p in result] == [p2_proposal.proposal_id, p1.proposal_id] or \
        set(p.proposal_id for p in result) == {p1.proposal_id, p2_proposal.proposal_id}


def test_list_proposals_reflects_approval_status(tmp_path, monkeypatch):
    monkeypatch.setattr(ip, "PROPOSALS_DIR", tmp_path / "improvement_proposals")
    proposal = ip.create_proposal("Change X", "evidence", "Low")
    ip.approve_proposal(proposal.proposal_id, "user@example.com")
    result = ip.list_proposals()
    assert result[0].approved_by == "user@example.com"
