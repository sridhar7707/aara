"""Tests for applications.trading_intelligence.ui.decision_center.screen."""
import datetime
import dataclasses

import pytest

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)


def _make_view(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionView(**defaults)


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


def test_decision_list_area_reports_empty_state_when_no_decisions():
    area = DecisionListArea(decisions=[])

    assert area.is_empty is True
    assert area.empty_state_message == "No decisions recorded yet."


def test_decision_list_area_reports_not_empty_with_decisions():
    area = DecisionListArea(decisions=[_make_view()])

    assert area.is_empty is False
    assert area.empty_state_message is None


def test_decision_list_area_is_immutable():
    area = DecisionListArea(decisions=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.decisions = [_make_view()]


def test_decision_detail_area_reports_empty_when_no_decision_selected():
    area = DecisionDetailArea(decision=None)

    assert area.is_empty is True
    assert area.confidence_display is None
    assert area.status_display is None
    assert area.timestamp_display is None


def test_decision_detail_area_formats_confidence_as_a_percentage():
    area = DecisionDetailArea(decision=_make_view(confidence=0.78))

    assert area.confidence_display == "78%"


def test_decision_detail_area_formats_status_as_title_case_words():
    area = DecisionDetailArea(decision=_make_view(status=DecisionState.DECISION_CREATED))

    assert area.status_display == "Decision Created"


def test_decision_detail_area_formats_timestamp():
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 8, 4, 12, 30, 0))
    )

    assert area.timestamp_display == "2026-08-04 12:30 UTC"


def test_decision_detail_area_defaults_to_no_evidence():
    area = DecisionDetailArea(decision=_make_view())

    assert area.evidence == ()


def test_decision_detail_area_carries_evidence_entries():
    entry = _make_entry()
    area = DecisionDetailArea(decision=_make_view(), evidence=(entry,))

    assert area.evidence == (entry,)


def test_decision_detail_area_with_evidence_still_formats_core_decision_fields():
    entry = _make_entry()
    area = DecisionDetailArea(
        decision=_make_view(confidence=0.78, status=DecisionState.DECISION_CREATED),
        evidence=(entry,),
    )

    assert area.confidence_display == "78%"
    assert area.status_display == "Decision Created"
    assert area.timestamp_display == "2026-08-04 12:00 UTC"


def test_decision_detail_area_is_immutable_including_evidence():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.evidence = (_make_entry(),)


def test_decision_detail_area_defaults_to_no_governance():
    area = DecisionDetailArea(decision=_make_view())

    assert area.governance == ()


def test_decision_detail_area_carries_governance_entries():
    entry = _make_governance_entry()
    area = DecisionDetailArea(decision=_make_view(), governance=(entry,))

    assert area.governance == (entry,)


def test_decision_detail_area_defaults_to_no_approvals():
    area = DecisionDetailArea(decision=_make_view())

    assert area.approvals == ()


def test_decision_detail_area_carries_approval_entries():
    entry = _make_approval_entry()
    area = DecisionDetailArea(decision=_make_view(), approvals=(entry,))

    assert area.approvals == (entry,)


def test_decision_detail_area_is_immutable_including_governance_and_approvals():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.governance = (_make_governance_entry(),)
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.approvals = (_make_approval_entry(),)


def test_decision_detail_area_with_governance_and_approvals_still_formats_core_decision_fields():
    area = DecisionDetailArea(
        decision=_make_view(confidence=0.78, status=DecisionState.DECISION_CREATED),
        governance=(_make_governance_entry(),),
        approvals=(_make_approval_entry(),),
    )

    assert area.confidence_display == "78%"
    assert area.status_display == "Decision Created"


def test_decision_center_screen_composes_list_and_detail_areas():
    view = _make_view()
    list_area = DecisionListArea(decisions=[view])
    detail_area = DecisionDetailArea(decision=view)

    screen = DecisionCenterScreen(list_area=list_area, detail_area=detail_area)

    assert screen.list_area is list_area
    assert screen.detail_area is detail_area
