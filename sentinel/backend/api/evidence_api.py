"""Evidence API adapter (FastAPI). Signatures only, no implementation.

Not among the 6 endpoints explicitly enumerated in
IMPLEMENTATION_HANDOFF.md, but evidence_api.py is named in the
repository tree; this is the natural home for evidence reads
(role-based filtering per SENTINEL_DESIGN_SYSTEM_FINAL.md is applied
in the service layer, not here).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/decisions", tags=["evidence"])


@router.get("/{decision_id}/evidence")
def get_evidence_for_decision(decision_id: str) -> list[dict]:
    raise NotImplementedError
