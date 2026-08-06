"""Base immutable event shape (SYSTEM_EVENT_MODEL_v1.2.md, Universal Event Metadata).

All Sentinel events carry this metadata regardless of event type. No
direct database writes from UI; events are written only through
EventWriter (event_writer.py).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    timestamp: str  # ISO 8601 UTC
    event_version: int
    schema_version: str
    created_by: str
    created_source: str
    record_hash: str
    previous_record_hash: str
    correlation_id: str | None = None
    causation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
