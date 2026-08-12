"""Translation boundary between the existing Phase-1A decision-write
path's decision_row and the Sentinel Engine Governance/Approval domain
contracts (ADR-014).

Takes plain data (the decision_row shape bot/trust_ledger/decisions.py's
write_decision_event() already produces), never a bot type, so this
module has zero import dependency on bot/. All fields are validated here
because this is a system boundary.

The adapter produces a `policy_id` string and, separately, an `Approval`
domain object -- plain data and an existing domain contract for a future
caller to pass to GovernanceService. It never calls GovernanceService,
never registers a Policy, and never persists anything.

Per ADR-014 Section 4, `to_policy_id()` returns an identifier only; this
module does not construct or register a `Policy` -- deciding an actual
Phase-1A policy's name/description/enabled state is separate, unauthorized
future governance work.

Per ADR-014 Section 5, the literal `approved_by` value for an autonomous
Phase-1A decision is deliberately NOT selected by this ADR. `to_approval()`
therefore requires both `status` and `approved_by` as caller-supplied
plain inputs -- mirroring the same boundary principle already established
for `decision_id`: identity and provenance cross the boundary as plain
data supplied by the caller, never invented by the adapter. The only
autonomous-provenance guarantee this module enforces is the one ADR-014
Section 5 states explicitly: `approved_by` must not reuse or conflict with
an existing Sentinel Engine human-role value.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus

# ADR-014 Section 5: existing Sentinel Engine `Approval.approved_by` values
# already in human-role use. An autonomous Approval must never reuse or
# conflict with these.
_HUMAN_ROLE_APPROVED_BY_VALUES = frozenset({"risk_officer", "cro"})


def to_policy_id(decision_row: dict) -> str:
    """ADR-014 Section 4: a deterministic policy_id identifier, derived
    only from existing decision_row data. This is an identifier only -- it
    does not register or imply the existence of any operational Policy."""
    if not isinstance(decision_row, dict):
        raise ValueError("decision_row must be a dict")
    if "action" not in decision_row:
        raise ValueError("decision_row missing required field: action")

    action = decision_row["action"]
    if not isinstance(action, str) or not action:
        raise ValueError("decision_row['action'] must be a non-empty string")

    return f"phase1a-{action.lower()}"


def to_approval(
    decision_row: dict,
    status: ApprovalStatus,
    approved_by: str,
    approval_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Approval:
    """ADR-014 Section 5: translates an existing decision_id, plus a
    caller-supplied governance verdict and provenance, into the Approval
    domain object.

    `status` is never inferred here -- the adapter must not invoke
    GovernanceService (ADR-014 Section 3), so the governance verdict must
    already have been produced by the caller.

    `approved_by` is never invented or defaulted here -- ADR-014 Section 5
    deliberately defers selection of the literal autonomous `approved_by`
    value, so the caller must supply it explicitly. This function rejects
    only the one concrete case ADR-014 Section 5 states explicitly: reuse
    of an existing Sentinel Engine human-role value.
    """
    if not isinstance(decision_row, dict):
        raise ValueError("decision_row must be a dict")
    if "decision_id" not in decision_row:
        raise ValueError("decision_row missing required field: decision_id")

    decision_id = decision_row["decision_id"]
    if not isinstance(decision_id, str) or not decision_id:
        raise ValueError("decision_row['decision_id'] must be a non-empty string")

    if not isinstance(status, ApprovalStatus):
        raise ValueError("status must be an ApprovalStatus")

    if not isinstance(approved_by, str) or not approved_by:
        raise ValueError("approved_by must be a non-empty string")
    if approved_by in _HUMAN_ROLE_APPROVED_BY_VALUES:
        raise ValueError(
            f"approved_by={approved_by!r} reuses an existing Sentinel Engine "
            "human-role value; ADR-014 Section 5 prohibits this for an "
            "autonomous Approval"
        )

    if approval_id is None:
        approval_id = str(uuid.uuid4())
    elif not isinstance(approval_id, str) or not approval_id:
        raise ValueError("approval_id must be a non-empty string")

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif not isinstance(timestamp, datetime):
        raise ValueError("timestamp must be a datetime instance")
    elif timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    return Approval(
        approval_id=approval_id,
        decision_id=decision_id,
        status=status,
        approved_by=approved_by,
        timestamp=timestamp,
    )
