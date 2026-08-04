"""Tests for applications.trading_intelligence.ui.decision_center.screen."""
import datetime
import dataclasses

import pytest

from applications.trading_intelligence.projections.decision_view import DecisionView
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
        status="DECISION_CREATED",
        confidence=0.78,
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionView(**defaults)


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
    area = DecisionDetailArea(decision=_make_view(status="DECISION_CREATED"))

    assert area.status_display == "Decision Created"


def test_decision_detail_area_formats_timestamp():
    area = DecisionDetailArea(
        decision=_make_view(updated_at=datetime.datetime(2026, 8, 4, 12, 30, 0))
    )

    assert area.timestamp_display == "2026-08-04 12:30 UTC"


def test_decision_center_screen_composes_list_and_detail_areas():
    view = _make_view()
    list_area = DecisionListArea(decisions=[view])
    detail_area = DecisionDetailArea(decision=view)

    screen = DecisionCenterScreen(list_area=list_area, detail_area=detail_area)

    assert screen.list_area is list_area
    assert screen.detail_area is detail_area
