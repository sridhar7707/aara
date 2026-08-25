"""Settings screen structure -- shell MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/morning_brief/screen.py's pattern. Like Morning Brief, and unlike
ui/portfolio_intelligence/screen.py and ui/risk_intelligence/screen.py,
this package never carries a "populated" branch: per
docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2,
Settings' three required areas -- User Settings, Thresholds, Notification
Preferences -- have no Sentinel Engine contract proposed ("none proposed
... explicitly out of Sentinel's scope") and no product-layer persistence/
configuration contract is wired in this application either. Inventing
illustrative values here would misrepresent an unbuilt data path as a
populated one, and could be mistaken for real user configuration -- this
package's own content rule forbids that. Every area is therefore always
unavailable, with a fixed, honest message.

Area titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim.
"""
from dataclasses import dataclass
from typing import Tuple

USER_SETTINGS_TITLE = "User Settings"
THRESHOLDS_TITLE = "Thresholds"
NOTIFICATION_PREFERENCES_TITLE = "Notification Preferences"


@dataclass(frozen=True)
class SettingsArea:
    title: str
    unavailable_message: str


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
