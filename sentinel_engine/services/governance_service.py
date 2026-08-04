"""Governance workflow boundary: registers Policy contracts and records
Approval contracts. No trading rules or policy evaluation logic live here.

In-memory only: no repository, no persistence. Internal storage is private
and never handed out by reference. Policy/Approval are frozen dataclasses,
so returning a stored instance is already an immutable view.
"""
from typing import Dict, Optional

from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval


class GovernanceService:
    def __init__(self):
        self._policies: Dict[str, Policy] = {}
        self._approvals: Dict[str, Approval] = {}

    def register_policy(self, policy: Policy) -> None:
        self._policies[policy.policy_id] = policy

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def is_policy_enabled(self, policy_id: str) -> bool:
        policy = self._policies.get(policy_id)
        return policy.enabled if policy is not None else False

    def record_approval(self, approval: Approval) -> None:
        self._approvals[approval.decision_id] = approval

    def get_approval(self, decision_id: str) -> Optional[Approval]:
        return self._approvals.get(decision_id)
