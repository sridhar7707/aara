"""Portfolio API adapter (FastAPI). Signatures only, no implementation.

IMPLEMENTATION_HANDOFF.md endpoint: GET /api/v1/portfolio/health

Not in the handoff doc's repository tree, added for the same reason as
governance_api.py -- no other file in the given tree fits.
Phase 2A: mock/simulated portfolio data only, no real broker state.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/health")
def get_portfolio_health() -> dict:
    raise NotImplementedError
