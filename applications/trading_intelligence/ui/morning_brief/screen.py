"""Morning Brief screen structure -- shell MVP.

Framework-independent dataclasses (no gradio import), mirroring
ui/portfolio_intelligence/screen.py's and ui/risk_intelligence/screen.py's
pattern. Unlike those two siblings, this package never carries a
"populated" branch: per docs/products/AARA_TRADING_INTELLIGENCE_UI_
SPECIFICATION.md Section 2, Morning Brief's four required sections --
Portfolio Snapshot, Market Mood/Regime, Candidate Screening Summary,
Overnight Holdings News -- have no Sentinel-side contract, wired or
proposed, and no producer of any kind exists anywhere in this application
for any of them. Inventing illustrative numbers here (the way Portfolio/
Risk Intelligence do for their own, differently-scoped gaps) would
misrepresent an unbuilt data path as a populated one. Every section is
therefore always unavailable, with a fixed, honest message -- there is no
code path in this package that could ever report one as available.

Section titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim -- in particular
"Candidate Screening Summary", which must never be replaced by decision-
activity, DecisionProjection, or MorningBriefQuery-derived content (see
this package's mock_data.py docstring).
"""
from dataclasses import dataclass
from typing import Tuple

PORTFOLIO_SNAPSHOT_TITLE = "Portfolio Snapshot"
MARKET_MOOD_REGIME_TITLE = "Market Mood / Regime"
CANDIDATE_SCREENING_SUMMARY_TITLE = "Candidate Screening Summary"
OVERNIGHT_HOLDINGS_NEWS_TITLE = "Overnight Holdings News"


@dataclass(frozen=True)
class MorningBriefSection:
    title: str
    unavailable_message: str


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
        """Always True in this shell -- no section has a wired data source
        yet. Kept as an explicit property (rather than a bare constant)
        to match DecisionListArea/PortfolioScreen/RiskScreen's own
        is_empty convention, so this screen's emptiness is queried the
        same way every sibling screen's is."""
        return True

    @property
    def empty_state_message(self) -> str:
        return "Morning Brief has no wired data sources yet."
