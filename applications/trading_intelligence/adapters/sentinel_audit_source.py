"""Read-only audit-trail source backed by Sentinel Engine's own
DecisionQuery.

Mirrors SentinelEvidenceSource's own rationale exactly: wraps
sentinel_engine.queries.decision_query.DecisionQuery rather than
duplicating ledger-filtering/event-reconstruction logic, since
DecisionQuery.get_decision_timeline() already computes the decision's
events, already sorted by created_at -- see its own docstring/tests.
Read-only: get_decision_timeline() never appends events, never saves or
advances a projection, never mutates Sentinel Engine state.

get_audit_trail() translates DecisionQuery infrastructure exceptions into
TradingIntelligenceReadError (contracts/read_error.py) -- DecisionQuery has
no documented exception contract, so a future persistent backend may raise
anything.
"""
from typing import List

from sentinel_engine.queries.decision_query import DecisionQuery

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.audit_entry import AuditEntry


class SentinelAuditSource:
    def __init__(self, decision_query: DecisionQuery):
        self._decision_query = decision_query

    def get_audit_trail(self, decision_id: str) -> List[AuditEntry]:
        try:
            timeline = self._decision_query.get_decision_timeline(decision_id)
        except Exception as exc:
            raise TradingIntelligenceReadError(
                f"Failed to read audit trail for decision {decision_id!r}."
            ) from exc
        if timeline is None:
            return []
        return [
            AuditEntry(
                event_id=event.event_id,
                event_type=event.event_type,
                created_at=event.created_at,
                payload=event.payload,
            )
            for event in timeline.events
        ]
