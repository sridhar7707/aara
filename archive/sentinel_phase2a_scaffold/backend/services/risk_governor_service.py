"""RiskGovernorService (IMPLEMENTATION_HANDOFF.md: Service interfaces).

Not listed in the handoff doc's repository tree under services/, but
explicitly specified as a service interface to generate -- added here
alongside projection_service.py for the same reason.

RiskGovernorState is a 3-state machine (NORMAL/WARNING/DEFENSIVE).
DEFENSIVE is a hard stop on new decisions. Thresholds beyond DEFENSIVE
are recorded as Governance Integrity BREACH events, not a 4th state.
"""

from sentinel.backend.domain.enums import RiskGovernorState
from sentinel.backend.domain.governance import RiskState
from sentinel.backend.repositories.projection_repository import ProjectionRepository


class RiskGovernorService:
    def __init__(self, projection_repository: ProjectionRepository) -> None:
        self._projection_repository = projection_repository

    def current_state(self) -> RiskState:
        raise NotImplementedError

    def check_threshold(self, drawdown_pct: float) -> RiskGovernorState:
        raise NotImplementedError
