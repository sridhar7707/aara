"""EventWriter (IMPLEMENTATION_HANDOFF.md: Event Ledger is Source of Truth).

All state changes are written as immutable events through this writer.
No direct database writes from UI or services. In Phase 2A the ledger
is not persisted to disk -- events remain in memory for the session
(IMPLEMENTATION_HANDOFF.md, Phase 2A Mock Boundary).
"""

from sentinel.backend.events.event import Event
from sentinel.backend.events.event_types import EventType


class EventWriter:
    """Writes immutable events. Phase 2A: in-memory only, no persistence."""

    def write(self, event_type: EventType, payload: dict) -> Event:
        raise NotImplementedError

    def read_stream(self, correlation_id: str) -> list[Event]:
        raise NotImplementedError
