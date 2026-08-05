from datetime import datetime
from typing import Optional

from bot.decision_engine.models import EvidenceItem


def create_evidence_item(
    source: str,
    signal: str,
    value: float,
    contribution: float,
    timestamp: Optional[datetime] = None,
) -> EvidenceItem:
    return EvidenceItem(
        source=source,
        signal=signal,
        value=float(value),
        contribution=float(contribution),
        timestamp=timestamp,
    )
