"""Phase 1B scaffolding (phase1b_requirements.md Section 5): Trust Scorecard
governance-gate assembly.

Not wired into any dashboard, cron job, or bot pipeline -- see
analytics/calibration.py's module docstring for the same gating note.

Implements only the "Evidence Collection" section and the four Governance
Gates that phase1b_requirements.md v1.2 actually scopes to Phase 1B (see that
doc's Section 5 note on Shadow Investor Mode moving to Phase 3, which removed
gate 5/the old gate 6 here). Reuses ledger.integrity.run_integrity_check for
hash-chain/pointer verification and ledger.reproducibility for reconstruction
sampling rather than reimplementing either.

Deliberately NOT implemented here: Model Performance, Operational Maturity,
Capital Safety, Confidence Level, and Capital Progression Recommendation
(the rest of phase1b_requirements.md's illustrative Section 5 scorecard).
Those need a portfolio-level equity curve (Sharpe ratio, max drawdown), a
black-swan replay, and human capital-scaling judgment calls -- none of which
this module can compute correctly from decision-level ledger rows alone, and
guessing the shape now would risk a same-named-but-wrong metric (the same
reasoning analytics/regime_views.py already applied to omitting its own
max-drawdown column).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ledger.integrity import run_integrity_check
from ledger.reproducibility import acceptance_test_fr_0_10

from analytics.compliance import ComplianceSummary, constitution_compliance_report

_CONSTITUTION_PASS_THRESHOLD = 0.95


@dataclass
class EvidenceCollection:
    decisions_collected: int
    outcomes_recorded: int
    reproducibility_sampled: int
    reproducibility_failures: list[str]
    hash_chain_broken_count: int


@dataclass
class GovernanceGates:
    constitution_compliance_pass: bool    # Gate 1: overall pass rate >= 95%
    reproducibility_pass: bool            # Gate 2: 100% of sampled decisions reconstructible
    ledger_integrity_pass: bool           # Gate 3: zero broken chains, no active-pointer drift
    risk_controls_active: bool            # Gate 4: Risk Governor has logged at least one state


@dataclass
class TrustScorecard:
    evidence: EvidenceCollection
    compliance: ComplianceSummary
    gates: GovernanceGates
    all_governance_gates_pass: bool


def _sample_reproducibility(conn: sqlite3.Connection, sample_size: int) -> tuple[int, list[str]]:
    rows = conn.execute(
        "SELECT decision_id FROM decision_events WHERE event_type = 'EXECUTED' "
        "ORDER BY sequence_number DESC LIMIT ?",
        (sample_size,),
    ).fetchall()
    failures = []
    for (decision_id,) in rows:
        try:
            acceptance_test_fr_0_10(conn, decision_id)
        except Exception as e:
            failures.append(f"{decision_id}: {e}")
    return len(rows), failures


def generate_scorecard(conn: sqlite3.Connection, reproducibility_sample_size: int = 5) -> TrustScorecard:
    decisions_collected = conn.execute(
        "SELECT COUNT(*) FROM decision_events WHERE event_type = 'EXECUTED'"
    ).fetchone()[0]
    outcomes_recorded = conn.execute("SELECT COUNT(*) FROM decision_outcome_events").fetchone()[0]

    integrity_result = run_integrity_check(conn)
    broken_count = sum(len(breaks) for breaks in integrity_result["broken_chains"].values())
    ledger_integrity_pass = broken_count == 0 and not integrity_result["pointer_drift"]

    sampled, failures = _sample_reproducibility(conn, reproducibility_sample_size)
    reproducibility_pass = sampled > 0 and not failures

    compliance = constitution_compliance_report(conn)
    constitution_compliance_pass = compliance.overall_pass_rate >= _CONSTITUTION_PASS_THRESHOLD

    risk_controls_active = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM risk_evaluation_events)"
    ).fetchone()[0] == 1

    gates = GovernanceGates(
        constitution_compliance_pass=constitution_compliance_pass,
        reproducibility_pass=reproducibility_pass,
        ledger_integrity_pass=ledger_integrity_pass,
        risk_controls_active=risk_controls_active,
    )

    return TrustScorecard(
        evidence=EvidenceCollection(
            decisions_collected=decisions_collected,
            outcomes_recorded=outcomes_recorded,
            reproducibility_sampled=sampled,
            reproducibility_failures=failures,
            hash_chain_broken_count=broken_count,
        ),
        compliance=compliance,
        gates=gates,
        all_governance_gates_pass=all((
            gates.constitution_compliance_pass,
            gates.reproducibility_pass,
            gates.ledger_integrity_pass,
            gates.risk_controls_active,
        )),
    )
