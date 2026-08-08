"""Repository abstraction for DecisionProjection read models.

No concrete backend lives here. Adapters (SQLite, in-memory, etc.)
implement this interface in a later migration phase.
"""
from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime
from typing import Optional

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection


class ProjectionRepository(ABC):
    @abstractmethod
    def save(self, projection: DecisionProjection) -> None:
        ...

    @abstractmethod
    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        ...

    def advance_status(self, decision_id: str, status: DecisionState, updated_at: datetime) -> None:
        """Advance an existing projection's status; no-op if none exists.

        Concrete on this ABC (built on the abstract get/save primitives every
        subclass already implements) so lifecycle-step services can advance a
        projection's status without reading, constructing, or saving a
        DecisionProjection themselves.
        """
        existing = self.get(decision_id)
        if existing is None:
            return
        self.save(replace(existing, status=status, updated_at=updated_at))
