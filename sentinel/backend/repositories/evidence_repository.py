"""EvidenceRepository interface (IMPLEMENTATION_HANDOFF.md: Phase 2A Mock Boundary).

No concrete database implementation in Phase 2A; backs onto an
in-memory mock repository for the session.
"""

from sentinel.backend.domain.evidence import Evidence


class EvidenceRepository:
    def add(self, evidence: Evidence) -> None:
        raise NotImplementedError

    def get_by_decision(self, decision_id: str) -> list[Evidence]:
        raise NotImplementedError
