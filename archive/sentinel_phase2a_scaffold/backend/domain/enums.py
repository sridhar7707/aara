"""Frozen enums for the Sentinel domain (IMPLEMENTATION_HANDOFF.md).

Source of truth: docs/architecture/IMPLEMENTATION_HANDOFF.md,
docs/architecture/GRADIO_IMPLEMENTATION_GUIDE.md.

RiskGovernorState is a 3-state machine (NORMAL/WARNING/DEFENSIVE).
Drawdown beyond DEFENSIVE's threshold is recorded as a Governance
Integrity BREACH event, not a fourth Risk Governor state.
"""

from enum import Enum


class DecisionState(Enum):
    IDENTIFIED = "IDENTIFIED"
    EVALUATED = "EVALUATED"
    GOVERNED = "GOVERNED"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    EXECUTED = "EXECUTED"
    REVIEWED = "REVIEWED"
    CLOSED = "CLOSED"


class RiskGovernorState(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    DEFENSIVE = "DEFENSIVE"


class GovernanceAction(Enum):
    APPROVE = "APPROVE_DECISION"
    DEFER = "DEFER_DECISION"
    DECLINE = "DECLINE_DECISION"
    ESCALATE = "ESCALATE_REVIEW"


class SentinelRole(Enum):
    """Placeholder enum. Not enforced in Phase 2A (no RBAC, no auth)."""

    INVESTOR = "INVESTOR"
    ADVISOR = "ADVISOR"
    RISK_OFFICER = "RISK_OFFICER"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    ADMINISTRATOR = "ADMINISTRATOR"


class OperationalMode(Enum):
    RESEARCH = "RESEARCH"
    PAPER = "PAPER"
    SUPERVISED = "SUPERVISED"
    GOVERNED_AUTOMATION = "GOVERNED_AUTOMATION"  # Future value; not implemented in Phase 2A
