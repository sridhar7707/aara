"""Trading Intelligence's own audit-trail read model for the Decision Detail
panel -- narrower than sentinel_engine.events.event.Event.

Deliberately excludes event_id (an internal identifier the Detail panel has
no use for, mirroring EvidenceEntry's exclusion of evidence_id) and payload
(the arbitrary per-event-type dict, mirroring EvidenceEntry's exclusion of
Evidence.data -- rendering that free-form data is a separate, later
decision, not part of this slice).
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditEntry:
    event_type: str
    created_at: datetime
