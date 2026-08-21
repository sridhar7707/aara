"""Tests for applications.trading_intelligence.ui.decision_center.screen."""
import datetime
import dataclasses

import pytest

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry, ApprovalStatus
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
    ReadStatus,
    format_display_timestamp,
)


def test_format_display_timestamp_converts_naive_utc_to_america_chicago_summer_cdt():
    assert (
        format_display_timestamp(datetime.datetime(2026, 8, 21, 19, 45, 0))
        == "2026-08-21 14:45 CDT"
    )


def test_format_display_timestamp_converts_naive_utc_to_america_chicago_winter_cst():
    assert (
        format_display_timestamp(datetime.datetime(2026, 1, 8, 15, 40, 0))
        == "2026-01-08 09:40 CST"
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

    assert area.timestamp_display == "2026-08-04 07:30 CDT"


def test_decision_detail_area_formats_timestamp_in_america_chicago_summer_cdt():
    """P1 UI-only timestamp fix: all Decision Center timestamps are stored
    as naive-but-UTC (see format_display_timestamp's own docstring) and
    must display converted to America/Chicago, DST-aware. August is CDT
    (UTC-5)."""
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 8, 21, 19, 45, 0))
    )

    assert area.timestamp_display == "2026-08-21 14:45 CDT"


def test_decision_detail_area_formats_timestamp_in_america_chicago_winter_cst():
    """Same conversion, but January is CST (UTC-6) -- proves the DST
    transition is honored automatically, not a fixed offset."""
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 1, 8, 15, 40, 0))
    )

    assert area.timestamp_display == "2026-01-08 09:40 CST"


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
    assert area.timestamp_display == "2026-08-04 07:00 CDT"


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


def test_decision_detail_area_defaults_to_no_audit_trail():
    area = DecisionDetailArea(decision=_make_view())

    assert area.audit_trail == ()


def test_decision_detail_area_carries_audit_entries():
    entry = _make_audit_entry()
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(entry,))

    assert area.audit_trail == (entry,)


def test_decision_detail_area_preserves_audit_entry_order():
    first = _make_audit_entry(event_type="DECISION_CREATED")
    second = _make_audit_entry(event_type="EVIDENCE_ATTACHED")
    area = DecisionDetailArea(decision=_make_view(), audit_trail=(first, second))

    assert area.audit_trail == (first, second)


def test_decision_detail_area_is_immutable_including_audit_trail():
    area = DecisionDetailArea(decision=_make_view())
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.audit_trail = (_make_audit_entry(),)


def test_empty_audit_trail_and_errored_audit_trail_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), audit_trail=())
    errored = DecisionDetailArea(
        decision=_make_view(), audit_trail=(), audit_trail_status=ReadStatus.ERROR
    )

    assert empty.audit_trail_status is ReadStatus.OK
    assert errored.audit_trail_status is ReadStatus.ERROR


def test_decision_detail_area_defaults_every_read_status_to_ok():
    area = DecisionDetailArea(decision=None)

    assert area.decision_status is ReadStatus.OK
    assert area.evidence_status is ReadStatus.OK
    assert area.governance_status is ReadStatus.OK
    assert area.approvals_status is ReadStatus.OK
    assert area.audit_trail_status is ReadStatus.OK


def test_missing_decision_and_errored_decision_are_distinguishable():
    missing = DecisionDetailArea(decision=None)
    errored = DecisionDetailArea(decision=None, decision_status=ReadStatus.ERROR)

    assert missing.decision_status is ReadStatus.OK
    assert errored.decision_status is ReadStatus.ERROR
    assert missing.decision_status != errored.decision_status


def test_empty_evidence_and_errored_evidence_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), evidence=())
    errored = DecisionDetailArea(
        decision=_make_view(), evidence=(), evidence_status=ReadStatus.ERROR
    )

    assert empty.evidence == () and empty.evidence_status is ReadStatus.OK
    assert errored.evidence == () and errored.evidence_status is ReadStatus.ERROR


def test_empty_governance_and_errored_governance_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), governance=())
    errored = DecisionDetailArea(
        decision=_make_view(), governance=(), governance_status=ReadStatus.ERROR
    )

    assert empty.governance_status is ReadStatus.OK
    assert errored.governance_status is ReadStatus.ERROR


def test_empty_approvals_and_errored_approvals_are_distinguishable():
    empty = DecisionDetailArea(decision=_make_view(), approvals=())
    errored = DecisionDetailArea(
        decision=_make_view(), approvals=(), approvals_status=ReadStatus.ERROR
    )

    assert empty.approvals_status is ReadStatus.OK
    assert errored.approvals_status is ReadStatus.ERROR


def test_decision_detail_area_read_status_fields_are_immutable():
    area = DecisionDetailArea(decision=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        area.decision_status = ReadStatus.ERROR


def test_decision_detail_area_defaults_evidence_and_risk_reference_to_none():
    area = DecisionDetailArea(decision=_make_view())

    assert area.evidence_reference is None
    assert area.risk_reference is None


def test_decision_detail_area_carries_raw_evidence_and_risk_reference():
    area = DecisionDetailArea(
        decision=_make_view(), evidence_reference="evidence-001", risk_reference="risk-001",
    )

    assert area.evidence_reference == "evidence-001"
    assert area.risk_reference == "risk-001"


def test_decision_center_screen_composes_list_and_detail_areas():
    view = _make_view()
    list_area = DecisionListArea(decisions=[view])
    detail_area = DecisionDetailArea(decision=view)

    screen = DecisionCenterScreen(list_area=list_area, detail_area=detail_area)

    assert screen.list_area is list_area
    assert screen.detail_area is detail_area
