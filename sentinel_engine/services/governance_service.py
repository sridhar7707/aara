"""Governance workflow boundary: registers Policy contracts, evaluates a
policy against a decision, and records Approval contracts. No trading rules
live here — only the governance slice of the decision lifecycle.

Policy/approval state stays in-memory and private. evaluate_policy() emits a
GOVERNANCE_EVALUATED domain event through LedgerRepository and advances the
decision's projection only through ProjectionRepository.advance_status() —
this service never constructs, mutates, or saves a DecisionProjection
itself, mirroring the boundary established for EvidenceService.
"""
import uuid
from datetime import datetime
from typing import Dict, Optional

from sentinel_engine.events.event import Event
from sentinel_engine.events.event_types import EventType
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class GovernanceService:
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        projection_repository: ProjectionRepository,
    ):
        self._policies: Dict[str, Policy] = {}
        self._approvals: Dict[str, Approval] = {}
        self._ledger_repository = ledger_repository
        self._projection_repository = projection_repository

    def register_policy(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def is_policy_enabled(self, policy_id: str) -> bool:
        policy = self._policies.get(policy_id)
        return policy.enabled if policy is not None else False

    def evaluate_policy(self, decision_id: str, policy_id: str) -> bool:
        enabled = self.is_policy_enabled(policy_id)

        evaluated_at = datetime.utcnow()
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.GOVERNANCE_EVALUATED,
            created_at=evaluated_at,
            payload={
                "decision_id": decision_id,
                "policy_id": policy_id,
                "enabled": enabled,
            },
        )
        self._ledger_repository.save_event(event)

        self._projection_repository.advance_status(
            decision_id, EventType.GOVERNANCE_EVALUATED.value, evaluated_at,
        )

        return enabled

    def record_approval(self, approval: Approval) -> None:
        self._approvals[approval.decision_id] = approval

    def get_approval(self, decision_id: str) -> Optional[Approval]:
        return self._approvals.get(decision_id)
