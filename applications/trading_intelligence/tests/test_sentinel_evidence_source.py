"""Tests for applications.trading_intelligence.adapters.sentinel_evidence_source."""
import datetime

from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService

from applications.trading_intelligence.adapters.sentinel_evidence_source import SentinelEvidenceSource
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.services.decision_evidence_query_service import EvidenceSource


class _InMemoryLedgerStore(LedgerStore):
    def __init__(self):
        self._events = []

    def append(self, event):
        self._events.append(event)

    def read_all(self):
        return list(self._events)


class _InMemoryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


def _make_decision(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        timestamp=datetime.datetime(2026, 8, 8, 9, 0, 0),
        confidence=0.82,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
    )
    defaults.update(overrides)
    return Decision(**defaults)


def _make_evidence(**overrides):
    defaults = dict(
        evidence_id="ev-001",
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        data={"score": 0.62},
        collected_at=datetime.datetime(2026, 8, 8, 9, 5, 0),
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def _make_wiring():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    decision_query = DecisionQuery(ledger_repository, projection_repository)
    source = SentinelEvidenceSource(decision_query)
    return decision_service, evidence_service, source


def test_sentinel_evidence_source_is_an_evidence_source():
    _, _, source = _make_wiring()

    assert isinstance(source, EvidenceSource)


def test_get_evidence_maps_summary_to_entry_correctly():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    evidence_service.associate_evidence("dec-001", _make_evidence())

    result = source.get_evidence("dec-001")

    assert len(result) == 1
    assert isinstance(result[0], EvidenceEntry)


def test_get_evidence_preserves_evidence_type():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    evidence_service.associate_evidence("dec-001", _make_evidence(evidence_type="PRICE_ACTION"))

    result = source.get_evidence("dec-001")

    assert result[0].evidence_type == "PRICE_ACTION"


def test_get_evidence_preserves_source():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    evidence_service.associate_evidence("dec-001", _make_evidence(source="alpaca"))

    result = source.get_evidence("dec-001")

    assert result[0].source == "alpaca"


def test_get_evidence_preserves_attached_at():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    attached_at = datetime.datetime(2026, 8, 8, 9, 5, 0)
    evidence_service.associate_evidence("dec-001", _make_evidence(collected_at=attached_at))

    result = source.get_evidence("dec-001")

    assert result[0].attached_at == attached_at


def test_get_evidence_returns_empty_list_for_a_decision_with_no_evidence():
    decision_service, _, source = _make_wiring()
    decision_service.create_decision(_make_decision())

    assert source.get_evidence("dec-001") == []


def test_get_evidence_returns_empty_list_for_a_missing_decision():
    _, _, source = _make_wiring()

    assert source.get_evidence("missing-decision") == []


def test_get_evidence_returns_multiple_entries_in_order():
    decision_service, evidence_service, source = _make_wiring()
    decision_service.create_decision(_make_decision())
    evidence_service.associate_evidence(
        "dec-001",
        _make_evidence(
            evidence_id="ev-001", evidence_type="NEWS_SENTIMENT",
            collected_at=datetime.datetime(2026, 8, 8, 9, 1, 0),
        ),
    )
    evidence_service.associate_evidence(
        "dec-001",
        _make_evidence(
            evidence_id="ev-002", evidence_type="PRICE_ACTION",
            collected_at=datetime.datetime(2026, 8, 8, 9, 2, 0),
        ),
    )

    result = source.get_evidence("dec-001")

    assert [entry.evidence_type for entry in result] == ["NEWS_SENTIMENT", "PRICE_ACTION"]


def test_get_evidence_never_calls_a_write_operation():
    """Read-only: the adapter must never append a ledger event or save a
    projection. Setup writes through real repositories first, then wraps
    the same underlying data in read-delegating, write-forbidding fakes and
    exercises get_evidence() against those -- any write call fails the test."""
    real_store = _InMemoryLedgerStore()
    real_ledger_repository = LedgerRepository(real_store)
    real_projection_repository = _InMemoryProjectionRepository()
    decision_service = DecisionService(real_ledger_repository, real_projection_repository)
    evidence_service = EvidenceService(real_ledger_repository, real_projection_repository)
    decision_service.create_decision(_make_decision())
    evidence_service.associate_evidence("dec-001", _make_evidence())

    class _AssertNoAppendStore(LedgerStore):
        def append(self, event):
            raise AssertionError("SentinelEvidenceSource must never append ledger events")

        def read_all(self):
            return real_store.read_all()

    class _AssertNoSaveProjectionRepository(ProjectionRepository):
        def get(self, decision_id):
            return real_projection_repository.get(decision_id)

        def save(self, projection):
            raise AssertionError("SentinelEvidenceSource must never save a projection")

    read_only_query = DecisionQuery(
        LedgerRepository(_AssertNoAppendStore()),
        _AssertNoSaveProjectionRepository(),
    )
    source = SentinelEvidenceSource(read_only_query)

    result = source.get_evidence("dec-001")

    assert len(result) == 1
