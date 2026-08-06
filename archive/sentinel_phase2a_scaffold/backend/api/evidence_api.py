"""Evidence API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md GET /api/decisions/{decision_id}/evidence
(authoritative REST contract). Path prefix unversioned to match. Role-based
filtering per SENTINEL_DESIGN_SYSTEM_FINAL.md is applied in the service
layer, not here.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/decisions", tags=["evidence"])


@router.get("/{decision_id}/evidence")
def get_evidence_for_decision(decision_id: str) -> dict:
    """Response: {"decision_id": str, "evidence": list[dict]}, per
    API_REQUIREMENTS_v1.0.md lines 189-219 -- not a bare list."""
    raise NotImplementedError
