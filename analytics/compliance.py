"""Phase 1B scaffolding (phase1b_requirements.md Section 6): Constitution
Compliance Report over constitution_enforcement_events.

Not wired into any dashboard, cron job, or bot pipeline -- see
analytics/calibration.py's module docstring for the same gating note.

rule_id/rule_name pairs are read directly from the ledger rather than
hardcoded here -- bot/trust_ledger/constitution.py already assigns them
(rule_1..rule_6) when it writes each row, and this module should reflect
whatever rules actually ran, not a guess at what they might be.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class RuleCompliance:
    rule_id: str
    rule_name: str
    total_checks: int
    pass_count: int
    fail_count: int
    escalated_count: int
    pass_rate: float


@dataclass
class ComplianceSummary:
    total_decisions: int
    total_checks: int
    overall_pass_rate: float
    by_rule: list[RuleCompliance]


def constitution_compliance_report(conn: sqlite3.Connection) -> ComplianceSummary:
    """Section 6: overall + per-rule PASS/FAIL/ESCALATED breakdown across
    every constitution_enforcement_events row recorded so far."""
    rows = conn.execute(
        "SELECT decision_id, rule_id, rule_name, check_result FROM constitution_enforcement_events"
    ).fetchall()

    by_rule: dict[tuple[str, str], dict[str, int]] = {}
    decision_ids: set[str] = set()
    for decision_id, rule_id, rule_name, check_result in rows:
        decision_ids.add(decision_id)
        key = (rule_id, rule_name)
        counts = by_rule.setdefault(key, {"PASS": 0, "FAIL": 0, "ESCALATED": 0})
        counts[check_result] += 1

    rule_reports = []
    for (rule_id, rule_name), counts in sorted(by_rule.items()):
        total = counts["PASS"] + counts["FAIL"] + counts["ESCALATED"]
        rule_reports.append(RuleCompliance(
            rule_id=rule_id, rule_name=rule_name,
            total_checks=total, pass_count=counts["PASS"],
            fail_count=counts["FAIL"], escalated_count=counts["ESCALATED"],
            pass_rate=counts["PASS"] / total if total else 0.0,
        ))

    total_checks = len(rows)
    total_pass = sum(r.pass_count for r in rule_reports)
    return ComplianceSummary(
        total_decisions=len(decision_ids),
        total_checks=total_checks,
        overall_pass_rate=total_pass / total_checks if total_checks else 0.0,
        by_rule=rule_reports,
    )
