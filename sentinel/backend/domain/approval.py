"""Approval domain model (IMPLEMENTATION_HANDOFF.md).

Every approval is explicit. No auto-execute. Approval is the end of the
governance workflow in Phase 2A -- it is separate from dispatch/execution.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Approval:
    approved_by: str
    approved_at: datetime
    reason: str
