"""Tests for applications.trading_intelligence.services.recommendation_diff.

Mirrors news_cache_snapshot_diff.py's own discipline: a pure, deterministic
comparison of two already-fetched RecommendationSnapshot instances for the
same symbol -- "the recommendation was X, is now Y", never "the change is
material" or "the recommendation is invalidated". Every field is a fact
directly computable from the two snapshots' own values -- none is
invented, weighted, or scored.
"""
from applications.trading_intelligence.adapters.legacy_recommendation_source import (
    RecommendationSnapshot,
)
from applications.trading_intelligence.services.recommendation_diff import (
    RecommendationDiff,
    diff_recommendation_snapshots,
)


def _snapshot(**overrides):
    defaults = dict(
        symbol="AAPL", prediction_date="2026-09-01", recommendation="BUY", confidence=0.61,
    )
    defaults.update(overrides)
    return RecommendationSnapshot(**defaults)


def test_same_recommendation_is_unchanged():
    before = _snapshot(prediction_date="2026-09-01", recommendation="BUY", confidence=0.61)
    after = _snapshot(prediction_date="2026-09-05", recommendation="BUY", confidence=0.58)

    result = diff_recommendation_snapshots(before, after)

    assert result.is_unchanged is True


def test_different_recommendation_is_changed():
    before = _snapshot(prediction_date="2026-09-01", recommendation="BUY", confidence=0.61)
    after = _snapshot(prediction_date="2026-09-05", recommendation="WAIT", confidence=0.48)

    result = diff_recommendation_snapshots(before, after)

    assert result.is_unchanged is False


def test_result_carries_recommendation_values_verbatim():
    before = _snapshot(recommendation="BUY")
    after = _snapshot(recommendation="WAIT")

    result = diff_recommendation_snapshots(before, after)

    assert result.before_recommendation == "BUY"
    assert result.after_recommendation == "WAIT"


def test_result_carries_confidence_values_verbatim():
    before = _snapshot(confidence=0.6101)
    after = _snapshot(confidence=0.4823)

    result = diff_recommendation_snapshots(before, after)

    assert result.before_confidence == 0.6101
    assert result.after_confidence == 0.4823


def test_result_carries_snapshot_identity_fields_verbatim():
    before = _snapshot(symbol="AAPL", prediction_date="2026-09-01")
    after = _snapshot(symbol="AAPL", prediction_date="2026-09-05")

    result = diff_recommendation_snapshots(before, after)

    assert result.symbol == "AAPL"
    assert result.before_prediction_date == "2026-09-01"
    assert result.after_prediction_date == "2026-09-05"


def test_is_unchanged_is_plain_equality_regardless_of_confidence_drift():
    """Confidence may drift while the recommendation itself stays the
    same -- is_unchanged reflects only the recommendation string, never a
    confidence-delta threshold."""
    before = _snapshot(recommendation="BUY", confidence=0.99)
    after = _snapshot(recommendation="BUY", confidence=0.51)

    result = diff_recommendation_snapshots(before, after)

    assert result.is_unchanged is True


def test_mismatched_symbols_raise_value_error():
    before = _snapshot(symbol="AAPL")
    after = _snapshot(symbol="MSFT")

    import pytest
    with pytest.raises(ValueError):
        diff_recommendation_snapshots(before, after)


def test_diff_result_type_carries_no_materiality_severity_or_alert_fields():
    """Regression lock for the sprint's explicit scope boundary: the
    result type must never grow a materiality/severity/alert/score/
    validity/polarity field. confidence itself IS an intentional,
    verbatim-passthrough field for this diff type -- not forbidden."""
    forbidden_field_names = {
        "materiality", "material", "valid", "invalidated", "thesis",
        "score", "severity", "alert", "polarity", "significance",
    }
    actual_fields = set(RecommendationDiff.__dataclass_fields__.keys())

    assert actual_fields.isdisjoint(forbidden_field_names)
