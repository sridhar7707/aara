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


def test_thresholds_stays_unavailable_with_no_preference_fields():
    screen = build_mock_screen()

    assert screen.thresholds.preference_fields == ()
    assert screen.thresholds.is_available is False


def test_user_settings_and_notification_preferences_each_carry_exactly_one_allow_listed_field():
    """The smallest defensible allow-list: one ordinary, non-trading
    preference per area. Not risk_tolerance/max_position_pct/
    max_drawdown_pct/stop_loss_pct/notifications_enabled (database/
    user_settings.py's own protected fields) -- those are Governor/risk/
    persistence-adjacent and out of this backlog slice's authorized scope."""
    screen = build_mock_screen()

    assert screen.user_settings.is_available is True
    assert len(screen.user_settings.preference_fields) == 1
    assert screen.user_settings.preference_fields[0].label == "Display Theme"

    assert screen.notification_preferences.is_available is True
    assert len(screen.notification_preferences.preference_fields) == 1
    assert screen.notification_preferences.preference_fields[0].label == "Show In-App Notifications"


def test_available_areas_still_carry_a_non_configurable_disclosure():
    """unavailable_message stays populated -- and truthful -- even once an
    area has preference_fields: it now states that the shown control is
    not currently configurable and cannot be saved, not that the whole
    area has no source."""
    screen = build_mock_screen()

    for message in (
        screen.user_settings.unavailable_message,
        screen.notification_preferences.unavailable_message,
    ):
        assert "not currently configurable" in message.lower()
        assert "cannot be saved" in message.lower()


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
