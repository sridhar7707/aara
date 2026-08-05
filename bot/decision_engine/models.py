from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class EvidenceItem:
    source: str
    signal: str
    value: float
    contribution: float
    timestamp: Optional[datetime] = None
