"""Tests for sentinel_engine.evidence.evidence.Evidence."""
import datetime
import dataclasses

import pytest

from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.evidence.evidence_polarity import EvidencePolarity


def _make_evidence(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def test_evidence_can_be_created_with_required_fields():
    evidence = _make_evidence()
    assert evidence.evidence_id == "ev-001"
    assert evidence.evidence_type == "NEWS_SENTIMENT"
    assert evidence.source == "newsapi"
    assert evidence.data == {"score": 0.62}
    assert evidence.collected_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_evidence_is_a_dataclass():
    assert dataclasses.is_dataclass(Evidence)


def test_evidence_is_immutable():
    evidence = _make_evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.source = "other"


def test_evidence_requires_all_fields():
    with pytest.raises(TypeError):
        Evidence(evidence_id="ev-001", evidence_type="NEWS_SENTIMENT")


def test_evidence_polarity_defaults_to_none():
    """Batch 2's additive polarity field must not break existing callers
    that construct Evidence without it."""
    evidence = _make_evidence()
    assert evidence.polarity is None


@pytest.mark.parametrize("polarity", [
    EvidencePolarity.SUPPORTING,
    EvidencePolarity.CONTRADICTING,
])
def test_evidence_preserves_polarity_when_provided(polarity):
    evidence = _make_evidence(polarity=polarity.value)
    assert evidence.polarity == polarity.value
