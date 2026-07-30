"""Hash-chain integrity helpers (SYSTEM_EVENT_MODEL_v1.2.md).

Signatures only. Every event's record_hash chains to the previous
event's record_hash so tampering is detectable.
"""

from sentinel.backend.events.event import Event


def compute_record_hash(event: Event) -> str:
    """Compute the SHA-256 record_hash for an event given its fields."""
    raise NotImplementedError


def verify_chain(events: list[Event]) -> bool:
    """Verify record_hash/previous_record_hash linkage across a sequence."""
    raise NotImplementedError
