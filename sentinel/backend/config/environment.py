"""Environment resolution (IMPLEMENTATION_HANDOFF.md: OperationalMode).

Phase 2A supports RESEARCH, PAPER, SUPERVISED only. GOVERNED_AUTOMATION
is a reserved future value -- do not build execution infrastructure
for it in Phase 2A.
"""

from sentinel.backend.domain.enums import OperationalMode

PHASE_2A_SUPPORTED_MODES = (
    OperationalMode.RESEARCH,
    OperationalMode.PAPER,
    OperationalMode.SUPERVISED,
)


def get_operational_mode() -> OperationalMode:
    raise NotImplementedError
