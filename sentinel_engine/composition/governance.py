"""ADR-045 SS2.1-authorized temporary GovernanceService composition boundary.

Since ADR-067 SS3.C / SS8, the GovernanceService and its
LedgerRepository/ProjectionRepository are the single shared pair defined in
``sentinel_engine/composition/decision_lifecycle.py`` -- so one
DecisionProjection can walk the full causal lifecycle. ADR-067 SS12 narrowly
supersedes ADR-045 SS2.1's dedicated-instance language (and ADR-014 SS8's) for
this shared pair only. ADR-045 SS3's prohibition on operative Policy
registration and record_approval() wiring is untouched and remains in force;
this module only exposes evaluate_policy() through the shared service.

This module keeps its public accessor -- ``get_governance_service()`` -- and the
``_TemporaryLedgerStore`` / ``_TemporaryProjectionRepository`` /
``_ledger_repository`` / ``_projection_repository`` names unchanged (now bound
to the shared implementation), so no ``bot/`` import line changes.
"""
from sentinel_engine.composition.decision_lifecycle import (
    _LifecycleLedgerStore as _TemporaryLedgerStore,
    _LifecycleProjectionRepository as _TemporaryProjectionRepository,
    _ledger_repository as _ledger_repository,
    _projection_repository as _projection_repository,
    get_governance_service as get_governance_service,
)

__all__ = [
    "_TemporaryLedgerStore",
    "_TemporaryProjectionRepository",
    "_ledger_repository",
    "_projection_repository",
    "get_governance_service",
]
