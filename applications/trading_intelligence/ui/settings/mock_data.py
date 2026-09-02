"""Deterministic data for the Settings screen shell.

No sentinel_engine/bot/dashboard import. No persistence/configuration
contract import or reference of any kind: per docs/products/
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2, Settings has
"none proposed" for Sentinel Engine inputs, and no product-layer
persistence contract is wired in this application. This module -- the
sole data source for this screen, same role ui/morning_brief/mock_data.py
plays for its screen -- builds a fixed SettingsScreen rather than
illustrative values standing in for a real contract. Thresholds stays
all-unavailable (risk/execution-adjacent configuration, out of this
screen's authorized scope). User Settings and Notification Preferences
each carry exactly one allow-listed, non-trading preference field
(display theme; in-app notification visibility) -- rendered as a
non-interactive control (nothing consumes its value; see gradio_view.py)
with a disclosure that it is not currently configurable and cannot be
saved. Unlike
ui/portfolio_intelligence/mock_data.py's and
ui/risk_intelligence/mock_data.py's mock data (hand-picked but fabricated
figures standing in for real numbers), nothing here stands in for a real
wired setting -- these two fields are genuinely all that's here.
"""
from applications.trading_intelligence.ui.settings.screen import (
    NOTIFICATION_PREFERENCES_TITLE,
    THRESHOLDS_TITLE,
    USER_SETTINGS_TITLE,
    SettingsArea,
    SettingsPreferenceField,
    SettingsScreen,
)

_USER_SETTINGS = SettingsArea(
    title=USER_SETTINGS_TITLE,
    unavailable_message=(
        "This preference is not currently configurable and cannot be saved."
    ),
    preference_fields=(
        SettingsPreferenceField(
            label="Display Theme", options=("Light", "Dark"), default="Light",
        ),
    ),
)

_THRESHOLDS = SettingsArea(
    title=THRESHOLDS_TITLE,
    unavailable_message=(
        "No product-layer threshold-configuration contract is wired "
        "yet -- this area has no source."
    ),
)

_NOTIFICATION_PREFERENCES = SettingsArea(
    title=NOTIFICATION_PREFERENCES_TITLE,
    unavailable_message=(
        "This preference is not currently configurable and cannot be saved."
    ),
    preference_fields=(
        SettingsPreferenceField(
            label="Show In-App Notifications", options=("On", "Off"), default="On",
        ),
    ),
)


def build_mock_screen() -> SettingsScreen:
    """Named to match ui/morning_brief/mock_data.py's, ui/portfolio_
    intelligence/mock_data.py's, and ui/risk_intelligence/mock_data.py's
    build_mock_screen() so gradio_view.py's default-construction pattern
    stays identical across all five screens -- "mock" here means "this
    package's own fixed local state," not fabricated settings values (see
    module docstring above)."""
    return SettingsScreen(
        user_settings=_USER_SETTINGS,
        thresholds=_THRESHOLDS,
        notification_preferences=_NOTIFICATION_PREFERENCES,
    )
