"""End-to-end integration test for the Decision Center MVP data flow:

    ProjectionRepository (fake)
            |
            v
    SentinelProjectionDecisionSource
            |
            v
    DecisionQueryService
            |
            v
    DecisionCenterController
            |
            v
    DecisionCenterScreen

Every layer above already existed and was tested in isolation (Phases 3C,
3H, 3I). This file proves they compose correctly end-to-end, driven by real
sentinel_engine.projections.DecisionProjection objects rather than
hand-built DecisionContract/DecisionView values or mock_data.py. No
production code was changed to make this pass -- every class already
supported this wiring by construction (dependency injection throughout).

mock_data.py is untouched and remains available for demos, per this task's
constraint -- this file does not replace it, it adds a second, real-service-
backed path alongside it.
"""
import datetime

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.projection_repository import ProjectionRepository

from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
    EvidenceSource,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
    GovernanceSource,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.tests.fakes import InMemoryProjectionRepository
from applications.trading_intelligence.ui.decision_center.controller import (
    DecisionCenterController,
)


class _NoEvidenceSource(EvidenceSource):
    """This file proves the Projection -> Contract -> View chain; evidence
    wiring has its own dedicated tests (test_sentinel_evidence_source.py,
    test_decision_evidence_query_service.py, test_bootstrap.py), so this
    collaborator is a deliberately empty stand-in, not a real source."""

    def get_evidence(self, decision_id):
        return []


class _NoGovernanceSource(GovernanceSource):
    """Same rationale as _NoEvidenceSource above, for governance/approval
    wiring -- has its own dedicated tests (test_sentinel_governance_source.py,
    test_decision_governance_query_service.py, test_bootstrap.py)."""

    def get_governance(self, decision_id):
        return []

    def get_approvals(self, decision_id):
        return []


class _NoAuditSource:
    """Same rationale as _NoEvidenceSource above, for the audit trail --
    has its own dedicated tests (test_sentinel_audit_source.py,
    test_bootstrap.py). Audit trail is wired directly to SentinelAuditSource
    (no services/ wrapper -- see controller.py's own docstring on this
    accepted asymmetry), so this stand-in is a plain class, not an ABC
    subclass."""

    def get_audit_trail(self, decision_id):
        return []


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


def _build_controller(repository: ProjectionRepository) -> DecisionCenterController:
    source = SentinelProjectionDecisionSource(repository)
    query_service = DecisionQueryService(source)
    evidence_query_service = DecisionEvidenceQueryService(_NoEvidenceSource())
    governance_query_service = DecisionGovernanceQueryService(_NoGovernanceSource())
    return DecisionCenterController(
        query_service, evidence_query_service, governance_query_service, _NoAuditSource(),
    )


def test_empty_repository_produces_an_empty_screen():
    controller = _build_controller(InMemoryProjectionRepository())

    screen = controller.load_screen(["dec-001"])

    assert screen.list_area.is_empty is True
    assert screen.list_area.empty_state_message == "No decisions recorded yet."
    assert screen.detail_area.is_empty is True


def test_one_decision_produces_a_complete_screen():
    repository = InMemoryProjectionRepository()
    repository.save(_make_projection())

    controller = _build_controller(repository)
    screen = controller.load_screen(["dec-001"])

    assert screen.list_area.is_empty is False
    assert len(screen.list_area.decisions) == 1
    assert screen.list_area.decisions[0].decision_id == "dec-001"
    assert screen.detail_area.decision.decision_id == "dec-001"


def test_multiple_decisions_all_appear_in_the_list_area():
    repository = InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001", symbol="AAPL"))
    repository.save(_make_projection(decision_id="dec-002", symbol="MSFT"))
    repository.save(_make_projection(decision_id="dec-003", symbol="NVDA"))

    controller = _build_controller(repository)
    screen = controller.load_screen(["dec-001", "dec-002", "dec-003"])

    assert [d.decision_id for d in screen.list_area.decisions] == [
        "dec-001",
        "dec-002",
        "dec-003",
    ]


def test_decision_detail_loads_the_explicitly_selected_decision():
    repository = InMemoryProjectionRepository()
    repository.save(_make_projection(decision_id="dec-001", symbol="AAPL"))
    repository.save(_make_projection(decision_id="dec-002", symbol="MSFT"))

    controller = _build_controller(repository)
    screen = controller.load_screen(["dec-001", "dec-002"], selected_id="dec-002")

    assert screen.detail_area.decision.decision_id == "dec-002"
    assert screen.detail_area.decision.symbol == "MSFT"


def test_controller_produces_a_correctly_formatted_screen_model_from_real_projection_data():
    """Traces formatting all the way from a real DecisionProjection, not a
    hand-built DecisionContract/DecisionView -- confidence=0.78 -> "78%",
    status=DecisionState.DECISION_CREATED -> "Decision Created", timestamp formatting."""
    repository = InMemoryProjectionRepository()
    repository.save(
        _make_projection(
            decision_id="dec-001",
            confidence=0.78,
            status=DecisionState.DECISION_CREATED,
            updated_at=datetime.datetime(2026, 8, 4, 9, 35, 0),
        )
    )

    controller = _build_controller(repository)
    screen = controller.load_screen(["dec-001"])

    assert screen.detail_area.confidence_display == "78%"
    assert screen.detail_area.status_display == "Decision Created"
    assert screen.detail_area.timestamp_display == "2026-08-04 04:35 CDT"


def test_no_writes_occur_anywhere_in_the_chain():
    """Read-only, checked as a fact: the repository's save() must never be
    called by any layer between it and the controller."""

    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {
                "dec-001": _make_projection(decision_id="dec-001"),
                "dec-002": _make_projection(decision_id="dec-002"),
            }

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("no layer in this chain may call ProjectionRepository.save()")

    controller = _build_controller(_AssertNoSaveRepository())

    controller.load_screen(["dec-001", "dec-002"], selected_id="dec-002")
    controller.load_decisions(["dec-001"])
    controller.load_decision_detail("dec-002")
