"""Trading Intelligence's own evidence read model for the Decision Detail
panel -- narrower than sentinel_engine.queries.decision_query.EvidenceSummary.

Carries evidence_id (restored -- Decision Detail Depth pass) alongside
evidence_type/source/attached_at. Also carries data (ADR-036) -- the
free-form per-evidence-type payload attached at evidence-creation time,
sourced from the EVIDENCE_ATTACHED event's own payload, not from
EvidenceSummary. Defaults to {} so events predating ADR-036, or a missing
"data" key, produce a valid entry rather than an error. Rendering data in
the UI remains a separate, later decision, not part of this slice.

polarity (ADR-070, Sprint 3) carries the EVIDENCE_ATTACHED event payload's
own polarity value verbatim -- "SUPPORTING", "CONTRADICTING", or None
(events predating ADR-068 B1, a missing "polarity" key, or B1's own HOLD /
unrecognised-signal outcome). One record's value only; never aggregated,
counted, netted, scored, or combined with any other record's, and never
inferred from signal/confidence/metadata/source. Batch 1 read-model
plumbing only; the Decision Center polarity labels are Batch 2.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: str
    evidence_type: str
    source: str
    attached_at: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    polarity: Optional[str] = None
