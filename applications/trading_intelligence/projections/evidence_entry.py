"""Trading Intelligence's own evidence read model for the Decision Detail
panel -- narrower than sentinel_engine.queries.decision_query.EvidenceSummary.

Carries evidence_id (restored -- Decision Detail Depth pass) alongside
evidence_type/source/attached_at. Still never carries Evidence.data (the
arbitrary per-evidence-type payload attached at evidence-creation time);
rendering that free-form dict remains a separate, later decision, not part
of this slice.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: str
    evidence_type: str
    source: str
    attached_at: datetime
