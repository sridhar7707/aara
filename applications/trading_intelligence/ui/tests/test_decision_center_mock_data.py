"""Tests for applications.trading_intelligence.ui.decision_center.mock_data."""
from applications.trading_intelligence.projections.decision_view import DecisionView
from applications.trading_intelligence.ui.decision_center.mock_data import (
    get_mock_decisions,
    build_mock_screen,
)


def test_get_mock_decisions_returns_a_non_empty_list():
    decisions = get_mock_decisions()

    assert len(decisions) > 0


def test_get_mock_decisions_returns_valid_decision_views():
    decisions = get_mock_decisions()

    for view in decisions:
        assert isinstance(view, DecisionView)
        assert view.decision_id
        assert view.symbol
        assert view.action
        assert view.status
        assert 0.0 <= view.confidence <= 1.0


def test_build_mock_screen_list_area_contains_the_mock_decisions():
    screen = build_mock_screen()

    assert screen.list_area.decisions == get_mock_decisions()
    assert screen.list_area.is_empty is False


def test_build_mock_screen_detail_area_defaults_to_the_first_decision():
    screen = build_mock_screen()

    assert screen.detail_area.decision == get_mock_decisions()[0]
    assert screen.detail_area.is_empty is False
