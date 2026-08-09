"""Trading Intelligence's own evidence read model for the Decision Detail
panel -- narrower than sentinel_engine.queries.decision_query.EvidenceSummary.

Deliberately excludes evidence_id (an internal identifier the Detail panel
has no use for -- nothing in this slice looks anything up by it) and never
carries Evidence.data (the arbitrary per-evidence-type payload attached at
evidence-creation time); rendering that free-form dict is a separate,
later decision, not part of this slice.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_type: str
    source: str
    attached_at: datetime
