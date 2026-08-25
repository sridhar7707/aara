"""Deterministic all-unavailable data for the Settings screen shell.

No sentinel_engine/bot/dashboard import. No persistence/configuration
contract import or reference of any kind: per docs/products/
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2, Settings has
"none proposed" for Sentinel Engine inputs, and no product-layer
persistence contract is wired in this application. This module -- the
sole data source for this screen, same role ui/morning_brief/mock_data.py
plays for its screen -- builds a fixed, honest all-unavailable
SettingsScreen rather than illustrative values. Unlike
ui/portfolio_intelligence/mock_data.py's and
ui/risk_intelligence/mock_data.py's mock data (hand-picked but fabricated
figures), nothing here is a value standing in for a real user setting --
every field is a literal explanation of why that area has no source yet,
so it can never be mistaken for a real user's configuration.
"""
from applications.trading_intelligence.ui.settings.screen import (
    NOTIFICATION_PREFERENCES_TITLE,
    THRESHOLDS_TITLE,
    USER_SETTINGS_TITLE,
    SettingsArea,
    SettingsScreen,
)

_USER_SETTINGS = SettingsArea(
    title=USER_SETTINGS_TITLE,
    unavailable_message=(
        "No product-layer user-settings persistence contract is wired "
        "yet -- this area has no source."
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
        "No product-layer notification-preferences contract is wired "
        "yet -- this area has no source."
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
