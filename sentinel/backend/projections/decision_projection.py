"""Decision projection (DERIVED_STATE_VIEWS_v1.2.md).

Builds the read model for a single decision from the event stream.
No business logic beyond folding events into a view shape.
"""

from typing import Any

from sentinel.backend.events.event import Event


def project_decision_view(events: list[Event]) -> dict[str, Any]:
    raise NotImplementedError
