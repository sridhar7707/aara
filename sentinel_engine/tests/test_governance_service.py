"""Tests for sentinel_engine.services.governance_service.GovernanceService."""
import datetime

from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.governance.policy import Policy
from sentinel_engine.governance.approval import Approval
from sentinel_engine.events.event_types import EventType
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository


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


def _make_policy(**overrides):
    defaults = dict(
        policy_id="pol-001",
        name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    )
    defaults.update(overrides)
    return Policy(**defaults)


def _make_approval(**overrides):
    defaults = dict(
        approval_id="apr-001",
        decision_id="dec-001",
        status="APPROVED",
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def _make_projection(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=EventType.DECISION_CREATED.value,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


def _make_service():
    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()
    service = GovernanceService(ledger_repository, projection_repository)
    return service, ledger_repository, projection_repository


def test_get_policy_returns_none_when_not_registered():
    service, _, _ = _make_service()

    assert service.get_policy("missing-policy") is None


def test_register_policy_then_get_policy_returns_it():
    service, _, _ = _make_service()
    policy = _make_policy()

    service.register_policy(policy)

    assert service.get_policy("pol-001") == policy


def test_is_policy_enabled_reflects_the_policy_flag():
    service, _, _ = _make_service()
    service.register_policy(_make_policy(enabled=False))

    assert service.is_policy_enabled("pol-001") is False


def test_is_policy_enabled_returns_false_for_unknown_policy():
    service, _, _ = _make_service()

    assert service.is_policy_enabled("missing-policy") is False


def test_get_approval_returns_none_when_not_recorded():
    service, _, _ = _make_service()

    assert service.get_approval("dec-001") is None


def test_record_approval_then_get_approval_returns_it():
    service, _, _ = _make_service()
    approval = _make_approval()

    service.record_approval(approval)

    assert service.get_approval("dec-001") == approval


def test_governance_service_does_not_expose_internal_storage_attributes():
    service, _, _ = _make_service()

    assert not hasattr(service, "policies")
    assert not hasattr(service, "approvals")


def test_evaluate_policy_returns_true_for_enabled_policy():
    service, _, _ = _make_service()
    service.register_policy(_make_policy(enabled=True))

    assert service.evaluate_policy("dec-001", "pol-001") is True


def test_evaluate_policy_writes_governance_evaluated_event_for_enabled_policy():
    service, ledger_repository, _ = _make_service()
    service.register_policy(_make_policy(enabled=True))

    service.evaluate_policy("dec-001", "pol-001")

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.GOVERNANCE_EVALUATED
    assert events[0].payload["decision_id"] == "dec-001"
    assert events[0].payload["policy_id"] == "pol-001"
    assert events[0].payload["enabled"] is True


def test_evaluate_policy_advances_projection_status_when_projection_exists():
    service, _, projection_repository = _make_service()
    service.register_policy(_make_policy(enabled=True))
    projection_repository.save(_make_projection())

    service.evaluate_policy("dec-001", "pol-001")

    projection = projection_repository.get("dec-001")
    assert projection is not None
    assert projection.status == EventType.GOVERNANCE_EVALUATED.value
    # Unrelated fields preserved by the read-modify-write, not overwritten.
    assert projection.symbol == "AAPL"
    assert projection.action == "BUY"
    assert projection.confidence == 0.78


def test_evaluate_policy_returns_false_for_disabled_policy():
    service, _, _ = _make_service()
    service.register_policy(_make_policy(enabled=False))

    assert service.evaluate_policy("dec-001", "pol-001") is False


def test_evaluate_policy_writes_governance_evaluated_event_for_disabled_policy():
    service, ledger_repository, _ = _make_service()
    service.register_policy(_make_policy(enabled=False))

    service.evaluate_policy("dec-001", "pol-001")

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.GOVERNANCE_EVALUATED
    assert events[0].payload["enabled"] is False


def test_evaluate_policy_returns_false_for_unknown_policy():
    service, _, _ = _make_service()

    assert service.evaluate_policy("dec-001", "missing-policy") is False


def test_evaluate_policy_writes_auditable_event_for_unknown_policy():
    service, ledger_repository, _ = _make_service()

    service.evaluate_policy("dec-001", "missing-policy")

    events = ledger_repository.get_events()
    assert len(events) == 1
    assert events[0].event_type == EventType.GOVERNANCE_EVALUATED
    assert events[0].payload["decision_id"] == "dec-001"
    assert events[0].payload["policy_id"] == "missing-policy"
    # Unknown policies are indistinguishable from disabled ones in
    # is_policy_enabled()'s existing behavior; evaluate_policy preserves
    # that rather than special-casing "unknown" as a different outcome.
    assert events[0].payload["enabled"] is False


def test_evaluate_policy_does_not_create_a_projection_when_none_exists():
    service, _, projection_repository = _make_service()
    service.register_policy(_make_policy(enabled=True))

    service.evaluate_policy("dec-001", "pol-001")

    assert projection_repository.get("dec-001") is None
