"""Read-only EvidenceSource implementation backed by Sentinel Engine's own
DecisionQuery.

Wraps sentinel_engine.queries.decision_query.DecisionQuery rather than
ProjectionRepository (SentinelProjectionDecisionSource's own dependency),
since evidence is never stored on DecisionProjection -- it only exists as
ledger events, and DecisionQuery is the read-side component that already
reconstructs it from them. Read-only: DecisionQuery.get_decision_timeline()
never appends events, never saves or advances a projection, never mutates
Sentinel Engine state -- see its own docstring/tests.

Deliberately does not key off Decision.evidence_reference: nothing in
Sentinel Engine looks up evidence by that string (EvidenceService and
DecisionQuery both key strictly by decision_id), so using it here would
just be decorative, not functional.

get_evidence() translates DecisionQuery infrastructure exceptions into
TradingIntelligenceReadError (contracts/read_error.py) -- DecisionQuery has
no documented exception contract, so a future persistent backend may raise
anything.

data (ADR-036) is sourced from timeline.events, not timeline.evidence --
EvidenceSummary deliberately stays narrow (unwidened), but DecisionTimeline
already exposes the full, unfiltered Event list, and each EVIDENCE_ATTACHED
event's own payload now carries "data" (sentinel_engine/services/
evidence_service.py). Mirrors SentinelAuditSource's existing pattern of
reading timeline.events directly rather than inventing a new query.
"""
from typing import Any, Dict, List

from sentinel_engine.events.event_types import EventType
from sentinel_engine.queries.decision_query import DecisionQuery

from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.services.decision_evidence_query_service import (
    EvidenceSource,
)


class SentinelEvidenceSource(EvidenceSource):
    def __init__(self, decision_query: DecisionQuery):
        self._decision_query = decision_query

    def get_evidence(self, decision_id: str) -> List[EvidenceEntry]:
        try:
            timeline = self._decision_query.get_decision_timeline(decision_id)
        except Exception as exc:
            raise TradingIntelligenceReadError(
                f"Failed to read evidence for decision {decision_id!r}."
            ) from exc
        if timeline is None:
            return []
        data_by_evidence_id = self._data_by_evidence_id(timeline.events)
        return [
            EvidenceEntry(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                source=item.source,
                attached_at=item.attached_at,
                data=data_by_evidence_id.get(item.evidence_id, {}),
            )
            for item in timeline.evidence
        ]

    @staticmethod
    def _data_by_evidence_id(events) -> Dict[str, Dict[str, Any]]:
        return {
            event.payload["evidence_id"]: event.payload.get("data", {})
            for event in events
            if event.event_type == EventType.EVIDENCE_ATTACHED
        }
