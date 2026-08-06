"""Governance projection (DERIVED_STATE_VIEWS_v1.2.md).

Builds the Risk Governor / governance read model. RiskGovernorState is
3-state (NORMAL/WARNING/DEFENSIVE); integrity breaches beyond
DEFENSIVE surface as Governance Integrity Events, not a 4th state.
"""

from typing import Any

from sentinel.backend.events.event import Event


def project_governance_state(events: list[Event]) -> dict[str, Any]:
    raise NotImplementedError
