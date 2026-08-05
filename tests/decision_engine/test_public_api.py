"""Contract tests for bot.decision_engine's public package surface.

These guard the Phase 2B.5.1 hardening decisions: there is exactly one
DecisionResult (the orchestration result produced by DecisionEngine.evaluate),
and it is reachable from the package root without knowing the internal
module layout.
"""
import bot.decision_engine as decision_engine_pkg
from bot.decision_engine import (
    DecisionContext,
    DecisionEngine,
    DecisionResult,
    DecisionState,
    EvidenceItem,
)
from bot.decision_engine.decision_engine import DecisionResult as CanonicalDecisionResult


def test_package_level_decision_result_is_the_canonical_orchestration_result():
    assert DecisionResult is CanonicalDecisionResult


def test_models_module_no_longer_defines_a_decision_result():
    import bot.decision_engine.models as models

    assert not hasattr(models, "DecisionResult")


def test_package_exposes_stable_public_api():
    assert decision_engine_pkg.DecisionEngine is DecisionEngine
    assert decision_engine_pkg.DecisionResult is DecisionResult
    assert decision_engine_pkg.DecisionContext is DecisionContext
    assert decision_engine_pkg.EvidenceItem is EvidenceItem
    assert decision_engine_pkg.DecisionState is DecisionState


def test_public_api_is_exactly_the_intended_contract():
    assert set(decision_engine_pkg.__all__) == {
        "DecisionEngine",
        "DecisionResult",
        "DecisionContext",
        "EvidenceItem",
        "DecisionState",
    }
