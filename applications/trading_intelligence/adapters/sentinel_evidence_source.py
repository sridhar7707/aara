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
"""
from typing import List

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
        return [
            EvidenceEntry(
                evidence_type=item.evidence_type,
                source=item.source,
                attached_at=item.attached_at,
            )
            for item in timeline.evidence
        ]
