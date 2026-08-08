"""Domain contract for human/system approval state on a decision."""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.governance.approval_status import ApprovalStatus


@dataclass(frozen=True)
class Approval:
    approval_id: str
    decision_id: str
    status: ApprovalStatus
    approved_by: str
    timestamp: datetime
