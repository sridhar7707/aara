"""Governance and Risk Governor domain models (IMPLEMENTATION_HANDOFF.md).

Governance rules are checkpoints, not suggestions. Risk Governor DEFENSIVE
state is a hard stop on new decisions; it does not bypass governance.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sentinel.backend.domain.enums import RiskGovernorState


@dataclass
class Governance:
    status: str
    checks: dict[str, Any] = field(default_factory=dict)
    policy_version: str = ""
    effective_date: date | None = None


@dataclass
class RiskState:
    current_state: RiskGovernorState
    drawdown_pct: float
    buffer_pct: float
