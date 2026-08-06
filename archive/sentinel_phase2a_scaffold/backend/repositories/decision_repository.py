"""DecisionRepository interface (IMPLEMENTATION_HANDOFF.md: Phase 2A Mock Boundary).

Repository interfaces must exist; concrete database implementations
must not be created in Phase 2A. Services depend on repositories, not
the reverse.
"""

from sentinel.backend.domain.decision import Decision


class DecisionRepository:
    def add(self, decision: Decision) -> None:
        raise NotImplementedError

    def get(self, decision_id: str) -> Decision:
        raise NotImplementedError

    def get_pending(self) -> list[Decision]:
        raise NotImplementedError
