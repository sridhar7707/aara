"""Domain contract for evidence supporting an investment decision."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    evidence_type: str
    source: str
    data: Dict[str, Any]
    collected_at: datetime
