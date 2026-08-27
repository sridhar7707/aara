"""Morning Brief screen structure -- shell MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/portfolio_intelligence/screen.py's and ui/risk_intelligence/screen.py's
pattern. Per docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md
Section 2, Morning Brief's four required sections -- Portfolio Snapshot,
Market Mood/Regime, Candidate Screening Summary, Overnight Holdings News --
have no Sentinel-side contract, wired or proposed, for any of them.
Inventing illustrative numbers here (the way Portfolio/Risk Intelligence
do for their own, differently-scoped gaps) would misrepresent an unbuilt
data path as a populated one -- `available_summary` therefore only ever
carries a real, adapter-sourced value (see bootstrap.py's
_build_morning_brief_ui()), never a fabricated one. A section with no
real source stays exactly as it always has: an honest, fixed unavailable
message.

Section titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim -- in particular
"Candidate Screening Summary", which must never be replaced by decision-
activity, DecisionProjection, or MorningBriefQuery-derived content (see
this package's mock_data.py docstring).
"""
from dataclasses import dataclass
from typing import Optional, Tuple

PORTFOLIO_SNAPSHOT_TITLE = "Portfolio Snapshot"
MARKET_MOOD_REGIME_TITLE = "Market Mood / Regime"
CANDIDATE_SCREENING_SUMMARY_TITLE = "Candidate Screening Summary"
OVERNIGHT_HOLDINGS_NEWS_TITLE = "Overnight Holdings News"


@dataclass(frozen=True)
class MorningBriefSection:
    title: str
    unavailable_message: str
    available_summary: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """True only once a real, adapter-sourced summary has been
        supplied (see bootstrap.py) -- default None means unavailable,
        matching every other screen's own is_available convention
        (SettingsArea, PortfolioScreen's is_empty)."""
        return self.available_summary is not None


@dataclass(frozen=True)
class MorningBriefScreen:
    portfolio_snapshot: MorningBriefSection
    market_mood_regime: MorningBriefSection
    candidate_screening_summary: MorningBriefSection
    overnight_holdings_news: MorningBriefSection

    @property
    def sections(self) -> Tuple[MorningBriefSection, ...]:
        """Fixed display order, matching the frozen IA's own section order."""
        return (
            self.portfolio_snapshot,
            self.market_mood_regime,
            self.candidate_screening_summary,
            self.overnight_holdings_news,
        )

    @property
    def is_empty(self) -> bool:
        """True only when every section is unavailable. Kept as an
        explicit property (rather than a bare constant) to match
        DecisionListArea/PortfolioScreen/RiskScreen's own is_empty
        convention, so this screen's emptiness is queried the same way
        every sibling screen's is."""
        return not any(section.is_available for section in self.sections)

    @property
    def empty_state_message(self) -> str:
        return "Morning Brief has no wired data sources yet."
