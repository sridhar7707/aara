"""Governance API adapter (FastAPI). Signatures only, no implementation.

IMPLEMENTATION_HANDOFF.md endpoint: GET /api/v1/governance/state

Not in the handoff doc's repository tree (which lists only
decision_api.py, evidence_api.py, approval_api.py under api/), but the
endpoint has no other home -- added as governance_api.py rather than
folding it into decision_api.py, since governance/Risk Governor state
is portfolio-wide, not decision-scoped.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/governance", tags=["governance"])


@router.get("/state")
def get_governance_state() -> dict:
    """Risk Governor state (3-state: NORMAL/WARNING/DEFENSIVE) + drawdown + buffer."""
    raise NotImplementedError
