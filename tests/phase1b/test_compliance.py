"""Tests for analytics/compliance.py (Phase 1B scaffolding).

Writes constitution_enforcement_events rows directly (rather than going
through bot.trust_ledger.constitution.check_and_log) so these tests exercise
compliance.py's own aggregation logic, not constitution.py's rule thresholds
-- the two are already covered separately by tests/phase1a/test_constitution.py.
"""
from __future__ import annotations

import bot.trust_ledger.decisions as decisions
import ledger.ledger as ledger_svc
from bot.strategy.model_output_adapter import build_model_outputs
from bot.trust_ledger.ids import new_constitution_event_id

from analytics.compliance import constitution_compliance_report


def _write_decision(conn, reference_chain, asset):
    return decisions.write_decision_event(
        conn,
        candidate_event_id=reference_chain["candidate_event_id"],
        asset=asset, action="BUY", event_type="EXECUTED",
        portfolio_snapshot={"value": 10000.0}, market_context={"regime": "TRENDING_UP"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.8,
        deployment_manifest_id=reference_chain["manifest_id"],
        intent=decisions.build_intent("BUY"),
        data_completeness=decisions.build_data_completeness(),
    )["decision_id"]


def _log_check(conn, decision_id, rule_id, rule_name, check_result):
    ledger_svc.append_ledger_row(conn, "constitution_enforcement_events", {
        "event_id": new_constitution_event_id(),
        "decision_id": decision_id,
        "rule_id": rule_id,
        "rule_name": rule_name,
        "check_timestamp": "2026-07-29T00:00:00Z",
        "check_result": check_result,
        "action_taken": "execution_proceeded" if check_result == "PASS" else "advisory_only",
        "reason": "test",
    })


def test_constitution_compliance_report_empty_ledger(conn):
    report = constitution_compliance_report(conn)
    assert report.total_decisions == 0
    assert report.total_checks == 0
    assert report.overall_pass_rate == 0.0
    assert report.by_rule == []


def test_constitution_compliance_report_aggregates_by_rule(conn, reference_chain):
    d1 = _write_decision(conn, reference_chain, "AAPL")
    d2 = _write_decision(conn, reference_chain, "MSFT")

    _log_check(conn, d1, "rule_1", "Risk Governor Authority", "PASS")
    _log_check(conn, d2, "rule_1", "Risk Governor Authority", "PASS")
    _log_check(conn, d1, "rule_3", "Trade Structure Requirement", "PASS")
    _log_check(conn, d2, "rule_3", "Trade Structure Requirement", "ESCALATED")

    report = constitution_compliance_report(conn)

    assert report.total_decisions == 2
    assert report.total_checks == 4
    assert report.overall_pass_rate == 0.75

    by_rule = {r.rule_id: r for r in report.by_rule}
    assert by_rule["rule_1"].total_checks == 2
    assert by_rule["rule_1"].pass_count == 2
    assert by_rule["rule_1"].pass_rate == 1.0
    assert by_rule["rule_3"].total_checks == 2
    assert by_rule["rule_3"].pass_count == 1
    assert by_rule["rule_3"].escalated_count == 1
    assert by_rule["rule_3"].pass_rate == 0.5
