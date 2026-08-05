from datetime import datetime, timezone

import pytest

from bot.decision_engine.confidence import ConfidenceScore
from bot.decision_engine.decision_context import DecisionContext
from bot.decision_engine.evidence_aggregator import EvidenceSummary
from bot.decision_engine.explanation import ExplanationGenerator

_PROHIBITED_PHRASES = (
    "will increase",
    "guaranteed",
    "market will",
    "expected profit",
)


def _context(symbol="AAPL"):
    return DecisionContext(
        symbol=symbol,
        timestamp=datetime(2026, 8, 5, tzinfo=timezone.utc),
        strategy_signals={},
        portfolio_context={},
        market_regime="neutral",
        risk_state="normal",
    )


def _evidence_summary(supporting=(), conflicting=(), evidence_count=None):
    if evidence_count is None:
        evidence_count = len(supporting) + len(conflicting)
    return EvidenceSummary(
        total_positive_contribution=0.0,
        total_negative_contribution=0.0,
        supporting_sources=tuple(supporting),
        conflicting_sources=tuple(conflicting),
        evidence_count=evidence_count,
    )


def _confidence(score, evidence_count, supporting_count, conflicting_count, rationale="rationale"):
    return ConfidenceScore(
        score=score,
        evidence_count=evidence_count,
        supporting_count=supporting_count,
        conflicting_count=conflicting_count,
        rationale=rationale,
    )


def test_supporting_evidence_is_reflected_in_reasons_and_summary():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(supporting=["xgb", "sentiment"])
    confidence_score = _confidence(0.8, 2, 2, 0, rationale="2 supporting vs 0 conflicting")

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    assert "xgb" in explanation.summary
    assert "sentiment" in explanation.summary
    assert any("xgb" in reason and "supporting" in reason for reason in explanation.evidence_reasons)
    assert any("sentiment" in reason and "supporting" in reason for reason in explanation.evidence_reasons)


def test_conflicting_evidence_is_reflected_in_reasons_and_summary():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(supporting=["xgb"], conflicting=["macro"])
    confidence_score = _confidence(0.3, 2, 1, 1, rationale="1 supporting vs 1 conflicting")

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    assert "macro" in explanation.summary
    assert any("macro" in reason and "conflicting" in reason for reason in explanation.evidence_reasons)
    assert any("conflicting" in warning.lower() for warning in explanation.warnings)


def test_low_confidence_produces_warning():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(supporting=["xgb"])
    confidence_score = _confidence(0.1, 1, 1, 0, rationale="1 supporting vs 0 conflicting")

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    assert any("low" in warning.lower() for warning in explanation.warnings)
    assert "low" in explanation.confidence_reason.lower()


def test_high_confidence_produces_no_low_confidence_warning():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(
        supporting=["xgb", "lstm", "sentiment", "macro", "regime"]
    )
    confidence_score = _confidence(0.95, 5, 5, 0, rationale="5 supporting vs 0 conflicting")

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    assert not any("low" in warning.lower() for warning in explanation.warnings)
    assert "high" in explanation.confidence_reason.lower()


def test_empty_evidence_produces_explanation_with_warning():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary()
    confidence_score = _confidence(
        0.0, 0, 0, 0, rationale="No evidence available; confidence defaults to zero."
    )

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    assert explanation.evidence_reasons
    assert any("no evidence" in reason.lower() for reason in explanation.evidence_reasons)
    assert any("no evidence" in warning.lower() for warning in explanation.warnings)


def test_deterministic_output_for_same_input():
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(supporting=["xgb"], conflicting=["macro"])
    confidence_score = _confidence(0.4, 2, 1, 1, rationale="1 supporting vs 1 conflicting")
    context = _context()

    first = generator.generate(context, evidence_summary, confidence_score)
    second = generator.generate(context, evidence_summary, confidence_score)

    assert first == second


@pytest.mark.parametrize(
    "supporting,conflicting,score",
    [
        (["xgb", "lstm"], [], 0.9),
        (["xgb"], ["macro"], 0.2),
        ([], [], 0.0),
        (["xgb", "lstm", "sentiment", "macro", "regime"], [], 1.0),
    ],
)
def test_no_prohibited_prediction_language(supporting, conflicting, score):
    generator = ExplanationGenerator()
    evidence_summary = _evidence_summary(supporting=supporting, conflicting=conflicting)
    confidence_score = _confidence(
        score,
        len(supporting) + len(conflicting),
        len(supporting),
        len(conflicting),
        rationale="synthetic rationale for testing",
    )

    explanation = generator.generate(_context(), evidence_summary, confidence_score)

    full_text = " ".join(
        [explanation.summary, explanation.confidence_reason]
        + list(explanation.evidence_reasons)
        + list(explanation.warnings)
    ).lower()

    for phrase in _PROHIBITED_PHRASES:
        assert phrase not in full_text


def test_evidence_reasons_and_warnings_are_tuples():
    generator = ExplanationGenerator()
    explanation = generator.generate(
        _context(), _evidence_summary(supporting=["xgb"]), _confidence(0.5, 1, 1, 0)
    )

    assert isinstance(explanation.evidence_reasons, tuple)
    assert isinstance(explanation.warnings, tuple)
