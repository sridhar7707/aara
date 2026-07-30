"""Decision API adapter (FastAPI). Signatures only, no implementation.

IMPLEMENTATION_HANDOFF.md endpoint: GET /api/v1/decisions/{id}
Gradio is the only client; this layer has zero domain logic of its
own -- it delegates to services.
"""

from fastapi import APIRouter

from sentinel.backend.services.decision_service import DecisionService

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.get("/pending")
def get_pending_decisions() -> list[dict]:
    # Must stay registered before "/{decision_id}" -- otherwise Starlette
    # matches "/pending" to the decision_id path parameter instead.
    raise NotImplementedError


@router.get("/{decision_id}")
def get_decision(decision_id: str) -> dict:
    """Return the decision projection view. See DERIVED_STATE_VIEWS_v1.2.md."""
    raise NotImplementedError
