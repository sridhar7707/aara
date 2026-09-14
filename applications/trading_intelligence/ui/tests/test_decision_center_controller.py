"""Tests for applications.trading_intelligence.ui.decision_center.controller."""
import datetime

from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.audit_entry import AuditEntry
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
from applications.trading_intelligence.ui.decision_center.screen import ReadStatus


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


class _InMemoryAuditSource:
    """Fake audit source -- controller.py holds this directly (no services/
    wrapper for audit trail; see its own docstring on this accepted
    asymmetry), so this is a plain class, not an ABC subclass."""

    def __init__(self, audit_trail_by_decision=None):
        self._audit_trail_by_decision = audit_trail_by_decision or {}

    def get_audit_trail(self, decision_id):
        return list(self._audit_trail_by_decision.get(decision_id, []))


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
        evidence_id="ev-001",
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
        approval_id="apr-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        approved_at=datetime.datetime(2026, 8, 4, 12, 7, 0),
    )
    defaults.update(overrides)
    return ApprovalEntry(**defaults)


def _make_audit_entry(**overrides):
    defaults = dict(
        event_id="evt-001",
        event_type="DECISION_CREATED",
        created_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
        payload={"decision_id": "dec-001"},
    )
    defaults.update(overrides)
    return AuditEntry(**defaults)


def _make_controller(
    decisions=None,
    evidence_by_decision=None,
    governance_by_decision=None,
    approvals_by_decision=None,
    audit_trail_by_decision=None,
):
    query_service = DecisionQueryService(_InMemoryDecisionSource(decisions or {}))
    evidence_query_service = DecisionEvidenceQueryService(
        _InMemoryEvidenceSource(evidence_by_decision or {})
    )
    governance_query_service = DecisionGovernanceQueryService(
        _InMemoryGovernanceSource(governance_by_decision or {}, approvals_by_decision or {})
    )
    audit_source = _InMemoryAuditSource(audit_trail_by_decision or {})
    return DecisionCenterController(
        query_service, evidence_query_service, governance_query_service, audit_source,
    )


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


def test_load_decision_detail_missing_decision_is_ok_not_error():
    """EMPTY (not-found) must stay distinguishable from ERROR."""
    controller = _make_controller()

    detail_area = controller.load_decision_detail("does-not-exist")

    assert detail_area.decision is None
    assert detail_area.decision_status is ReadStatus.OK


def test_load_decision_detail_carries_raw_evidence_and_risk_reference():
    controller = _make_controller(
        {"dec-001": _make_contract(evidence_reference="evidence-001", risk_reference="risk-001")}
    )

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.evidence_reference == "evidence-001"
    assert detail_area.risk_reference == "risk-001"


def test_load_decision_detail_leaves_references_none_for_a_missing_decision():
    controller = _make_controller()

    detail_area = controller.load_decision_detail("does-not-exist")

    assert detail_area.evidence_reference is None
    assert detail_area.risk_reference is None


class _BoomDecisionSource(DecisionSource):
    def get_decision(self, decision_id):
        raise TradingIntelligenceReadError("boom")

    def list_decisions(self, decision_ids):
        raise AssertionError("must not be called by load_decision_detail")


class _StrictEvidenceSource(EvidenceSource):
    def get_evidence(self, decision_id):
        raise AssertionError("evidence must not be queried when decision read fails")


class _StrictGovernanceSource(GovernanceSource):
    def get_governance(self, decision_id):
        raise AssertionError("governance must not be queried when decision read fails")

    def get_approvals(self, decision_id):
        raise AssertionError("approvals must not be queried when decision read fails")


class _StrictAuditSource:
    def get_audit_trail(self, decision_id):
        raise AssertionError("audit trail must not be queried when decision read fails")


class _BoomEvidenceSource(EvidenceSource):
    def get_evidence(self, decision_id):
        raise TradingIntelligenceReadError("boom")


class _BoomAuditSource:
    def get_audit_trail(self, decision_id):
        raise TradingIntelligenceReadError("boom")


class _BoomGovernanceSource(GovernanceSource):
    def __init__(self, fail_governance=False, fail_approvals=False):
        self._fail_governance = fail_governance
        self._fail_approvals = fail_approvals

    def get_governance(self, decision_id):
        if self._fail_governance:
            raise TradingIntelligenceReadError("boom")
        return []

    def get_approvals(self, decision_id):
        if self._fail_approvals:
            raise TradingIntelligenceReadError("boom")
        return []


def test_load_decision_detail_reports_decision_error_without_querying_evidence_or_governance():
    controller = DecisionCenterController(
        DecisionQueryService(_BoomDecisionSource()),
        DecisionEvidenceQueryService(_StrictEvidenceSource()),
        DecisionGovernanceQueryService(_StrictGovernanceSource()),
        _StrictAuditSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is None
    assert detail.decision_status is ReadStatus.ERROR


def test_load_decision_detail_reports_evidence_error_but_keeps_decision_and_governance():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_BoomEvidenceSource()),
        DecisionGovernanceQueryService(
            _InMemoryGovernanceSource(
                {"dec-001": [_make_governance_entry()]},
                {"dec-001": [_make_approval_entry()]},
            )
        ),
        _InMemoryAuditSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.decision_status is ReadStatus.OK
    assert detail.evidence == ()
    assert detail.evidence_status is ReadStatus.ERROR
    assert detail.governance == (_make_governance_entry(),)
    assert detail.governance_status is ReadStatus.OK
    assert detail.approvals == (_make_approval_entry(),)
    assert detail.approvals_status is ReadStatus.OK


def test_load_decision_detail_reports_governance_error_independently_of_approvals():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_BoomGovernanceSource(fail_governance=True)),
        _InMemoryAuditSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.governance == ()
    assert detail.governance_status is ReadStatus.ERROR
    assert detail.approvals == ()
    assert detail.approvals_status is ReadStatus.OK


def test_load_decision_detail_reports_approvals_error_independently_of_governance():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_BoomGovernanceSource(fail_approvals=True)),
        _InMemoryAuditSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.approvals == ()
    assert detail.approvals_status is ReadStatus.ERROR
    assert detail.governance == ()
    assert detail.governance_status is ReadStatus.OK


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
        _InMemoryAuditSource(),
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
        _InMemoryAuditSource(),
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
        _InMemoryAuditSource(),
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
        _InMemoryAuditSource(),
    )

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False


def test_load_decision_detail_attaches_audit_trail_from_the_audit_query_service():
    entry = _make_audit_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        audit_trail_by_decision={"dec-001": [entry]},
    )

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.audit_trail == (entry,)


def test_load_decision_detail_returns_empty_audit_trail_when_none_recorded():
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail_area = controller.load_decision_detail("dec-001")

    assert detail_area.audit_trail == ()


def test_load_decision_detail_does_not_query_audit_trail_for_a_missing_decision():
    class _AssertNotCalledAuditSource:
        def get_audit_trail(self, decision_id):
            raise AssertionError("audit trail must not be queried for a missing decision")

    query_service = DecisionQueryService(_InMemoryDecisionSource())
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _AssertNotCalledAuditSource(),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.audit_trail == ()


def test_load_decision_detail_reports_audit_trail_error_but_keeps_other_concerns():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource({"dec-001": [_make_entry()]})),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _BoomAuditSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.evidence == (_make_entry(),)
    assert detail.evidence_status is ReadStatus.OK
    assert detail.audit_trail == ()
    assert detail.audit_trail_status is ReadStatus.ERROR


def test_load_screen_default_selection_includes_audit_trail():
    entry = _make_audit_entry()
    controller = _make_controller(
        decisions={"dec-001": _make_contract()},
        audit_trail_by_decision={"dec-001": [entry]},
    )

    screen = controller.load_screen(["dec-001"])

    assert screen.detail_area.audit_trail == (entry,)


def test_load_decisions_does_not_query_audit_trail():
    class _AssertNotCalledAuditSource:
        def get_audit_trail(self, decision_id):
            raise AssertionError("load_decisions must never query the audit trail")

    query_service = DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract()}))
    controller = DecisionCenterController(
        query_service,
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _AssertNotCalledAuditSource(),
    )

    list_area = controller.load_decisions(["dec-001"])

    assert list_area.is_empty is False


class _InMemoryNewsCacheDiffSource:
    """Fake news-cache diff collaborator -- duck-typed like
    _InMemoryAuditSource above (no services/ wrapper, no ABC)."""

    def __init__(self, diff_by_decision=None):
        self._diff_by_decision = diff_by_decision or {}

    def get_diff(self, symbol, decision_timestamp):
        return self._diff_by_decision.get(symbol)


class _BoomNewsCacheDiffSource:
    def get_diff(self, symbol, decision_timestamp):
        raise TradingIntelligenceReadError("boom")


def test_load_decision_detail_attaches_news_cache_diff_when_collaborator_present():
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract(symbol="AAPL")})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        news_cache_diff_source=_InMemoryNewsCacheDiffSource({"AAPL": "some-diff"}),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.news_cache_diff == "some-diff"
    assert detail.news_cache_diff_status is ReadStatus.OK


def test_load_decision_detail_news_cache_diff_is_none_when_collaborator_absent():
    """No news_cache_diff_source injected -- the Sentinel path's existing
    4-arg construction must keep working unchanged, with an honest OK/None
    result, never an error, and never a read attempt."""
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail = controller.load_decision_detail("dec-001")

    assert detail.news_cache_diff is None
    assert detail.news_cache_diff_status is ReadStatus.OK


def test_load_decision_detail_reports_news_cache_diff_error_but_keeps_other_concerns():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource({"dec-001": [_make_entry()]})),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        news_cache_diff_source=_BoomNewsCacheDiffSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.evidence == (_make_entry(),)
    assert detail.evidence_status is ReadStatus.OK
    assert detail.news_cache_diff is None
    assert detail.news_cache_diff_status is ReadStatus.ERROR


def test_load_decision_detail_does_not_query_news_cache_diff_for_a_missing_decision():
    class _AssertNotCalledNewsCacheDiffSource:
        def get_diff(self, symbol, decision_timestamp):
            raise AssertionError("news cache diff must not be queried for a missing decision")

    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource()),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        news_cache_diff_source=_AssertNotCalledNewsCacheDiffSource(),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.news_cache_diff is None
    assert detail_area.news_cache_diff_status is ReadStatus.OK


class _InMemoryRecommendationDiffSource:
    """Fake recommendation diff collaborator -- duck-typed like
    _InMemoryNewsCacheDiffSource above (no services/ wrapper, no ABC)."""

    def __init__(self, diff_by_decision=None):
        self._diff_by_decision = diff_by_decision or {}

    def get_diff(self, symbol, decision_timestamp):
        return self._diff_by_decision.get(symbol)


class _BoomRecommendationDiffSource:
    def get_diff(self, symbol, decision_timestamp):
        raise TradingIntelligenceReadError("boom")


def test_load_decision_detail_attaches_recommendation_diff_when_collaborator_present():
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract(symbol="AAPL")})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        recommendation_diff_source=_InMemoryRecommendationDiffSource({"AAPL": "some-rec-diff"}),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.recommendation_diff == "some-rec-diff"
    assert detail.recommendation_diff_status is ReadStatus.OK


def test_load_decision_detail_recommendation_diff_is_none_when_collaborator_absent():
    """No recommendation_diff_source injected -- the Sentinel path's
    existing construction must keep working unchanged, with an honest
    OK/None result, never an error, and never a read attempt."""
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail = controller.load_decision_detail("dec-001")

    assert detail.recommendation_diff is None
    assert detail.recommendation_diff_status is ReadStatus.OK


def test_load_decision_detail_reports_recommendation_diff_error_but_keeps_other_concerns():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource({"dec-001": [_make_entry()]})),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        recommendation_diff_source=_BoomRecommendationDiffSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.evidence == (_make_entry(),)
    assert detail.evidence_status is ReadStatus.OK
    assert detail.recommendation_diff is None
    assert detail.recommendation_diff_status is ReadStatus.ERROR


def test_load_decision_detail_does_not_query_recommendation_diff_for_a_missing_decision():
    class _AssertNotCalledRecommendationDiffSource:
        def get_diff(self, symbol, decision_timestamp):
            raise AssertionError(
                "recommendation diff must not be queried for a missing decision"
            )

    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource()),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        recommendation_diff_source=_AssertNotCalledRecommendationDiffSource(),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.recommendation_diff is None
    assert detail_area.recommendation_diff_status is ReadStatus.OK


class _InMemoryEarningsSource:
    """Fake earnings collaborator -- duck-typed like
    _InMemoryRecommendationDiffSource above (no services/ wrapper, no
    ABC). get_snapshot(symbol) only -- no date, no diff."""

    def __init__(self, snapshot_by_symbol=None):
        self._snapshot_by_symbol = snapshot_by_symbol or {}

    def get_snapshot(self, symbol):
        return self._snapshot_by_symbol.get(symbol)


class _BoomEarningsSource:
    def get_snapshot(self, symbol):
        raise TradingIntelligenceReadError("boom")


def test_load_decision_detail_attaches_earnings_snapshot_when_collaborator_present():
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract(symbol="AVGO")})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        earnings_source=_InMemoryEarningsSource({"AVGO": "some-earnings-snapshot"}),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.earnings_snapshot == "some-earnings-snapshot"
    assert detail.earnings_status is ReadStatus.OK


def test_load_decision_detail_earnings_snapshot_is_none_when_collaborator_absent():
    """No earnings_source injected -- the Sentinel path's existing
    construction must keep working unchanged, with an honest OK/None
    result, never an error, and never a read attempt."""
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail = controller.load_decision_detail("dec-001")

    assert detail.earnings_snapshot is None
    assert detail.earnings_status is ReadStatus.OK


def test_load_decision_detail_reports_earnings_error_but_keeps_other_concerns():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource({"dec-001": [_make_entry()]})),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        earnings_source=_BoomEarningsSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.evidence == (_make_entry(),)
    assert detail.evidence_status is ReadStatus.OK
    assert detail.earnings_snapshot is None
    assert detail.earnings_status is ReadStatus.ERROR


def test_load_decision_detail_does_not_query_earnings_for_a_missing_decision():
    class _AssertNotCalledEarningsSource:
        def get_snapshot(self, symbol):
            raise AssertionError("earnings must not be queried for a missing decision")

    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource()),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        earnings_source=_AssertNotCalledEarningsSource(),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.earnings_snapshot is None
    assert detail_area.earnings_status is ReadStatus.OK


# --- Decision -> Outcome linkage ------------------------------------------


class _InMemoryOutcomeSource:
    """Fake outcome collaborator -- duck-typed like _InMemoryEarningsSource
    above (no services/ wrapper, no ABC). get_outcome(decision_id) only --
    no symbol, no timestamp, since the decision_id is already known."""

    def __init__(self, outcome_by_decision_id=None):
        self._outcome_by_decision_id = outcome_by_decision_id or {}

    def get_outcome(self, decision_id):
        return self._outcome_by_decision_id.get(decision_id)


class _BoomOutcomeSource:
    def get_outcome(self, decision_id):
        raise TradingIntelligenceReadError("boom")


def test_load_decision_detail_attaches_outcome_when_collaborator_present():
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": _make_contract()})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        outcome_source=_InMemoryOutcomeSource({"dec-001": "some-outcome"}),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.outcome == "some-outcome"
    assert detail.outcome_status is ReadStatus.OK


def test_load_decision_detail_outcome_is_none_when_collaborator_absent():
    """No outcome_source injected -- the Sentinel path's existing
    construction must keep working unchanged, with an honest OK/None
    result, never an error, and never a read attempt."""
    controller = _make_controller(decisions={"dec-001": _make_contract()})

    detail = controller.load_decision_detail("dec-001")

    assert detail.outcome is None
    assert detail.outcome_status is ReadStatus.OK


def test_load_decision_detail_reports_outcome_error_but_keeps_other_concerns():
    contract = _make_contract()
    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource({"dec-001": contract})),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource({"dec-001": [_make_entry()]})),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        outcome_source=_BoomOutcomeSource(),
    )

    detail = controller.load_decision_detail("dec-001")

    assert detail.decision is not None
    assert detail.evidence == (_make_entry(),)
    assert detail.evidence_status is ReadStatus.OK
    assert detail.outcome is None
    assert detail.outcome_status is ReadStatus.ERROR


def test_load_decision_detail_does_not_query_outcome_for_a_missing_decision():
    class _AssertNotCalledOutcomeSource:
        def get_outcome(self, decision_id):
            raise AssertionError("outcome must not be queried for a missing decision")

    controller = DecisionCenterController(
        DecisionQueryService(_InMemoryDecisionSource()),
        DecisionEvidenceQueryService(_InMemoryEvidenceSource()),
        DecisionGovernanceQueryService(_InMemoryGovernanceSource()),
        _InMemoryAuditSource(),
        outcome_source=_AssertNotCalledOutcomeSource(),
    )

    detail_area = controller.load_decision_detail("missing-decision")

    assert detail_area.is_empty is True
    assert detail_area.outcome is None
    assert detail_area.outcome_status is ReadStatus.OK
