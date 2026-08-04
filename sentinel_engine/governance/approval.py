"""Domain contract for human/system approval state on a decision."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Approval:
    approval_id: str
    decision_id: str
    status: str
    approved_by: str
    timestamp: datetime
