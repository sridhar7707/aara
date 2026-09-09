"""ADR-065-authorized temporary DecisionService composition boundary for
execution-outcome reporting.

Since ADR-067 SS3.C / SS8, the DecisionService used for
``DecisionService.record_execution()`` and its
LedgerRepository/ProjectionRepository are the single shared pair defined in
``sentinel_engine/composition/decision_lifecycle.py`` -- so the execution
outcome lands on the same DecisionProjection the causal lifecycle created and
advanced. ADR-067 SS12 narrowly supersedes the dedicated-instance language of
ADR-013 SS7 / ADR-014 SS8 / ADR-045 SS2.1 for this shared pair only. ADR-065
remains authoritative for the execution-outcome-reporting contract itself
(``execution_adapter.py``, ``record_execution()`` idempotency, failure
isolation); only the backing repository pair is now shared.

This module keeps its public accessor --
``get_decision_service_for_execution_reporting()`` -- and the
``_TemporaryLedgerStore`` / ``_TemporaryProjectionRepository`` /
``_ledger_repository`` / ``_projection_repository`` names unchanged (now bound
to the shared implementation), so no ``bot/`` import line changes.
"""
from sentinel_engine.composition.decision_lifecycle import (
    _LifecycleLedgerStore as _TemporaryLedgerStore,
    _LifecycleProjectionRepository as _TemporaryProjectionRepository,
    _ledger_repository as _ledger_repository,
    _projection_repository as _projection_repository,
    get_decision_service as get_decision_service_for_execution_reporting,
)

__all__ = [
    "_TemporaryLedgerStore",
    "_TemporaryProjectionRepository",
    "_ledger_repository",
    "_projection_repository",
    "get_decision_service_for_execution_reporting",
]
