"""Phase 1A Sprint 3 -- decision_events writer.

Every BUY/SELL/HOLD/REJECT a symbol reaches in a cycle writes exactly one
decision_events row, referencing that day's candidate_evaluation_events row
(bot.trust_ledger.candidates.get_todays_candidate_event_id) and the active
deployment_manifest_id. HOLD/REJECT use event_type=QUALIFIED_REJECTION;
BUY/SELL that actually execute use event_type=EXECUTED
(phase1a_requirements.md Section 12c).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import ledger.ledger as ledger_svc
from bot.trust_ledger.ids import new_decision_id

_PRIMARY_INTENT = {
    "BUY": "OPPORTUNITY_ENTRY",
    "SELL": "RISK_MANAGEMENT_EXIT",
    "HOLD": "NO_ACTION",
    "REJECT": "NO_ACTION",
}


class DuplicateDecisionError(Exception):
    """Raised by check_fingerprint when an EXECUTED BUY/SELL would duplicate
    an already-OPEN decision for the same (asset, action) without an
    explicit override_reason."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_intent(
    action: str, contributing_modules: list[str] | None = None,
    override_reason: str | None = None,
    thesis: str | None = None, invalidation_point: str | None = None,
    expected_return_basis_points: float | None = None,
) -> dict:
    """thesis/invalidation_point/expected_return_basis_points back
    TRADING_CONSTITUTION.md Rule 3 (Trade Structure Requirement) -- an
    OPPORTUNITY_ENTRY (BUY) states why, when it's wrong, and what it
    expects. Deliberately optional: a RISK_MANAGEMENT_EXIT (SELL) doesn't
    get a new thesis -- it's the invalidation point of the original BUY's
    thesis firing, not a fresh position -- and NO_ACTION (HOLD/REJECT)
    never opens risk at all. See bot/trust_ledger/constitution.py's Rule 3
    check, which scopes the requirement to BUY accordingly."""
    intent = {
        "primary_intent": _PRIMARY_INTENT.get(action, "NO_ACTION"),
        "contributing_modules": contributing_modules or [],
    }
    if override_reason:
        intent["override_reason"] = override_reason
    if thesis:
        intent["thesis"] = thesis
    if invalidation_point:
        intent["invalidation_point"] = invalidation_point
    if expected_return_basis_points is not None:
        intent["expected_return_basis_points"] = expected_return_basis_points
    return intent


def build_data_completeness(
    lstm_is_degraded: bool = False,
    sentiment_available: bool = True,
    vix_available: bool = True,
) -> dict:
    missing_inputs: list[str] = []
    stale_inputs: list[str] = []
    if lstm_is_degraded:
        stale_inputs.append("lstm")
    if not sentiment_available:
        missing_inputs.append("finbert")
    if not vix_available:
        missing_inputs.append("vix")
    status = "COMPLETE" if not missing_inputs and not stale_inputs else "DEGRADED"
    return {"status": status, "missing_inputs": missing_inputs, "stale_inputs": stale_inputs}


def check_fingerprint(
    conn: sqlite3.Connection, asset: str, action: str, override_reason: str | None = None,
) -> None:
    """Idempotency guard for EXECUTED BUY/SELL writes only (never called for
    QUALIFIED_REJECTION -- those aren't capital-committing and legitimately
    recur every cycle). Raises DuplicateDecisionError if an EXECUTED
    decision for this (asset, action) is still OPEN -- i.e. no matching
    decision_outcome_events row yet, meaning we're already holding a
    position from an earlier entry today. A CLOSED prior decision (already
    exited) does not block a new one -- that's a legitimate same-day
    re-entry, per phase1a_requirements.md Section 12's own example.

    Simplification vs. the doc's literal "asset + strategy_version_id +
    direction" fingerprint: strategy_version_id is dropped from the filter.
    In current single-manifest-at-a-time operation there is exactly one
    active strategy_version_id at any moment, so filtering by asset+action
    alone is equivalent in practice -- and using decision_state (OPEN/
    CLOSED) instead of a synthetic time-window is what actually
    distinguishes "still holding, this is a duplicate" from "already
    closed, this is a legitimate re-entry," matching the doc's own examples
    exactly rather than approximating them with day-granularity."""
    if override_reason:
        return
    row = conn.execute(
        "SELECT decision_id FROM decision_events "
        "WHERE asset=? AND action=? AND event_type='EXECUTED' "
        "ORDER BY sequence_number DESC LIMIT 1",
        (asset, action),
    ).fetchone()
    if not row:
        return
    state = conn.execute(
        "SELECT outcome_state FROM decision_state WHERE decision_id=?", (row[0],)
    ).fetchone()
    if state and state[0] == "OPEN":
        raise DuplicateDecisionError(
            f"{asset}: an EXECUTED {action} decision ({row[0]}) is still OPEN -- "
            "pass override_reason to force a duplicate entry."
        )


def write_decision_event(
    conn: sqlite3.Connection,
    candidate_event_id: str,
    asset: str,
    action: str,
    event_type: str,
    portfolio_snapshot: dict,
    market_context: dict,
    model_outputs: dict,
    risk_checks: dict,
    final_confidence: float,
    deployment_manifest_id: str,
    intent: dict,
    data_completeness: dict,
    timestamp: str | None = None,
) -> dict:
    return ledger_svc.append_ledger_row(conn, "decision_events", {
        "decision_id": new_decision_id(asset),
        "candidate_event_id": candidate_event_id,
        "timestamp": timestamp or _utc_now(),
        "asset": asset,
        "action": action,
        "event_type": event_type,
        "portfolio_snapshot": portfolio_snapshot,
        "market_context": market_context,
        "model_outputs": model_outputs,
        "risk_checks": risk_checks,
        "final_confidence": final_confidence,
        "deployment_manifest_id": deployment_manifest_id,
        "intent": intent,
        "data_completeness": data_completeness,
    })
