from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from bot.decision_engine.decision_state import DecisionState


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    signal: str
    value: float
    contribution: float
    timestamp: Optional[datetime] = None


@dataclass
class DecisionResult:
    recommendation: str
    confidence: float
    evidence: List[EvidenceItem]
    explanation: str
    state: DecisionState
