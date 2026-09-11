"""Master Roadmap Sprint 4A -- sentinel_engine.evidence.evidence_analysis.

Pure evidence-analysis facts over the existing Evidence model: counts,
polarity mix, agreement/disagreement, corroboration by distinct source,
type/source distribution, and optional collected_at age. No confidence, no
uncertainty, no relevance, no ensemble_confidence/ensemble_score, no I/O,
no persistence -- see the module's own docstring for the full boundary.
"""
import ast
import copy
import datetime
import inspect

import pytest

from sentinel_engine.evidence import evidence_analysis
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.evidence.evidence_analysis import (
    EvidenceAge,
    EvidenceAnalysis,
    analyze_evidence,
    evidence_age,
)

_T0 = datetime.datetime(2026, 8, 4, 12, 0, 0)


def _make_evidence(evidence_id="ev-001", polarity=None, source="xgboost",
                    evidence_type="MODEL_OUTPUT", collected_at=_T0, **overrides):
    defaults = dict(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source=source,
        data={"signal": "BUY"},
        collected_at=collected_at,
        polarity=polarity,
    )
    defaults.update(overrides)
    return Evidence(**defaults)


# -- 1: zero evidence ------------------------------------------------------

def test_zero_evidence_yields_all_zero_counts_and_undefined_agreement():
    result = analyze_evidence([])

    assert result.total_count == 0
    assert result.supporting_count == 0
    assert result.contradicting_count == 0
    assert result.neutral_count == 0
    assert result.agreement_ratio is None
    assert result.contradiction_present is False
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 0
    assert result.evidence_type_distribution == {}
    assert result.evidence_source_distribution == {}
    assert result.ages == ()


# -- 2: one supporting -------------------------------------------------

def test_one_supporting_evidence():
    result = analyze_evidence([_make_evidence(polarity="SUPPORTING")])

    assert result.total_count == 1
    assert result.supporting_count == 1
    assert result.contradicting_count == 0
    assert result.neutral_count == 0
    assert result.agreement_ratio == 1.0
    assert result.contradiction_present is False
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 1


# -- 3: one contradicting ------------------------------------------------

def test_one_contradicting_evidence():
    result = analyze_evidence([_make_evidence(polarity="CONTRADICTING")])

    assert result.total_count == 1
    assert result.supporting_count == 0
    assert result.contradicting_count == 1
    assert result.neutral_count == 0
    assert result.agreement_ratio == 1.0
    assert result.contradiction_present is True
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 0


# -- 4: one neutral (None polarity) --------------------------------------

def test_one_neutral_evidence_with_none_polarity():
    result = analyze_evidence([_make_evidence(polarity=None)])

    assert result.total_count == 1
    assert result.supporting_count == 0
    assert result.contradicting_count == 0
    assert result.neutral_count == 1
    assert result.agreement_ratio is None
    assert result.contradiction_present is False
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 0


# -- 5: unanimous supporting ----------------------------------------------

def test_unanimous_supporting_evidence():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="SUPPORTING", source="lstm"),
        _make_evidence("ev-3", polarity="SUPPORTING", source="finbert"),
    ])

    assert result.total_count == 3
    assert result.supporting_count == 3
    assert result.contradicting_count == 0
    assert result.agreement_ratio == 1.0
    assert result.contradiction_present is False
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 3


# -- 6: unanimous contradicting -------------------------------------------

def test_unanimous_contradicting_evidence():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="CONTRADICTING", source="xgboost"),
        _make_evidence("ev-2", polarity="CONTRADICTING", source="lstm"),
    ])

    assert result.total_count == 2
    assert result.contradicting_count == 2
    assert result.agreement_ratio == 1.0
    assert result.contradiction_present is True
    assert result.unresolved_disagreement_present is False
    assert result.corroborating_source_count == 0


# -- 7: mixed supporting/contradicting ------------------------------------

def test_mixed_supporting_and_contradicting_evidence():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="CONTRADICTING", source="lstm"),
    ])

    assert result.total_count == 2
    assert result.supporting_count == 1
    assert result.contradicting_count == 1
    assert result.agreement_ratio == 0.0
    assert result.contradiction_present is True
    assert result.unresolved_disagreement_present is True
    assert result.corroborating_source_count == 1


def test_two_supporting_one_contradicting_partial_agreement():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="SUPPORTING", source="lstm"),
        _make_evidence("ev-3", polarity="CONTRADICTING", source="finbert"),
    ])

    # directional_count = 3, |2-1| / 3
    assert result.agreement_ratio == pytest.approx(1 / 3)
    assert result.unresolved_disagreement_present is True


# -- 8: supporting + neutral ------------------------------------------

def test_supporting_plus_neutral_evidence():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity=None, source="lstm"),
    ])

    assert result.total_count == 2
    assert result.supporting_count == 1
    assert result.neutral_count == 1
    assert result.contradicting_count == 0
    assert result.agreement_ratio == 1.0  # directional_count is 1 (neutral excluded)
    assert result.contradiction_present is False
    assert result.unresolved_disagreement_present is False


# -- 9: contradicting + neutral -----------------------------------------

def test_contradicting_plus_neutral_evidence():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="CONTRADICTING", source="xgboost"),
        _make_evidence("ev-2", polarity=None, source="lstm"),
    ])

    assert result.total_count == 2
    assert result.contradicting_count == 1
    assert result.neutral_count == 1
    assert result.agreement_ratio == 1.0
    assert result.contradiction_present is True
    assert result.unresolved_disagreement_present is False


# -- 10: corroborating multiple supporting evidence -----------------------

def test_corroboration_counts_distinct_sources_not_raw_items():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-3", polarity="SUPPORTING", source="lstm"),
    ])

    assert result.supporting_count == 3
    # Only 2 distinct sources corroborate, even though 3 items support.
    assert result.corroborating_source_count == 2


def test_corroboration_ignores_contradicting_and_neutral_sources():
    result = analyze_evidence([
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="CONTRADICTING", source="lstm"),
        _make_evidence("ev-3", polarity=None, source="finbert"),
    ])

    assert result.corroborating_source_count == 1


# -- 11: collected_at freshness calculation --------------------------------

def test_evidence_age_is_plain_elapsed_time():
    item = _make_evidence(collected_at=_T0)
    reference = _T0 + datetime.timedelta(hours=2)

    assert evidence_age(item, reference) == datetime.timedelta(hours=2)


def test_evidence_age_can_be_negative_when_evidence_is_after_reference():
    item = _make_evidence(collected_at=_T0 + datetime.timedelta(hours=1))

    assert evidence_age(item, _T0) == datetime.timedelta(hours=-1)


def test_analyze_evidence_without_reference_timestamp_leaves_ages_empty():
    result = analyze_evidence([_make_evidence()])

    assert result.ages == ()


def test_analyze_evidence_with_reference_timestamp_populates_ages_in_order():
    reference = _T0 + datetime.timedelta(days=1)
    result = analyze_evidence(
        [
            _make_evidence("ev-1", collected_at=_T0),
            _make_evidence("ev-2", collected_at=_T0 + datetime.timedelta(hours=12)),
        ],
        reference_timestamp=reference,
    )

    assert result.ages == (
        EvidenceAge(evidence_id="ev-1", age=datetime.timedelta(days=1)),
        EvidenceAge(evidence_id="ev-2", age=datetime.timedelta(hours=12)),
    )


# -- 12: deterministic repeated analysis -----------------------------------

def test_repeated_analysis_of_the_same_input_is_equal():
    items = [
        _make_evidence("ev-1", polarity="SUPPORTING", source="xgboost"),
        _make_evidence("ev-2", polarity="CONTRADICTING", source="lstm"),
    ]

    first = analyze_evidence(items, reference_timestamp=_T0)
    second = analyze_evidence(items, reference_timestamp=_T0)

    assert first == second


# -- 13: input collection is not mutated -----------------------------------

def test_analyze_evidence_does_not_mutate_the_input_list_or_items():
    items = [
        _make_evidence("ev-1", polarity="SUPPORTING"),
        _make_evidence("ev-2", polarity="CONTRADICTING"),
    ]
    snapshot = copy.deepcopy(items)

    analyze_evidence(items, reference_timestamp=_T0)

    assert items == snapshot


# -- malformed / unsupported polarity, per existing Evidence convention ---

@pytest.mark.parametrize("bad_polarity", ["", "buy", "SUPPORTING ", "supporting", "HOLD", 123])
def test_malformed_or_unrecognised_polarity_is_treated_as_neutral(bad_polarity):
    result = analyze_evidence([_make_evidence(polarity=bad_polarity)])

    assert result.supporting_count == 0
    assert result.contradicting_count == 0
    assert result.neutral_count == 1
    assert result.corroborating_source_count == 0


def test_evidence_type_and_source_distribution_are_counted():
    result = analyze_evidence([
        _make_evidence("ev-1", source="xgboost", evidence_type="MODEL_OUTPUT"),
        _make_evidence("ev-2", source="lstm", evidence_type="MODEL_OUTPUT"),
        _make_evidence("ev-3", source="newsapi", evidence_type="NEWS_SENTIMENT"),
    ])

    assert result.evidence_type_distribution == {"MODEL_OUTPUT": 2, "NEWS_SENTIMENT": 1}
    assert result.evidence_source_distribution == {"xgboost": 1, "lstm": 1, "newsapi": 1}


# -- structural guards: stay decoupled from the legacy ensemble concept ---

def test_module_has_no_ensemble_bot_or_persistence_imports():
    source = inspect.getsource(evidence_analysis)
    tree = ast.parse(source)
    forbidden = (
        "bot", "alpaca", "applications",
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


def test_module_never_imports_or_calls_ensemble_confidence_or_ensemble_score():
    """The module docstring documents the forbidden legacy concepts by name
    (required by the "keep these concepts separate" architectural
    principle) -- that prose is fine. What must never appear is an actual
    import of, or call to, the legacy ensemble machinery."""
    tree = ast.parse(inspect.getsource(evidence_analysis))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ensemble" not in alias.name.lower()
        elif isinstance(node, ast.ImportFrom):
            assert "ensemble" not in (node.module or "").lower()
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert "ensemble" not in node.func.id.lower()
        elif isinstance(node, ast.Attribute):
            assert "ensemble" not in node.attr.lower()


def test_module_does_not_compute_a_confidence_or_uncertainty_result():
    """This slice produces analysis facts only -- no field or function name
    may claim to be a confidence or uncertainty verdict."""
    tree = ast.parse(inspect.getsource(evidence_analysis))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    lowered = {name.lower() for name in names}
    assert not any("confidence" in name for name in lowered)
    assert not any("uncertainty" in name for name in lowered)


def test_analyze_evidence_is_a_pure_function_with_no_side_effect_markers():
    src = inspect.getsource(evidence_analysis)
    assert "open(" not in src
    assert "requests" not in src
    assert "sqlite3" not in src
    assert "socket" not in src


def test_evidence_analysis_result_type_is_frozen():
    result = analyze_evidence([_make_evidence(polarity="SUPPORTING")])
    with pytest.raises(Exception):
        result.total_count = 99
