"""DecisionService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

All calculations happen here, not in Gradio callbacks. Depends on
repositories only (never on the frontend).
"""

from sentinel.backend.domain.decision import Decision
from sentinel.backend.repositories.decision_repository import DecisionRepository


class DecisionService:
    def __init__(self, decision_repository: DecisionRepository) -> None:
        self._decision_repository = decision_repository

    def create(self, *, asset: str, action: str, proposed_allocation: float, thesis: str) -> Decision:
        raise NotImplementedError

    def get(self, decision_id: str) -> Decision:
        raise NotImplementedError

    def get_pending(self) -> list[Decision]:
        raise NotImplementedError
