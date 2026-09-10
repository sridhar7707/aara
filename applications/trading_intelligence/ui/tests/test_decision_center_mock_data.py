"""Tests for applications.trading_intelligence.ui.decision_center.mock_data."""
from applications.trading_intelligence.projections.decision_view import DecisionView
from applications.trading_intelligence.ui.decision_center.mock_data import (
    get_mock_decisions,
    get_mock_evidence,
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


def test_build_mock_screen_detail_area_exercises_every_evidence_polarity_phrase():
    """ADR-070 §9: the demo detail area carries evidence records whose
    per-record polarity labels cover all three phrases -- "Supported the
    BUY", "Contradicted the BUY", "Polarity unavailable" -- one label per
    record, never aggregated."""
    screen = build_mock_screen()

    labels = [row.polarity_label for row in screen.detail_area.evidence_polarity_rows]

    assert labels == ["Supported the BUY", "Contradicted the BUY", "Polarity unavailable"]
    assert len(screen.detail_area.evidence) == len(get_mock_evidence())


def test_mock_decisions_exercise_every_recommendation_provenance_state():
    """ADR-070 Sprint 3: the demo decisions must let a viewer see all the
    recommendation-surfacing states -- a Sentinel recommendation, an
    interpreted strategy decision, an unrecorded-provenance decision (safe
    default), and a Sentinel-authored WAIT (the inert non-concurrence line)."""
    by_source = {}
    for view in get_mock_decisions():
        by_source.setdefault(view.action_source, []).append(view)

    assert "SENTINEL" in by_source
    assert "STRATEGY" in by_source
    assert None in by_source  # provenance deliberately unrecorded on one decision
    assert any(
        v.action == "WAIT" and v.action_source == "SENTINEL" for v in get_mock_decisions()
    )
