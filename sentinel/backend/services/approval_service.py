"""ApprovalService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

Every approval is explicit; no auto-execute. Approval is separate from
dispatch/execution (Phase 2A does not implement execution).
"""

from sentinel.backend.domain.approval import Approval
from sentinel.backend.repositories.decision_repository import DecisionRepository


class ApprovalService:
    def __init__(self, decision_repository: DecisionRepository) -> None:
        self._decision_repository = decision_repository

    def approve(self, decision_id: str, *, approved_by: str, reason: str) -> Approval:
        raise NotImplementedError

    def defer(self, decision_id: str, *, deferred_by: str, reason: str) -> None:
        raise NotImplementedError

    def decline(self, decision_id: str, *, declined_by: str, reason: str) -> None:
        raise NotImplementedError

    def escalate(self, decision_id: str, *, escalated_by: str, reason: str) -> None:
        raise NotImplementedError
