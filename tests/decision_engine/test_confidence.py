import pytest

from bot.decision_engine.confidence import ConfidenceCalculator
from bot.decision_engine.evidence_aggregator import EvidenceSummary


def _summary(supporting, conflicting, evidence_count=None):
    if evidence_count is None:
        evidence_count = len(supporting) + len(conflicting)
    return EvidenceSummary(
        total_positive_contribution=0.0,
        total_negative_contribution=0.0,
        supporting_sources=tuple(supporting),
        conflicting_sources=tuple(conflicting),
        evidence_count=evidence_count,
    )


def test_empty_evidence_returns_score_near_zero():
    calculator = ConfidenceCalculator()
    result = calculator.calculate(_summary([], []))
    assert result.score == 0.0
    assert result.evidence_count == 0
    assert result.supporting_count == 0
    assert result.conflicting_count == 0


def test_single_supporting_evidence_yields_low_but_nonzero_confidence():
    calculator = ConfidenceCalculator()
    result = calculator.calculate(_summary(["xgb"], []))
    assert 0.0 < result.score < 1.0
    assert result.supporting_count == 1
    assert result.conflicting_count == 0


def test_strong_agreement_yields_high_confidence():
    calculator = ConfidenceCalculator()
    result = calculator.calculate(
        _summary(["xgb", "lstm", "sentiment", "macro", "regime"], [])
    )
    assert result.score == pytest.approx(1.0)


def test_more_supporting_evidence_increases_confidence():
    calculator = ConfidenceCalculator()
    low = calculator.calculate(_summary(["xgb"], []))
    high = calculator.calculate(_summary(["xgb", "lstm", "sentiment"], []))
    assert high.score > low.score


def test_conflicting_evidence_reduces_confidence():
    calculator = ConfidenceCalculator()
    clean = calculator.calculate(_summary(["xgb", "lstm", "sentiment"], []))
    conflicted = calculator.calculate(
        _summary(["xgb", "lstm", "sentiment"], ["macro", "regime"])
    )
    assert conflicted.score < clean.score


def test_mixed_evidence_scores_lower_than_full_agreement():
    calculator = ConfidenceCalculator()
    mixed = calculator.calculate(_summary(["a", "b", "c"], ["d", "e", "f"]))
    agreement = calculator.calculate(_summary(["a", "b", "c", "d", "e", "f"], []))
    assert mixed.score < agreement.score


def test_score_always_within_bounds():
    calculator = ConfidenceCalculator()
    cases = [
        _summary([], []),
        _summary(["a"], []),
        _summary([], ["a"]),
        _summary(["a", "b", "c", "d", "e", "f", "g"], []),
        _summary(["a"], ["b", "c", "d", "e", "f"]),
    ]
    for case in cases:
        result = calculator.calculate(case)
        assert 0.0 <= result.score <= 1.0


def test_deterministic_calculation_for_same_input():
    calculator = ConfidenceCalculator()
    summary = _summary(["xgb", "lstm"], ["macro"])
    first = calculator.calculate(summary)
    second = calculator.calculate(summary)
    assert first == second


def test_rationale_is_generated_and_nonempty():
    calculator = ConfidenceCalculator()
    result = calculator.calculate(_summary(["xgb"], ["macro"]))
    assert isinstance(result.rationale, str)
    assert len(result.rationale) > 0


def test_rationale_mentions_supporting_and_conflicting_counts():
    calculator = ConfidenceCalculator()
    result = calculator.calculate(_summary(["xgb", "lstm"], ["macro"]))
    assert "2" in result.rationale
    assert "1" in result.rationale
