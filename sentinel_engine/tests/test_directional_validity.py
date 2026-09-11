"""Master Roadmap Sprint 4B.1 -- sentinel_engine.evidence.directional_validity.

Proves the one factual question this module answers: did the action
hypothesis an Evidence item's polarity was evaluated against match the
Decision's actual action? No confidence, no uncertainty, no quality/
reliability/freshness/relevance/corroboration result -- see the module's
own docstring for the full boundary.

Several tests below pin the real, already-discovered production scenario:
`sentinel_engine.adapters.evidence_adapter` always evaluates polarity
against a fixed "BUY" hypothesis (ADR-068), but
`bot/_main_trust_decisions.py::record_decision_safe()` applies it
unconditionally on the exit path too, so a real SELL Decision's evidence
can carry a polarity evaluated against a hypothesis ("BUY") it never
represents. This module must be able to state that mismatch as fact.
"""
import ast
import datetime
import inspect

import pytest

from sentinel_engine.evidence import directional_validity
from sentinel_engine.evidence.directional_validity import (
    DirectionalValidity,
    analyze_directional_validity,
    evaluate_directional_validity,
)
from sentinel_engine.evidence.evidence import Evidence

_T0 = datetime.datetime(2026, 8, 4, 12, 0, 0)


def _make_evidence(evidence_id="ev-001", polarity=None, source="xgboost"):
    return Evidence(
        evidence_id=evidence_id,
        evidence_type="MODEL_OUTPUT",
        source=source,
        data={"signal": "BUY"},
        collected_at=_T0,
        polarity=polarity,
    )


# -- directional polarity, hypothesis matches the decision -----------------

def test_supporting_polarity_with_matching_hypothesis_is_valid():
    evidence = _make_evidence(polarity="SUPPORTING")

    result = evaluate_directional_validity(
        evidence, decision_action="BUY", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is True
    assert result.hypothesis_matches_decision_action is True


def test_contradicting_polarity_with_matching_hypothesis_is_valid():
    evidence = _make_evidence(polarity="CONTRADICTING")

    result = evaluate_directional_validity(
        evidence, decision_action="BUY", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is True
    assert result.hypothesis_matches_decision_action is True


# -- the real production mismatch: SELL decision, BUY-evaluated polarity --

def test_sell_decision_with_buy_evaluated_polarity_is_flagged_as_mismatched():
    """Pins the exact scenario found in the Sprint 4B audit: evidence_adapter
    always evaluates polarity against "BUY" (ADR-068), but
    record_exit_decision_safe() attaches that same evidence to real SELL
    decisions. This must surface as a mismatch, not be silently accepted."""
    evidence = _make_evidence(polarity="CONTRADICTING")  # e.g. model signalled "SELL"

    result = evaluate_directional_validity(
        evidence, decision_action="SELL", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is True
    assert result.hypothesis_matches_decision_action is False


def test_sell_decision_with_supporting_buy_hypothesis_polarity_is_also_mismatched():
    evidence = _make_evidence(polarity="SUPPORTING")  # e.g. model signalled "BUY"

    result = evaluate_directional_validity(
        evidence, decision_action="SELL", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is True
    assert result.hypothesis_matches_decision_action is False


# -- non-directional polarity: match/mismatch is not applicable -----------

def test_none_polarity_is_not_directional_and_match_is_not_applicable():
    evidence = _make_evidence(polarity=None)

    result = evaluate_directional_validity(
        evidence, decision_action="BUY", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is False
    assert result.hypothesis_matches_decision_action is None


def test_none_polarity_stays_not_applicable_even_when_hypothesis_mismatches():
    evidence = _make_evidence(polarity=None)

    result = evaluate_directional_validity(
        evidence, decision_action="SELL", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is False
    assert result.hypothesis_matches_decision_action is None


@pytest.mark.parametrize("bad_polarity", ["", "buy", "supporting", "HOLD", "WAIT", 123])
def test_malformed_or_unrecognised_polarity_is_treated_as_non_directional(bad_polarity):
    evidence = _make_evidence(polarity=bad_polarity)

    result = evaluate_directional_validity(
        evidence, decision_action="BUY", polarity_hypothesis_action="BUY",
    )

    assert result.is_directional is False
    assert result.hypothesis_matches_decision_action is None


# -- action strings are compared verbatim, no invented semantics ----------

@pytest.mark.parametrize("decision_action", ["HOLD", "WAIT", "BUY_MORE"])
def test_action_strings_are_compared_as_opaque_values_for_every_decision_action(decision_action):
    """No special-cased meaning for HOLD/WAIT/BUY_MORE -- just equality."""
    matching = evaluate_directional_validity(
        _make_evidence(polarity="SUPPORTING"),
        decision_action=decision_action,
        polarity_hypothesis_action=decision_action,
    )
    mismatching = evaluate_directional_validity(
        _make_evidence(polarity="SUPPORTING"),
        decision_action=decision_action,
        polarity_hypothesis_action="BUY" if decision_action != "BUY" else "SELL",
    )

    assert matching.hypothesis_matches_decision_action is True
    assert mismatching.hypothesis_matches_decision_action is False


# -- evidence_id / polarity / hypothesis / decision_action are echoed -----

def test_result_echoes_all_four_inputs_verbatim():
    evidence = _make_evidence(evidence_id="ev-echo", polarity="CONTRADICTING")

    result = evaluate_directional_validity(
        evidence, decision_action="SELL", polarity_hypothesis_action="BUY",
    )

    assert result.evidence_id == "ev-echo"
    assert result.polarity == "CONTRADICTING"
    assert result.polarity_hypothesis_action == "BUY"
    assert result.decision_action == "SELL"


# -- batch analysis --------------------------------------------------------

def test_analyze_directional_validity_returns_one_result_per_item_in_order():
    items = [
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="CONTRADICTING", source="lstm"),
        _make_evidence("ev-3", polarity=None, source="finbert"),
    ]

    results = analyze_directional_validity(items, decision_action="BUY", polarity_hypothesis_action="BUY")

    assert [r.evidence_id for r in results] == ["ev-1", "ev-2", "ev-3"]
    assert results[0].hypothesis_matches_decision_action is True
    assert results[1].hypothesis_matches_decision_action is True
    assert results[2].hypothesis_matches_decision_action is None


def test_analyze_directional_validity_applies_the_same_hypothesis_to_every_item():
    items = [
        _make_evidence("ev-1", polarity="SUPPORTING"),
        _make_evidence("ev-2", polarity="CONTRADICTING"),
    ]

    results = analyze_directional_validity(items, decision_action="SELL", polarity_hypothesis_action="BUY")

    assert all(r.polarity_hypothesis_action == "BUY" for r in results)
    assert all(r.decision_action == "SELL" for r in results)
    assert all(r.hypothesis_matches_decision_action is False for r in results)


def test_analyze_directional_validity_on_empty_evidence_returns_empty_tuple():
    assert analyze_directional_validity([], decision_action="BUY", polarity_hypothesis_action="BUY") == ()


# -- determinism and no mutation -------------------------------------------

def test_repeated_evaluation_of_the_same_input_is_equal():
    evidence = _make_evidence(polarity="SUPPORTING")

    first = evaluate_directional_validity(evidence, "BUY", "BUY")
    second = evaluate_directional_validity(evidence, "BUY", "BUY")

    assert first == second


def test_analyze_directional_validity_does_not_mutate_the_input_list():
    items = [_make_evidence("ev-1", polarity="SUPPORTING")]
    snapshot = list(items)

    analyze_directional_validity(items, "BUY", "BUY")

    assert items == snapshot
    assert items[0] is snapshot[0]


def test_directional_validity_result_is_frozen():
    result = evaluate_directional_validity(_make_evidence(polarity="SUPPORTING"), "BUY", "BUY")
    with pytest.raises(Exception):
        result.decision_action = "SELL"


# -- structural guards ------------------------------------------------------

def test_module_has_no_bot_ledger_applications_or_execution_imports():
    source = inspect.getsource(directional_validity)
    tree = ast.parse(source)
    forbidden = (
        "bot", "alpaca", "applications", "ledger", "database", "dashboard", "scheduler",
        "sentinel_engine.services", "sentinel_engine.composition",
        "sentinel_engine.governance", "sentinel_engine.repositories",
        "sentinel_engine.ledger", "sentinel_engine.adapters",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), module


def test_module_never_imports_or_calls_ensemble_machinery():
    tree = ast.parse(inspect.getsource(directional_validity))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ensemble" not in alias.name.lower()
        elif isinstance(node, ast.ImportFrom):
            assert "ensemble" not in (node.module or "").lower()
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert "ensemble" not in node.func.id.lower()


def test_module_defines_no_confidence_uncertainty_quality_or_score_result():
    """This slice produces one factual comparison only -- no function,
    class, or field name may claim to be a confidence/uncertainty/quality/
    reliability/freshness/relevance/corroboration/weighted result."""
    forbidden_terms = (
        "confidence", "uncertainty", "quality", "reliability",
        "freshness", "relevance", "corroborat", "weight", "score",
    )
    tree = ast.parse(inspect.getsource(directional_validity))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        if isinstance(node, ast.arg):
            names.add(node.arg)
    lowered = {name.lower() for name in names}
    for term in forbidden_terms:
        assert not any(term in name for name in lowered), (term, lowered)


def test_module_is_a_pure_function_with_no_side_effect_markers():
    src = inspect.getsource(directional_validity)
    assert "open(" not in src
    assert "requests" not in src
    assert "sqlite3" not in src
    assert "socket" not in src
    assert "datetime.now(" not in src
