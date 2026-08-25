from applications.trading_intelligence.ui.settings.mock_data import build_mock_screen
from applications.trading_intelligence.ui.settings.screen import (
    NOTIFICATION_PREFERENCES_TITLE,
    THRESHOLDS_TITLE,
    USER_SETTINGS_TITLE,
)

# Terms that would indicate a mock value could be mistaken for a real user
# setting -- forbidden per this package's content rule (rule 6: do not
# create mock values that could be mistaken for real user settings).
_FORBIDDEN_REALISTIC_VALUE_MARKERS = ("@", "true", "false", "enabled", "disabled")


def test_build_mock_screen_returns_the_all_unavailable_screen():
    screen = build_mock_screen()

    assert screen.is_empty is True


def test_build_mock_screen_has_all_three_frozen_areas_with_correct_titles():
    screen = build_mock_screen()

    assert screen.user_settings.title == USER_SETTINGS_TITLE
    assert screen.thresholds.title == THRESHOLDS_TITLE
    assert screen.notification_preferences.title == NOTIFICATION_PREFERENCES_TITLE


def test_build_mock_screen_gives_every_area_a_non_empty_unavailable_message():
    screen = build_mock_screen()

    for area in screen.areas:
        assert isinstance(area.unavailable_message, str)
        assert area.unavailable_message.strip() != ""


def test_build_mock_screen_contains_no_values_resembling_real_settings():
    """No email addresses, boolean-looking toggle values, or numeric
    threshold-looking figures -- unlike ui/portfolio_intelligence/mock_data.py
    and ui/risk_intelligence/mock_data.py, which deliberately use hand-picked
    illustrative numbers for their own, differently-scoped gaps, this
    screen's content rule forbids anything that could be mistaken for a
    real user's configuration."""
    screen = build_mock_screen()

    for area in screen.areas:
        lowered = area.unavailable_message.lower()
        for marker in _FORBIDDEN_REALISTIC_VALUE_MARKERS:
            assert marker not in lowered
        assert "$" not in area.unavailable_message
        assert "%" not in area.unavailable_message
        assert not any(character.isdigit() for character in area.unavailable_message)
