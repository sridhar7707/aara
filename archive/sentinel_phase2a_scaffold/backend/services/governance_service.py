"""GovernanceService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

Governance rules are checkpoints, not suggestions. Evaluates a Decision
against the current policy version; exceptions escalate, they never
bypass.
"""

from sentinel.backend.domain.decision import Decision
from sentinel.backend.domain.governance import Governance
from sentinel.backend.repositories.decision_repository import DecisionRepository


class GovernanceService:
    def __init__(self, decision_repository: DecisionRepository) -> None:
        self._decision_repository = decision_repository

    def evaluate(self, decision: Decision) -> Governance:
        raise NotImplementedError

    def get_policy_version(self) -> str:
        raise NotImplementedError
