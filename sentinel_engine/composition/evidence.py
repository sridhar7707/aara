"""ADR-013-authorized temporary EvidenceService composition boundary.

Since ADR-067 SS3.C / SS8, the EvidenceService and its
LedgerRepository/ProjectionRepository are the single shared pair defined in
``sentinel_engine/composition/decision_lifecycle.py`` -- so one
DecisionProjection can walk the full causal lifecycle. ADR-067 SS12 narrowly
supersedes ADR-013 SS7's dedicated-instance language for this shared pair only;
every other ADR-013 provision (process-local, non-durable, ADR-004-deferred,
no decision creation from this module) remains in force.

This module keeps its public accessor -- ``get_evidence_service()`` -- and the
``_TemporaryLedgerStore`` / ``_TemporaryProjectionRepository`` /
``_ledger_repository`` / ``_projection_repository`` names unchanged (now bound
to the shared implementation), so no ``bot/`` import line changes.
"""
from sentinel_engine.composition.decision_lifecycle import (
    _LifecycleLedgerStore as _TemporaryLedgerStore,
    _LifecycleProjectionRepository as _TemporaryProjectionRepository,
    _ledger_repository as _ledger_repository,
    _projection_repository as _projection_repository,
    get_evidence_service as get_evidence_service,
)

__all__ = [
    "_TemporaryLedgerStore",
    "_TemporaryProjectionRepository",
    "_ledger_repository",
    "_projection_repository",
    "get_evidence_service",
]
