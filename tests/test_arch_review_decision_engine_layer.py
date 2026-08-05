"""Guards that scripts/arch_review.py knows about bot/decision_engine/.

Phase 2B.5.1 hardening: decision_engine currently has no callers, so there's
nothing to bypass yet. But once Phase 2B.6+ wires it in, it must be able to
detect a decision_engine module reaching straight into execution/broker code
instead of routing through the risk manager -- exactly like the existing
strategy-layer bypass check. This only asserts analyzer *coverage*; it does
not change any existing rule.
"""
from scripts.arch_review import LAYER_PATHS, STRATEGY_LAYERS, get_layer


def test_decision_engine_files_are_classified_into_a_layer():
    assert get_layer("bot/decision_engine/decision_engine.py") is not None
    assert get_layer("bot/decision_engine/models.py") is not None


def test_decision_engine_layer_is_registered_in_layer_paths():
    assert any(
        "bot/decision_engine" in path for paths in LAYER_PATHS.values() for path in paths
    )


def test_decision_engine_layer_is_subject_to_the_risk_bypass_check():
    decision_layer = get_layer("bot/decision_engine/decision_engine.py")
    assert decision_layer in STRATEGY_LAYERS
