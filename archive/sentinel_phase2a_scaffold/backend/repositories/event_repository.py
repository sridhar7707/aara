"""EventRepository interface (IMPLEMENTATION_HANDOFF.md: Phase 2A Mock Boundary).

Event ledger schema exists but is not written to disk in Phase 2A;
events remain in memory for the session.
"""

from sentinel.backend.events.event import Event


class EventRepository:
    def append(self, event: Event) -> None:
        raise NotImplementedError

    def read_stream(self, correlation_id: str) -> list[Event]:
        raise NotImplementedError
