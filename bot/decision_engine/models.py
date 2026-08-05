from dataclasses import dataclass
from typing import List

from bot.decision_engine.decision_state import DecisionState


@dataclass
class EvidenceItem:
    source: str
    signal: str
    value: float
    contribution: float


@dataclass
class DecisionResult:
    recommendation: str
    confidence: float
    evidence: List[EvidenceItem]
    explanation: str
    state: DecisionState
