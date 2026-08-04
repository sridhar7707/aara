"""Tests for sentinel_engine.services.evidence_service.EvidenceService."""
import datetime

from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.evidence.evidence import Evidence


def _make_evidence(evidence_id="ev-001", **overrides):
    defaults = dict(
        evidence_id=evidence_id,
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def test_get_evidence_for_decision_returns_empty_list_when_none_associated():
    service = EvidenceService()

    assert service.get_evidence_for_decision("dec-001") == []


def test_associate_evidence_then_get_evidence_for_decision_returns_it():
    service = EvidenceService()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    assert service.get_evidence_for_decision("dec-001") == [evidence]


def test_associate_evidence_accumulates_multiple_items_for_the_same_decision():
    service = EvidenceService()
    first = _make_evidence("ev-001")
    second = _make_evidence("ev-002")

    service.associate_evidence("dec-001", first)
    service.associate_evidence("dec-001", second)

    assert service.get_evidence_for_decision("dec-001") == [first, second]


def test_evidence_is_isolated_per_decision():
    service = EvidenceService()
    evidence = _make_evidence()

    service.associate_evidence("dec-001", evidence)

    assert service.get_evidence_for_decision("dec-002") == []


def test_get_evidence_for_decision_returns_a_copy_not_the_internal_list():
    service = EvidenceService()
    service.associate_evidence("dec-001", _make_evidence())

    result = service.get_evidence_for_decision("dec-001")
    result.append(_make_evidence("ev-injected"))

    assert len(service.get_evidence_for_decision("dec-001")) == 1


def test_evidence_service_does_not_expose_internal_storage_attribute():
    service = EvidenceService()

    assert not hasattr(service, "evidence_by_decision")
