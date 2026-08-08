"""Tests for sentinel_engine.presentation.investor_presenter.InvestorPresenter."""
import datetime

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.presentation.investor_presenter import (
    DecisionCenterViewModel,
    InvestorPresenter,
    MorningBriefView,
)


class _RecentDecisionActivity:
    def __init__(self, decision_id, status, last_activity_at):
        self.decision_id = decision_id
        self.status = status
        self.last_activity_at = last_activity_at


class _MorningBrief:
    def __init__(self, total_decisions, decisions_by_status, recent_decisions):
        self.total_decisions = total_decisions
        self.decisions_by_status = decisions_by_status
        self.recent_decisions = recent_decisions


class _EvidenceSummary:
    def __init__(self, evidence_id, evidence_type, source, attached_at):
        self.evidence_id = evidence_id
        self.evidence_type = evidence_type
        self.source = source
        self.attached_at = attached_at


class _GovernanceEvaluationSummary:
    def __init__(self, policy_id, enabled, evaluated_at):
        self.policy_id = policy_id
        self.enabled = enabled
        self.evaluated_at = evaluated_at


class _ApprovalSummary:
    def __init__(self, approval_id, status, approved_by, approved_at):
        self.approval_id = approval_id
        self.status = status
        self.approved_by = approved_by
        self.approved_at = approved_at


class _TimelineEventType:
    def __init__(self, value):
        self.value = value


class _TimelineEvent:
    def __init__(self, event_type, created_at):
        self.event_type = _TimelineEventType(event_type)
        self.created_at = created_at


class _DecisionCenterView:
    def __init__(
        self,
        decision_id,
        lifecycle_status,
        symbol,
        action,
        evidence,
        governance_evaluations,
        approvals,
        timeline,
    ):
        self.decision_id = decision_id
        self.lifecycle_status = lifecycle_status
        self.symbol = symbol
        self.action = action
        self.evidence = evidence
        self.governance_evaluations = governance_evaluations
        self.approvals = approvals
        self.timeline = timeline


class _FakeWorkspaceFacade:
    def __init__(self, morning_brief_result=None, decision_center_result=None):
        self._morning_brief_result = morning_brief_result
        self._decision_center_result = decision_center_result
        self.morning_brief_calls = 0
        self.received_decision_id = None

    def get_morning_brief(self):
        self.morning_brief_calls += 1
        return self._morning_brief_result

    def get_decision_center(self, decision_id):
        self.received_decision_id = decision_id
        return self._decision_center_result


def test_get_morning_brief_view_calls_facade_and_maps_fields():
    now = datetime.datetime(2026, 8, 6, 12, 0, 0)
    brief = _MorningBrief(
        total_decisions=3,
        decisions_by_status={DecisionState.DECISION_CREATED: 1, DecisionState.APPROVAL_RECORDED: 2},
        recent_decisions=[_RecentDecisionActivity("dec-001", DecisionState.APPROVAL_RECORDED, now)],
    )
    facade = _FakeWorkspaceFacade(morning_brief_result=brief)
    presenter = InvestorPresenter(facade)

    view = presenter.get_morning_brief_view()

    assert facade.morning_brief_calls == 1
    assert isinstance(view, MorningBriefView)
    assert view.total_decisions == 3
    assert view.status_summary == {DecisionState.DECISION_CREATED: 1, DecisionState.APPROVAL_RECORDED: 2}
    assert len(view.recent_activity_rows) == 1
    assert view.recent_activity_rows[0].decision_id == "dec-001"
    assert view.recent_activity_rows[0].status == DecisionState.APPROVAL_RECORDED
    assert view.recent_activity_rows[0].last_activity_at == now


def test_get_decision_center_view_passes_decision_id_and_maps_fields():
    created_at = datetime.datetime(2026, 8, 6, 12, 0, 0)
    evidence_at = datetime.datetime(2026, 8, 6, 12, 1, 0)
    evaluated_at = datetime.datetime(2026, 8, 6, 12, 2, 0)
    approved_at = datetime.datetime(2026, 8, 6, 12, 3, 0)

    decision_center_view = _DecisionCenterView(
        decision_id="dec-001",
        lifecycle_status=DecisionState.APPROVAL_RECORDED,
        symbol="AAPL",
        action="BUY",
        evidence=[
            _EvidenceSummary("ev-001", "NEWS_SENTIMENT", "newsapi", evidence_at)
        ],
        governance_evaluations=[
            _GovernanceEvaluationSummary("pol-001", True, evaluated_at)
        ],
        approvals=[
            _ApprovalSummary("apr-001", ApprovalStatus.APPROVED, "risk_officer", approved_at)
        ],
        timeline=[
            _TimelineEvent("DECISION_CREATED", created_at),
            _TimelineEvent("EVIDENCE_ATTACHED", evidence_at),
            _TimelineEvent("GOVERNANCE_EVALUATED", evaluated_at),
            _TimelineEvent("APPROVAL_RECORDED", approved_at),
        ],
    )
    facade = _FakeWorkspaceFacade(decision_center_result=decision_center_view)
    presenter = InvestorPresenter(facade)

    view = presenter.get_decision_center_view("dec-001")

    assert facade.received_decision_id == "dec-001"
    assert isinstance(view, DecisionCenterViewModel)
    assert view.decision_id == "dec-001"
    assert view.lifecycle_status == DecisionState.APPROVAL_RECORDED
    assert view.symbol == "AAPL"
    assert view.action == "BUY"

    assert len(view.evidence_rows) == 1
    assert view.evidence_rows[0].evidence_id == "ev-001"
    assert view.evidence_rows[0].evidence_type == "NEWS_SENTIMENT"
    assert view.evidence_rows[0].source == "newsapi"
    assert view.evidence_rows[0].attached_at == evidence_at

    assert view.governance_summary is not None
    assert view.governance_summary.policy_id == "pol-001"
    assert view.governance_summary.enabled is True
    assert view.governance_summary.evaluated_at == evaluated_at

    assert view.approval_summary is not None
    assert view.approval_summary.approval_id == "apr-001"
    assert view.approval_summary.status == ApprovalStatus.APPROVED
    assert view.approval_summary.approved_by == "risk_officer"
    assert view.approval_summary.approved_at == approved_at

    assert len(view.timeline_rows) == 4
    assert [row.event_type for row in view.timeline_rows] == [
        "DECISION_CREATED",
        "EVIDENCE_ATTACHED",
        "GOVERNANCE_EVALUATED",
        "APPROVAL_RECORDED",
    ]


def test_get_decision_center_view_returns_none_when_facade_returns_none():
    facade = _FakeWorkspaceFacade(decision_center_result=None)
    presenter = InvestorPresenter(facade)

    result = presenter.get_decision_center_view("missing-decision")

    assert result is None
    assert facade.received_decision_id == "missing-decision"


def test_presenter_works_with_fake_facade_and_no_repositories_or_services():
    brief = _MorningBrief(total_decisions=0, decisions_by_status={}, recent_decisions=[])
    facade = _FakeWorkspaceFacade(morning_brief_result=brief, decision_center_result=None)

    presenter = InvestorPresenter(facade)

    view = presenter.get_morning_brief_view()
    assert view.total_decisions == 0
    assert view.status_summary == {}
    assert view.recent_activity_rows == []

    assert presenter.get_decision_center_view("dec-any") is None
