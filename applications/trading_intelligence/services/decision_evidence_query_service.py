"""Evidence query boundary, kept separate from DecisionQueryService's own
narrow decision-view responsibility (get_decision_view/list_decision_views).

Evidence is a Decision Detail-only concern -- DecisionListArea never needs
it -- so folding it into DecisionQueryService would give every list-only
caller a dependency it never uses. Mirrors DecisionQueryService/DecisionSource's
own shape: accepts a future evidence source abstraction (EvidenceSource) via
constructor injection.
"""
from abc import ABC, abstractmethod
from typing import List

from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry


class EvidenceSource(ABC):
    @abstractmethod
    def get_evidence(self, decision_id: str) -> List[EvidenceEntry]:
        ...


class DecisionEvidenceQueryService:
    def __init__(self, source: EvidenceSource):
        self._source = source

    def get_evidence(self, decision_id: str) -> List[EvidenceEntry]:
        return self._source.get_evidence(decision_id)
