"""Read-only GovernanceSource implementation backed by Sentinel Engine's own
DecisionQuery.

Mirrors SentinelEvidenceSource's own rationale exactly: wraps
sentinel_engine.queries.decision_query.DecisionQuery rather than duplicating
ledger-filtering/event-reconstruction logic, since DecisionQuery.
get_decision_timeline() already computes governance_evaluations and
approvals alongside evidence. Read-only: get_decision_timeline() never
appends events, never saves or advances a projection, never mutates
Sentinel Engine state -- see its own docstring/tests.

get_governance() and get_approvals() each independently translate
DecisionQuery infrastructure exceptions into TradingIntelligenceReadError
(contracts/read_error.py) -- DecisionQuery has no documented exception
contract, so a future persistent backend may raise anything. They call
get_decision_timeline() separately (not sharing one cached result), which is
what lets a caller see "governance failed but approvals succeeded" or vice
versa.
"""
from typing import List

from sentinel_engine.queries.decision_query import DecisionQuery

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.services.decision_governance_query_service import (
    GovernanceSource,
)


class SentinelGovernanceSource(GovernanceSource):
    def __init__(self, decision_query: DecisionQuery):
        self._decision_query = decision_query

    def get_governance(self, decision_id: str) -> List[GovernanceEntry]:
        try:
            timeline = self._decision_query.get_decision_timeline(decision_id)
        except Exception as exc:
            raise TradingIntelligenceReadError(
                f"Failed to read governance for decision {decision_id!r}."
            ) from exc
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
        try:
            timeline = self._decision_query.get_decision_timeline(decision_id)
        except Exception as exc:
            raise TradingIntelligenceReadError(
                f"Failed to read approvals for decision {decision_id!r}."
            ) from exc
        if timeline is None:
            return []
        return [
            ApprovalEntry(
                approval_id=item.approval_id,
                status=item.status,
                approved_by=item.approved_by,
                approved_at=item.approved_at,
            )
            for item in timeline.approvals
        ]
