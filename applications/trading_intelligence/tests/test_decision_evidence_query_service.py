"""Tests for applications.trading_intelligence.services.decision_evidence_query_service."""
import datetime

import pytest

from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
    EvidenceSource,
)


def _make_entry(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        attached_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    defaults.update(overrides)
    return EvidenceEntry(**defaults)


class _InMemoryEvidenceSource(EvidenceSource):
    """Minimal conforming implementation used only to exercise the service --
    not a real source, matching decision_query_service's own test pattern."""

    def __init__(self, evidence_by_decision=None):
        self._evidence_by_decision = evidence_by_decision or {}

    def get_evidence(self, decision_id):
        return list(self._evidence_by_decision.get(decision_id, []))


def test_evidence_source_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        EvidenceSource()


def test_incomplete_evidence_source_subclass_cannot_be_instantiated():
    class _Incomplete(EvidenceSource):
        pass  # get_evidence deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()


def test_get_evidence_returns_empty_list_when_source_has_no_evidence():
    service = DecisionEvidenceQueryService(_InMemoryEvidenceSource())

    assert service.get_evidence("dec-001") == []


def test_get_evidence_returns_entries_from_the_source():
    entry = _make_entry()
    source = _InMemoryEvidenceSource({"dec-001": [entry]})
    service = DecisionEvidenceQueryService(source)

    result = service.get_evidence("dec-001")

    assert result == [entry]


def test_get_evidence_returns_multiple_entries():
    entry_a = _make_entry(evidence_type="NEWS_SENTIMENT")
    entry_b = _make_entry(evidence_type="PRICE_ACTION")
    source = _InMemoryEvidenceSource({"dec-001": [entry_a, entry_b]})
    service = DecisionEvidenceQueryService(source)

    result = service.get_evidence("dec-001")

    assert result == [entry_a, entry_b]


def test_get_evidence_delegates_to_the_injected_source_not_a_shared_default():
    source_a = _InMemoryEvidenceSource({"dec-001": [_make_entry()]})
    source_b = _InMemoryEvidenceSource()
    service_a = DecisionEvidenceQueryService(source_a)
    service_b = DecisionEvidenceQueryService(source_b)

    assert service_a.get_evidence("dec-001") == [_make_entry()]
    assert service_b.get_evidence("dec-001") == []
