"""Governance/approval query boundary, kept separate from
DecisionQueryService's decision-view responsibility and from
DecisionEvidenceQueryService's evidence-only responsibility -- Decision
Detail-only concerns that DecisionListArea never needs, mirroring
DecisionEvidenceQueryService's own rationale for staying out of
DecisionQueryService. Accepts a future governance source abstraction
(GovernanceSource) via constructor injection, matching DecisionQueryService/
DecisionEvidenceQueryService's own shape.
"""
from abc import ABC, abstractmethod
from typing import List

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry


class GovernanceSource(ABC):
    @abstractmethod
    def get_governance(self, decision_id: str) -> List[GovernanceEntry]:
        ...

    @abstractmethod
    def get_approvals(self, decision_id: str) -> List[ApprovalEntry]:
        ...


class DecisionGovernanceQueryService:
    def __init__(self, source: GovernanceSource):
        self._source = source

    def get_governance(self, decision_id: str) -> List[GovernanceEntry]:
        return self._source.get_governance(decision_id)

    def get_approvals(self, decision_id: str) -> List[ApprovalEntry]:
        return self._source.get_approvals(decision_id)
