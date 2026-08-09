"""Tests for applications.trading_intelligence.adapters.sentinel_projection_decision_source."""
import datetime

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.projection_repository import ProjectionRepository

from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.services.decision_query_service import DecisionSource


class _InMemoryProjectionRepository(ProjectionRepository):
    """Minimal conforming fake -- no real backend, matching the pattern
    sentinel_engine's own 82 tests already use."""

    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


def _make_projection(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


def test_sentinel_projection_decision_source_is_a_decision_source():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())
    assert isinstance(source, DecisionSource)


class _BoomProjectionRepository(ProjectionRepository):
    def save(self, projection):
        raise AssertionError("must never be called")

    def get(self, decision_id):
        raise ConnectionError("simulated infrastructure failure")


def test_get_decision_translates_repository_exceptions():
    source = SentinelProjectionDecisionSource(_BoomProjectionRepository())

    with pytest.raises(TradingIntelligenceReadError) as excinfo:
        source.get_decision("dec-001")

    assert isinstance(excinfo.value.__cause__, ConnectionError)


def test_list_decisions_does_not_translate_repository_exceptions():
    """Deliberate scope boundary (Slice 5): only the single-decision detail
    read path is covered. list_decisions() (the Decision List/top-table
    path) is untouched until a future slice designs its own error
    semantics -- this test locks that decision in so it isn't silently
    changed later."""
    source = SentinelProjectionDecisionSource(_BoomProjectionRepository())

    with pytest.raises(ConnectionError):
        source.list_decisions(["dec-001"])


def test_get_decision_returns_none_when_repository_has_no_projection():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.get_decision("missing-decision") is None


def test_get_decision_returns_a_decision_contract():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection())
    source = SentinelProjectionDecisionSource(repository)

    result = source.get_decision("dec-001")

    assert isinstance(result, DecisionContract)


def test_get_decision_maps_every_field_correctly():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection())
    source = SentinelProjectionDecisionSource(repository)

    result = source.get_decision("dec-001")

    assert result.decision_id == "dec-001"
    assert result.symbol == "AAPL"
    assert result.action == "BUY"
    assert result.status == DecisionState.DECISION_CREATED
    assert result.confidence == 0.78
    assert result.evidence_reference == "evidence-001"
    assert result.risk_reference == "risk-001"
    assert result.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_get_decision_reads_from_the_injected_repository_not_a_shared_default():
    repo_a = _InMemoryProjectionRepository()
    repo_a.save(_make_projection())
    repo_b = _InMemoryProjectionRepository()
    source_a = SentinelProjectionDecisionSource(repo_a)
    source_b = SentinelProjectionDecisionSource(repo_b)

    assert source_a.get_decision("dec-001") is not None
    assert source_b.get_decision("dec-001") is None


def test_source_only_calls_get_never_save():
    """Read-only: the adapter must never call ProjectionRepository.save()."""

    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {"dec-001": _make_projection()}

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelProjectionDecisionSource must never call save()")

    source = SentinelProjectionDecisionSource(_AssertNoSaveRepository())

    source.get_decision("dec-001")
    source.list_decisions(["dec-001"])


def test_list_decisions_returns_empty_list_when_no_ids_requested():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.list_decisions([]) == []


def test_list_decisions_returns_empty_list_when_repository_has_no_matches():
    source = SentinelProjectionDecisionSource(_InMemoryProjectionRepository())

    assert source.list_decisions(["missing-1", "missing-2"]) == []


def test_list_decisions_returns_multiple_contracts():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001", symbol="AAPL"))
    repository.save(_make_projection(decision_id="dec-002", symbol="MSFT"))
    source = SentinelProjectionDecisionSource(repository)

    results = source.list_decisions(["dec-001", "dec-002"])

    assert [r.decision_id for r in results] == ["dec-001", "dec-002"]
    assert [r.symbol for r in results] == ["AAPL", "MSFT"]
    assert all(isinstance(r, DecisionContract) for r in results)


def test_list_decisions_skips_ids_the_repository_does_not_have():
    repository = _InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001"))
    source = SentinelProjectionDecisionSource(repository)

    results = source.list_decisions(["dec-001", "missing-decision"])

    assert len(results) == 1
    assert results[0].decision_id == "dec-001"


def test_list_decisions_never_calls_save():
    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {"dec-001": _make_projection()}

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("list_decisions must never call save()")

    source = SentinelProjectionDecisionSource(_AssertNoSaveRepository())

    source.list_decisions(["dec-001", "missing"])
