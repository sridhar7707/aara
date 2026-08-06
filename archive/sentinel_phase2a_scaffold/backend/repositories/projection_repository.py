"""ProjectionRepository interface (IMPLEMENTATION_HANDOFF.md: Derived Views Only).

Frontend never displays raw ledger state. This repository serves
pre-calculated read-model projections only (DERIVED_STATE_VIEWS_v1.2.md).
"""

from typing import Any


class ProjectionRepository:
    def get_decision_view(self, decision_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_portfolio_health(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_risk_state(self) -> dict[str, Any]:
        raise NotImplementedError
