"""Associates Evidence objects with decisions, kept separate from Decision
domain logic (only decision_id references cross the boundary).

In-memory only: no repository, no persistence. Internal storage is private
and never handed out by reference.
"""
from typing import Dict, List

from sentinel_engine.evidence.evidence import Evidence


class EvidenceService:
    def __init__(self):
        self._evidence_by_decision: Dict[str, List[Evidence]] = {}

    def associate_evidence(self, decision_id: str, evidence: Evidence) -> None:
        self._evidence_by_decision.setdefault(decision_id, []).append(evidence)

    def get_evidence_for_decision(self, decision_id: str) -> List[Evidence]:
        return list(self._evidence_by_decision.get(decision_id, []))
