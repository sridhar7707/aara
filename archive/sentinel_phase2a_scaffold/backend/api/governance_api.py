"""Governance API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "3. Governance & Compliance"
(authoritative REST contract). Path prefix unversioned to match
/api/governance/evaluations/{decision_id}.

GET /state is IMPLEMENTATION_HANDOFF.md's Phase 2A workflow prioritization
pick (not in the frozen contract) -- kept, unversioned for consistency with
its sibling in this router. Governance/Risk Governor state is
portfolio-wide, not decision-scoped, so it stays out of decision_api.py.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/governance", tags=["governance"])


@router.get("/state")
def get_governance_state() -> dict:
    """Risk Governor state (3-state: NORMAL/WARNING/DEFENSIVE) + drawdown + buffer."""
    raise NotImplementedError


@router.get("/evaluations/{decision_id}")
def get_governance_evaluations(decision_id: str) -> dict:
    """Governance audit trail for a decision, including escalations.
    Backing view: decision_governance_evaluations."""
    raise NotImplementedError
