"""Evidence domain models (IMPLEMENTATION_HANDOFF.md, SYSTEM_DOMAIN_MODEL.md.v1.1_backup)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Evidence:
    evidence_id: str
    type: str
    provider: str
    version: str
    data_as_of: datetime
    recorded_at: datetime
    confidence: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceAssessment:
    """Derived analytical assessment. Never displayed as certainty or prediction."""

    score: int
    rationale: str
    provenance: dict[str, Any] = field(default_factory=dict)
