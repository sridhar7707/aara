from applications.trading_intelligence.ui.settings.screen import (
    NOTIFICATION_PREFERENCES_TITLE,
    THRESHOLDS_TITLE,
    USER_SETTINGS_TITLE,
    SettingsArea,
    SettingsPreferenceField,
    SettingsScreen,
)


def _make_screen(**overrides):
    defaults = dict(
        user_settings=SettingsArea(title=USER_SETTINGS_TITLE, unavailable_message="unavailable-1"),
        thresholds=SettingsArea(title=THRESHOLDS_TITLE, unavailable_message="unavailable-2"),
        notification_preferences=SettingsArea(
            title=NOTIFICATION_PREFERENCES_TITLE, unavailable_message="unavailable-3",
        ),
    )
    defaults.update(overrides)
    return SettingsScreen(**defaults)


def test_frozen_ia_area_titles_are_exact():
    """These three literal strings are the frozen IA's own "Required
    information" wording (docs/products/AARA_TRADING_INTELLIGENCE_UI_
    SPECIFICATION.md Section 2) -- this test locks them in verbatim."""
    assert USER_SETTINGS_TITLE == "User Settings"
    assert THRESHOLDS_TITLE == "Thresholds"
    assert NOTIFICATION_PREFERENCES_TITLE == "Notification Preferences"


def test_areas_property_returns_all_three_in_frozen_ia_order():
    screen = _make_screen()

    titles = [area.title for area in screen.areas]

    assert titles == [USER_SETTINGS_TITLE, THRESHOLDS_TITLE, NOTIFICATION_PREFERENCES_TITLE]


def test_screen_is_always_empty():
    """This shell has no code path that could ever report an area as
    available -- is_empty is always True, unconditionally."""
    screen = _make_screen()

    assert screen.is_empty is True


def test_empty_state_message_is_a_fixed_honest_string():
    screen = _make_screen()

    assert screen.empty_state_message == "Settings has no wired configuration source yet."


def test_each_area_carries_its_own_unavailable_message():
    screen = _make_screen(
        user_settings=SettingsArea(title=USER_SETTINGS_TITLE, unavailable_message="no settings source"),
    )

    assert screen.user_settings.unavailable_message == "no settings source"


def test_area_with_no_preference_fields_is_not_available():
    area = SettingsArea(title=THRESHOLDS_TITLE, unavailable_message="unavailable")

    assert area.preference_fields == ()
    assert area.is_available is False


def test_area_with_preference_fields_is_available():
    area = SettingsArea(
        title=USER_SETTINGS_TITLE,
        unavailable_message="not saved",
        preference_fields=(
            SettingsPreferenceField(label="Display Theme", options=("Light", "Dark"), default="Light"),
        ),
    )

    assert area.is_available is True


def test_settings_preference_field_carries_label_options_and_default():
    field = SettingsPreferenceField(label="Display Theme", options=("Light", "Dark"), default="Light")

    assert field.label == "Display Theme"
    assert field.options == ("Light", "Dark")
    assert field.default == "Light"
    assert field.default in field.options
