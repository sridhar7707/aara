from applications.trading_intelligence.ui.performance_learning.mock_data import (
    build_calibration_preview_screen,
    build_mock_screen,
)
from applications.trading_intelligence.ui.performance_learning.screen import (
    ATTRIBUTION_BREAKDOWN_TITLE,
    CALIBRATION_MIN_OUTCOMES,
    MODEL_CONFIDENCE_CALIBRATION_TITLE,
    OUTCOME_HISTORY_TITLE,
)


def test_build_mock_screen_returns_the_all_unavailable_screen():
    screen = build_mock_screen()

    assert screen.is_empty is True


def test_build_mock_screen_has_all_three_frozen_sections_with_correct_titles():
    screen = build_mock_screen()

    assert screen.outcome_history.title == OUTCOME_HISTORY_TITLE
    assert screen.attribution_breakdown.title == ATTRIBUTION_BREAKDOWN_TITLE
    assert screen.model_confidence_calibration.title == MODEL_CONFIDENCE_CALIBRATION_TITLE


def test_build_mock_screen_gives_every_section_a_non_empty_unavailable_message():
    screen = build_mock_screen()

    for section in screen.sections:
        assert isinstance(section.unavailable_message, str)
        assert section.unavailable_message.strip() != ""


def test_build_mock_screen_contains_no_fabricated_numeric_looking_data():
    """No dollar amounts, percentages, or other numeric-looking figures --
    unlike ui/portfolio_intelligence/mock_data.py and
    ui/risk_intelligence/mock_data.py, which deliberately use hand-picked
    illustrative numbers for their own, differently-scoped gaps, this
    screen's content rule forbids fabricated or illustrative performance
    figures entirely (no fake numerical metrics, no fake outcomes)."""
    screen = build_mock_screen()

    for section in screen.sections:
        assert "$" not in section.unavailable_message
        assert "%" not in section.unavailable_message
        assert not any(character.isdigit() for character in section.unavailable_message)


def test_outcome_history_message_does_not_imply_every_decision_has_an_outcome():
    """Spec constraint: DECISION_OUTCOME_RECORDED is BUY-scoped only -- "a
    UI must not imply every decision gets an outcome." Verified here since
    it's the one section with a spec-mandated nuance beyond plain
    unavailability."""
    screen = build_mock_screen()

    message = screen.outcome_history.unavailable_message
    assert "BUY" in message
    assert "never every decision" in message or "not every decision" in message.lower()


# --- calibration preview builder (opt-in; never the production shell) -----


def test_build_mock_screen_leaves_calibration_unavailable():
    """The production shell path must not gain fabricated calibration
    figures -- calibration stays unavailable exactly like the other
    unwired areas."""
    screen = build_mock_screen()

    assert screen.calibration_health is None
    assert screen.calibration_available is False
    assert screen.calibration_bands == ()


def test_calibration_preview_screen_is_healthy_and_over_the_min():
    screen = build_calibration_preview_screen()

    assert screen.calibration_available is True
    assert screen.calibration_total_outcomes >= CALIBRATION_MIN_OUTCOMES
    assert screen.calibration_has_enough_data is True


def test_calibration_preview_exercises_wins_losses_and_an_empty_band():
    screen = build_calibration_preview_screen()

    populated = [b for b in screen.calibration_bands if b.n > 0]
    empty = [b for b in screen.calibration_bands if b.n == 0]
    assert len(populated) >= 2
    assert len(empty) >= 1
    assert any(b.wins > 0 for b in populated)
    assert any(b.losses > 0 for b in populated)


def test_calibration_preview_is_deterministic():
    assert build_calibration_preview_screen() == build_calibration_preview_screen()


def test_calibration_preview_keeps_outcome_history_and_attribution_unavailable():
    """The preview builder illustrates the calibration render path only --
    it does not fabricate outcome-history rows or attribution data."""
    screen = build_calibration_preview_screen()

    assert screen.outcome_rows == ()
    assert screen.outcome_health is None
    assert screen.attribution_breakdown.unavailable_message == (
        build_mock_screen().attribution_breakdown.unavailable_message
    )
