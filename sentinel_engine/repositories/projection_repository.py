"""Repository abstraction for DecisionProjection read models.

No concrete backend lives here. Adapters (SQLite, in-memory, etc.)
implement this interface in a later migration phase.
"""
from abc import ABC, abstractmethod
from typing import Optional

from sentinel_engine.projections.decision_projection import DecisionProjection


class ProjectionRepository(ABC):
    @abstractmethod
    def save(self, projection: DecisionProjection) -> None:
        ...

    @abstractmethod
    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        ...
