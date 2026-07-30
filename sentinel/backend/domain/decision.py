"""Decision aggregate root (IMPLEMENTATION_HANDOFF.md, SYSTEM_DOMAIN_MODEL.md.v1.1_backup).

Decision is the primary domain object. Not trades, not tickers, not signals.
"""

from dataclasses import dataclass
from datetime import datetime

from sentinel.backend.domain.enums import DecisionState
from sentinel.backend.domain.evidence import EvidenceAssessment


@dataclass
class Decision:
    decision_id: str
    asset: str
    action: str
    proposed_allocation: float
    evidence_assessment: EvidenceAssessment
    thesis: str
    status: DecisionState
    created_at: datetime
