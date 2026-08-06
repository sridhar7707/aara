"""Admin API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "6. Admin Endpoints (Governance &
Monitoring)" (authoritative REST contract). Added during scaffold
expansion. Internal/Admin-only per PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md
Architectural Decision 3 (Tiered API Visibility) -- access control
enforcement is deferred to Phase 2B (no auth in Phase 2A), but the route
surface and response shape are frozen now.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/governance/rules")
def get_governance_rules() -> dict:
    """List active governance rules."""
    raise NotImplementedError


@router.get("/ledger-health")
def get_ledger_health() -> dict:
    """Chain integrity verification status per event ledger table."""
    raise NotImplementedError
