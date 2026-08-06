"""Decision API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "1. Decision Management" (authoritative
REST contract, per ARCHITECTURE_FREEZE_STATUS.md reconciliation). Path
prefix is unversioned to match that document's GET /api/decisions* routes.

IMPLEMENTATION_HANDOFF.md's GET /pending is Phase 2A workflow prioritization
(which reads matter first), not a contract addition -- kept here since it
has no other home and doesn't conflict with the frozen contract.

Gradio is the only client; this layer has zero domain logic of its own --
it delegates to services.
"""

from fastapi import APIRouter

from sentinel.backend.services.decision_service import DecisionService

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.get("/pending")
def get_pending_decisions() -> list[dict]:
    # Must stay registered before "/{decision_id}" -- otherwise Starlette
    # matches "/pending" to the decision_id path parameter instead.
    raise NotImplementedError


@router.get("")
def list_decisions(
    state: str | None = None,
    asset: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    quality_score_min: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List decisions with filtering. Backing view: decision_with_context."""
    raise NotImplementedError


@router.get("/{decision_id}")
def get_decision(decision_id: str) -> dict:
    """Decision detail with full context (evidence, governance, approval,
    lifecycle, quality, thesis). Backing views: decision_with_context,
    decision_evidence_trail, decision_governance_evaluations,
    decision_lifecycle_timeline, decision_quality_summary."""
    raise NotImplementedError


@router.get("/{decision_id}/timeline")
def get_decision_timeline(decision_id: str) -> dict:
    """Decision lifecycle timeline (investor-facing). Backing view:
    decision_lifecycle_timeline."""
    raise NotImplementedError
