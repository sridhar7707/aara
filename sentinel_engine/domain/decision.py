"""Domain contract for an investment decision, owned by Sentinel governance/audit."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Decision:
    decision_id: str
    symbol: str
    action: str
    timestamp: datetime
    confidence: float
    evidence_reference: str
    risk_reference: str
