"""Performance & Learning screen structure -- shell MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/morning_brief/screen.py's and ui/settings/screen.py's pattern. Like
those two, and unlike ui/portfolio_intelligence/screen.py and
ui/risk_intelligence/screen.py, this package never carries a "populated"
branch: per docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md
Section 2, Performance & Learning's three required areas -- Outcome
History, Attribution Breakdown, Model Confidence Calibration -- name only
a future, unwired Sentinel Engine input (`DECISION_OUTCOME_RECORDED`,
explicitly "BUY-scoped only... a UI must not imply every decision gets an
outcome") and no adapter for it exists in this application. Inventing
illustrative performance numbers, outcomes, or attribution figures here
would misrepresent an unbuilt data path as a populated one, and could be
read as real trading performance. Every area is therefore always
unavailable, with a fixed, honest message.

Area titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim.
"""
from dataclasses import dataclass
from typing import Tuple

OUTCOME_HISTORY_TITLE = "Outcome History"
ATTRIBUTION_BREAKDOWN_TITLE = "Attribution Breakdown"
MODEL_CONFIDENCE_CALIBRATION_TITLE = "Model Confidence Calibration"


@dataclass(frozen=True)
class PerformanceLearningSection:
    title: str
    unavailable_message: str


@dataclass(frozen=True)
class PerformanceLearningScreen:
    outcome_history: PerformanceLearningSection
    attribution_breakdown: PerformanceLearningSection
    model_confidence_calibration: PerformanceLearningSection

    @property
    def sections(self) -> Tuple[PerformanceLearningSection, ...]:
        """Fixed display order, matching the frozen IA's own section order."""
        return (
            self.outcome_history,
            self.attribution_breakdown,
            self.model_confidence_calibration,
        )

    @property
    def is_empty(self) -> bool:
        """Always True in this shell -- no area has a wired data source
        yet. Kept as an explicit property (rather than a bare constant)
        to match MorningBriefScreen's/SettingsScreen's/DecisionListArea's
        own is_empty convention."""
        return True

    @property
    def empty_state_message(self) -> str:
        return "Performance & Learning has no wired data sources yet."
