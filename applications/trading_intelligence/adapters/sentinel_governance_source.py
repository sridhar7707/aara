"""Read-only GovernanceSource implementation backed by Sentinel Engine's own
DecisionQuery.

Mirrors SentinelEvidenceSource's own rationale exactly: wraps
sentinel_engine.queries.decision_query.DecisionQuery rather than duplicating
ledger-filtering/event-reconstruction logic, since DecisionQuery.
get_decision_timeline() already computes governance_evaluations and
approvals alongside evidence. Read-only: get_decision_timeline() never
appends events, never saves or advances a projection, never mutates
Sentinel Engine state -- see its own docstring/tests.
"""
from typing import List

from sentinel_engine.queries.decision_query import DecisionQuery

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.services.decision_governance_query_service import (
    GovernanceSource,
)


class SentinelGovernanceSource(GovernanceSource):
    def __init__(self, decision_query: DecisionQuery):
        self._decision_query = decision_query

    def get_governance(self, decision_id: str) -> List[GovernanceEntry]:
        timeline = self._decision_query.get_decision_timeline(decision_id)
        if timeline is None:
            return []
        return [
            GovernanceEntry(
                policy_id=item.policy_id,
                enabled=item.enabled,
                evaluated_at=item.evaluated_at,
            )
            for item in timeline.governance_evaluations
        ]

    def get_approvals(self, decision_id: str) -> List[ApprovalEntry]:
        timeline = self._decision_query.get_decision_timeline(decision_id)
        if timeline is None:
            return []
        return [
            ApprovalEntry(
                status=item.status,
                approved_by=item.approved_by,
                approved_at=item.approved_at,
            )
            for item in timeline.approvals
        ]
