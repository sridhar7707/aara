"""Trading Intelligence's own audit-trail read model for the Decision Detail
panel -- narrower than sentinel_engine.events.event.Event.

Carries event_id and payload (restored -- Decision Detail Depth pass)
alongside event_type/created_at. payload is the same arbitrary per-event-
type dict Event itself carries (e.g. evidence_id/evidence_type/source for
EVIDENCE_ATTACHED, policy_id/enabled for GOVERNANCE_EVALUATED, approval_id/
status/approved_by for APPROVAL_RECORDED, symbol/action for
DECISION_CREATED) -- rendered as-is, never transformed or invented, by the
Audit Trail's expandable per-event detail view (gradio_view.py's
_format_audit_detail_html). Still distinct from Evidence.data (the
per-evidence-type payload EvidenceEntry itself never carries) -- that
remains a separate, later decision.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


@dataclass(frozen=True)
class AuditEntry:
    event_id: str
    event_type: str
    created_at: datetime
    payload: Dict[str, Any]
