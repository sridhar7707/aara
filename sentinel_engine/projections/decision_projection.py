"""Read-model contract representing a decision's current derived state."""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.domain.decision_state import DecisionState


@dataclass(frozen=True)
class DecisionProjection:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    evidence_reference: str
    risk_reference: str
    updated_at: datetime
