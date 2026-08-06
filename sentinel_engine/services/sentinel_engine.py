"""Application boundary for the Sentinel Engine: coordinates DecisionService,
EvidenceService, and GovernanceService behind a single entry point the
existing bot can call.

Pure coordination only: no trading logic, no ML logic, no persistence
decisions. Depends only on already-constructed services (dependency
injection), never wires a storage backend itself.
"""
from typing import List, Optional

from sentinel_engine.domain.decision import Decision
from sentinel_engine.events.event import Event
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.policy import Policy
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService


class SentinelEngine:
    def __init__(
        self,
        decision_service: DecisionService,
        evidence_service: EvidenceService,
        governance_service: GovernanceService,
    ):
        self._decision_service = decision_service
        self._evidence_service = evidence_service
        self._governance_service = governance_service

    def create_decision(self, decision: Decision) -> Event:
        return self._decision_service.create_decision(decision)

    def get_decision_projection(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._decision_service.get_projection(decision_id)

    def attach_evidence(self, decision_id: str, evidence: Evidence) -> None:
        self._evidence_service.associate_evidence(decision_id, evidence)

    def get_evidence(self, decision_id: str) -> List[Evidence]:
        return self._evidence_service.get_evidence_for_decision(decision_id)

    def register_policy(self, policy: Policy) -> None:
        self._governance_service.register_policy(policy)

    def is_policy_enabled(self, policy_id: str) -> bool:
        return self._governance_service.is_policy_enabled(policy_id)

    def evaluate_policy(self, decision_id: str, policy_id: str) -> bool:
        return self._governance_service.evaluate_policy(decision_id, policy_id)

    def record_approval(self, approval: Approval) -> None:
        self._governance_service.record_approval(approval)

    def get_approval(self, decision_id: str) -> Optional[Approval]:
        return self._governance_service.get_approval(decision_id)
