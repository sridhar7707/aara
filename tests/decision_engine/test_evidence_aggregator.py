import pytest

from bot.decision_engine.evidence_aggregator import aggregate_evidence
from bot.decision_engine.models import EvidenceItem


def _item(source, contribution, signal="directional", value=0.5):
    return EvidenceItem(source=source, signal=signal, value=value, contribution=contribution)


def test_single_evidence_item():
    summary = aggregate_evidence([_item("xgb", 0.3)])
    assert summary.total_positive_contribution == pytest.approx(0.3)
    assert summary.total_negative_contribution == 0.0
    assert summary.supporting_sources == ("xgb",)
    assert summary.conflicting_sources == ()
    assert summary.evidence_count == 1


def test_multiple_supporting_evidence_items():
    summary = aggregate_evidence(
        [_item("xgb", 0.3), _item("lstm", 0.2), _item("sentiment", 0.1)]
    )
    assert summary.total_positive_contribution == pytest.approx(0.6)
    assert summary.total_negative_contribution == 0.0
    assert summary.supporting_sources == ("xgb", "lstm", "sentiment")
    assert summary.conflicting_sources == ()
    assert summary.evidence_count == 3


def test_conflicting_evidence_populates_conflicting_sources():
    summary = aggregate_evidence([_item("xgb", 0.4), _item("lstm", -0.3)])
    assert summary.total_positive_contribution == pytest.approx(0.4)
    assert summary.total_negative_contribution == pytest.approx(-0.3)
    assert summary.supporting_sources == ("xgb",)
    assert summary.conflicting_sources == ("lstm",)
    assert summary.evidence_count == 2


def test_empty_evidence_returns_safe_summary():
    summary = aggregate_evidence([])
    assert summary.total_positive_contribution == 0.0
    assert summary.total_negative_contribution == 0.0
    assert summary.supporting_sources == ()
    assert summary.conflicting_sources == ()
    assert summary.evidence_count == 0


def test_deterministic_output_for_same_input():
    items = [_item("xgb", 0.3), _item("lstm", -0.2)]
    first = aggregate_evidence(items)
    second = aggregate_evidence(items)
    assert first == second
