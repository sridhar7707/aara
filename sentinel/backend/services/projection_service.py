"""ProjectionService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

Not listed in the handoff doc's repository tree under services/, but
explicitly specified as a service interface to generate -- added here
since projections/ holds read-model queries, not the service facade
that composes them for the API layer.

Frontend displays projection views only, never raw ledger state.
"""

from typing import Any

from sentinel.backend.repositories.projection_repository import ProjectionRepository


class ProjectionService:
    def __init__(self, projection_repository: ProjectionRepository) -> None:
        self._projection_repository = projection_repository

    def get_decision_view(self, decision_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_portfolio_health(self) -> dict[str, Any]:
        raise NotImplementedError
