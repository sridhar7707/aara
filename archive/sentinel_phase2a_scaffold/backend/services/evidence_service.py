"""EvidenceService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

Evidence is immutable after recording. Every artifact carries provider,
version, data-as-of, and recorded-at provenance.
"""

from sentinel.backend.domain.evidence import Evidence
from sentinel.backend.repositories.evidence_repository import EvidenceRepository


class EvidenceService:
    def __init__(self, evidence_repository: EvidenceRepository) -> None:
        self._evidence_repository = evidence_repository

    def record(self, evidence: Evidence) -> Evidence:
        raise NotImplementedError

    def get_by_decision(self, decision_id: str) -> list[Evidence]:
        raise NotImplementedError
