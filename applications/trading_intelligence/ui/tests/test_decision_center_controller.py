"""Tests for applications.trading_intelligence.ui.decision_center.controller."""
import datetime

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
    EvidenceSource,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
    GovernanceSource,
)
from applications.trading_intelligence.services.decision_query_service import (
    DecisionQueryService,
    DecisionSource,
)
from applications.trading_intelligence.ui.decision_center.controller import (
    DecisionCenterController,
)


class _InMemoryDecisionSource(DecisionSource):
    """Fake DecisionSource -- the real DecisionQueryService is used, only its
    dependency is faked, matching this codebase's established test pattern."""

    def __init__(self, decisions=None):
        self._decisions = decisions or {}

    def get_decision(self, decision_id):
        return self._decisions.get(decision_id)

    def list_decisions(self, decision_ids):
        return [self._decisions[d] for d in decision_ids if d in self._decisions]


class _InMemoryEvidenceSource(EvidenceSource):
    """Fake EvidenceSource -- the real DecisionEvidenceQueryService is used,
    only its dependency is faked, mirroring _InMemoryDecisionSource above."""

    def __init__(self, evidence_by_decision=None):
        self._evidence_by_decision = evidence_by_decision or {}

    def get_evidence(self, decision_id):
        return list(self._evidence_by_decision.get(decision_id, []))


class _InMemoryGovernanceSource(GovernanceSource):
    """Fake GovernanceSource -- the real DecisionGovernanceQueryService is
    used, only its dependency is faked, mirroring _InMemoryEvidenceSource
    above."""

    def __init__(self, governance_by_decision=None, approvals_by_decision=None):
        self._governance_by_decision = governance_by_decision or {}
        self._approvals_by_decision = approvals_by_decision or {}

    def get_governance(self, decision_id):
        return list(self._governance_by_decision.get(decision_id, []))

    def get_approvals(self, decision_id):
        return list(self._approvals_by_decision.get(decision_id, []))


def _make_contract(**overrides):
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
    return DecisionContract(**defaults)


def _make_entry(**overrides):
    defaults = dict(
        evidence_type="NEWS_SENTIMENT",
        source="newsapi",
        attached_at=datetime.datetime(2026, 8, 4, 12, 5, 0),
    )
    defaults.update(overrides)
    return EvidenceEntry(**defaults)


def _make_governance_entry(**overrides):
    defaults = dict(
        policy_id="pol-001",
        enabled=True,
        evaluated_at=datetime.datetime(2026, 8, 4, 12, 6, 0),
    )
    defaults.update(overrides)
    return GovernanceEntry(**defaults)


def _make_approval_entry(**overrides):
    defaults = dict(
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 4, 12, 7, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


def _make_controller(
    decisions=None,
    evidence_by_decision=None,
    governance_by_decision=None,
    approvals_by_decision=None,
):
    query_service = DecisionQueryService(_InMemoryDecisionSource(decisions or {}))
    evidence_query_service = DecisionEvidenceQueryService(
        _InMemoryEvidenceSource(evidence_by_decision or {})
    )
    governance_query_service = DecisionGovernanceQueryService(
        _InMemoryGovernanceSource(governance_by_decision or {}, approvals_by_decision or {})
    )
    return DecisionCenterController(query_service, evidence_query_service, governance_query_service)


def test_load_decisions_returns_a_decision_list_area():
    controller = _make_controller({"dec-001": _make_contract()})

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False
    assert list_area.decisions[0].decision_id == "dec-001"


def test_load_decisions_handles_empty_results():
    controller = _make_controller()

    list_area = controller.load_decisions(["missing-1"])

    assert list_area.is_empty is True
    assert list_area.empty_state_message == "No decisions recorded yet."


def test_load_decision_detail_returns_a_decision_detail_area():
    controller = _make_controller({"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.is_empty is False
    assert detail_area.decision.decision_id == "dec-001"


def test_load_decision_detail_handles_missing_decision():
    controller = _make_controller()

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True


def test_load_decisions_with_multiple_decisions_returns_them_all():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
        "dec-003": _make_contract(decision_id="dec-003", symbol="NVDA"),
    })

    list_area = controller.load_decisions(["dec-001", "dec-002", "dec-003"])

    assert [d.decision_id for d in list_area.decisions] == ["dec-001", "dec-002", "dec-003"]


def test_load_screen_selects_first_decision_by_default():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
    })

    screen = controller.load_screen(["dec-001", "dec-002"])

    assert screen.list_area.decisions[0].decision_id == "dec-001"
    assert screen.detail_area.decision.decision_id == "dec-001"


def test_load_screen_selects_explicit_decision_when_given():
    controller = _make_controller({
        "dec-001": _make_contract(decision_id="dec-001", symbol="AAPL"),
        "dec-002": _make_contract(decision_id="dec-002", symbol="MSFT"),
    })

    screen = controller.load_screen(["dec-001", "dec-002"], selected_id="dec-002")

    assert screen.detail_area.decision.decision_id == "dec-002"


def test_load_screen_handles_fully_empty_state():
    controller = _make_controller()

    screen = controller.load_screen([])

    assert screen.list_area.is_empty is True
    assert screen.detail_area.is_empty is True


def test_load_decision_detail_attaches_evidence_from_the_evidence_query_service():
    entry = _make_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        evidence_by_decision={"dec-001": [entry]},
    )

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.evidence == (entry,)


def test_load_decision_detail_returns_empty_evidence_when_none_attached():
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.evidence == ()


def test_load_decision_detail_does_not_query_evidence_for_a_missing_decision():
    class _AssertNotCalledEvidenceSource(EvidenceSource):
        def get_evidence(self, decision_id):
            raise AssertionError("evidence must not be queried for a missing decision")

    query_service = DecisionQueryService(_InMemoryDecisionSource())
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_AssertNotCalledEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.evidence == ()


def test_load_screen_default_selection_includes_evidence():
    """The default (no explicit selected_id) branch must route through the
    same evidence-attaching path as an explicit selection -- otherwise the
    first-row detail shown on initial load/refresh would silently omit
    evidence while row-click/manual-lookup selection would include it."""
    entry = _make_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        evidence_by_decision={"dec-001": [entry]},
    )

    screen = controller.load_screen(["dec-001"])

    assert screen.detail_area.evidence == (entry,)


def test_load_decisions_does_not_query_evidence():
    class _AssertNotCalledEvidenceSource(EvidenceSource):
        def get_evidence(self, decision_id):
            raise AssertionError("load_decisions must never query evidence")

    query_service = DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract()}))
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_AssertNotCalledEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
    )

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False


def test_load_decision_detail_attaches_governance_from_the_governance_query_service():
    entry = _make_governance_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        governance_by_decision={"dec-001": [entry]},
    )

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.governance == (entry,)


def test_load_decision_detail_returns_empty_governance_when_none_evaluated():
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.governance == ()


def test_load_decision_detail_attaches_approvals_from_the_governance_query_service():
    entry = _make_approval_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        approvals_by_decision={"dec-001": [entry]},
    )

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.approvals == (entry,)


def test_load_decision_detail_returns_empty_approvals_when_none_recorded():
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.approvals == ()


def test_load_decision_detail_does_not_query_governance_for_a_missing_decision():
    class _AssertNotCalledGovernanceSource(GovernanceSource):
        def get_governance(self, decision_id):
            raise AssertionError("governance must not be queried for a missing decision")

        def get_approvals(self, decision_id):
            raise AssertionError("approvals must not be queried for a missing decision")

    query_service = DecisionQueryService(_InMemoryDecisionSource())
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_AssertNotCalledGovernanceSource()),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.governance == ()
    assert detail_area.approvals == ()


def test_load_screen_default_selection_includes_governance_and_approvals():
    """Mirrors test_load_screen_default_selection_includes_evidence: the
    default (no explicit selected_id) branch must route through the same
    governance/approval-attaching path as an explicit selection."""
    governance_entry = _make_governance_entry()
    approval_entry = _make_approval_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        governance_by_decision={"dec-001": [governance_entry]},
        approvals_by_decision={"dec-001": [approval_entry]},
    )

    screen = controller.load_screen(["dec-001"])

    assert screen.detail_area.governance == (governance_entry,)
    assert screen.detail_area.approvals == (approval_entry,)


def test_load_decisions_does_not_query_governance():
    class _AssertNotCalledGovernanceSource(GovernanceSource):
        def get_governance(self, decision_id):
            raise AssertionError("load_decisions must never query governance")

        def get_approvals(self, decision_id):
            raise AssertionError("load_decisions must never query approvals")

    query_service = DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract()}))
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_AssertNotCalledGovernanceSource()),
    )

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False
