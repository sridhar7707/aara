"""Trading Intelligence's own approval read model for the Decision Detail
panel -- narrower than sentinel_engine.queries.decision_query.ApprovalSummary.

Carries approval_id (restored -- Decision Detail Depth pass) alongside
status/approved_by/approved_at. Reuses ApprovalStatus (sentinel_engine.
governance.approval_status) rather than duplicating it, the same way
DecisionView/DecisionContract reuse DecisionState as the canonical
lifecycle vocabulary.

ApprovalStatus is imported (and therefore re-exported) here so that ui/
modules -- forbidden from importing sentinel_engine directly (see
applications/trading_intelligence/ui/tests/test_ui_structure.py) -- can
obtain it via this module instead, mirroring decision_view.py's own
re-export of DecisionState for the same reason.
"""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.governance.approval_status import ApprovalStatus


@dataclass(frozen=True)
class ApprovalEntry:
    approval_id: str
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime
