"""Portfolio API adapter (FastAPI). Signatures only, no implementation.

Contract: API_REQUIREMENTS_v1.0.md "2. Portfolio Management" (authoritative
REST contract). Path prefix unversioned to match /api/portfolio/positions
and /api/portfolio/tax-analysis.

GET /health is IMPLEMENTATION_HANDOFF.md's Phase 2A workflow prioritization
pick (not in the frozen contract) -- kept, unversioned for consistency with
its siblings in this router.

Phase 2A: mock/simulated portfolio data only, no real broker state.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/health")
def get_portfolio_health() -> dict:
    raise NotImplementedError


@router.get("/positions")
def get_portfolio_positions() -> dict:
    """Current positions with tax lots. Backing view: position_lots_current."""
    raise NotImplementedError


@router.get("/tax-analysis")
def get_tax_analysis() -> dict:
    """Tax planning dashboard (harvestable losses, wash-sale risk,
    recommendations). Backing view: tax_impact_summary. Tax logic is
    computed upstream by the Tax Classification Service, not this view
    (PHASE_2A_ARCHITECTURE_FREEZE_ADDENDUM.md, Decision 1)."""
    raise NotImplementedError
