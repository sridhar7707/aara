"""Settings screen structure -- shell MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/morning_brief/screen.py's pattern. Per docs/products/
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2, Settings' three
required areas -- User Settings, Thresholds, Notification Preferences --
have no Sentinel Engine contract proposed ("none proposed ... explicitly
out of Sentinel's scope") and no product-layer persistence/configuration
contract is wired in this application. Inventing illustrative values here
would misrepresent an unbuilt data path as a populated one, and could be
mistaken for real user configuration -- this package's own content rule
forbids that.

Thresholds carries risk/execution-adjacent configuration and stays
unavailable, with a fixed, honest message, for that reason alone.

User Settings and Notification Preferences may additionally carry a
narrow, explicitly allow-listed set of ordinary, non-trading display/
notification preferences (`preference_fields`) -- e.g. a display theme,
an in-app notification toggle. These are UI-local only: nothing here is
backed by a persistence or configuration contract, so a preference's
value never survives a page reload or a new session. `unavailable_message`
stays populated on every area (including ones with preference_fields) as
that area's disclosure text -- for Thresholds it explains total
unavailability; for an area with preference_fields it explains why
nothing shown there is saved.

Area titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim.
"""
from dataclasses import dataclass
from typing import Tuple

USER_SETTINGS_TITLE = "User Settings"
THRESHOLDS_TITLE = "Thresholds"
NOTIFICATION_PREFERENCES_TITLE = "Notification Preferences"


@dataclass(frozen=True)
class SettingsPreferenceField:
    """One allow-listed, non-trading display/notification preference.

    UI-local only -- see module docstring. `options` is the fixed set of
    choices a user may pick from; `default` is shown until changed and is
    never written anywhere."""
    label: str
    options: Tuple[str, ...]
    default: str


@dataclass(frozen=True)
class SettingsArea:
    title: str
    unavailable_message: str
    preference_fields: Tuple[SettingsPreferenceField, ...] = ()

    @property
    def is_available(self) -> bool:
        """True once this area carries at least one allow-listed,
        session-local preference field. False (Thresholds, always) means
        the area has no source at all -- render unavailable_message."""
        return len(self.preference_fields) > 0


@dataclass(frozen=True)
class SettingsScreen:
    user_settings: SettingsArea
    thresholds: SettingsArea
    notification_preferences: SettingsArea

    @property
    def areas(self) -> Tuple[SettingsArea, ...]:
        """Fixed display order, matching the frozen IA's own area order."""
        return (
            self.user_settings,
            self.thresholds,
            self.notification_preferences,
        )

    @property
    def is_empty(self) -> bool:
        """Always True in this shell -- no area has a wired configuration
        source yet. Kept as an explicit property (rather than a bare
        constant) to match MorningBriefScreen's/DecisionListArea's/
        PortfolioScreen's/RiskScreen's own is_empty convention."""
        return True

    @property
    def empty_state_message(self) -> str:
        return "Settings has no wired configuration source yet."
