"""Deterministic all-unavailable data for the Morning Brief screen shell.

No sentinel_engine/bot/dashboard import. No MorningBriefQuery import or
reference of any kind: per docs/products/AARA_TRADING_INTELLIGENCE_UI_
SPECIFICATION.md Section 2, Morning Brief's four required sections have no
Sentinel-side contract wired or proposed, so this module -- the sole data
source for this screen, same role ui/portfolio_intelligence/mock_data.py
and ui/risk_intelligence/mock_data.py play for their own screens -- builds
a fixed, honest all-unavailable MorningBriefScreen rather than illustrative
numbers. Unlike those two siblings' mock data (hand-picked but fabricated
figures), nothing here is a number standing in for a real one; every field
is a literal explanation of why that section has no source yet.

Candidate Screening Summary in particular must never be populated from
decision-activity data (DecisionProjection/MorningBriefQuery output covers
only decisions that already exist, never the pre-decision candidates the
screening gates rejected) -- see screen.py's module docstring. No such
substitution is made here.
"""
from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
    MorningBriefScreen,
    MorningBriefSection,
)

_PORTFOLIO_SNAPSHOT = MorningBriefSection(
    title=PORTFOLIO_SNAPSHOT_TITLE,
    unavailable_message=(
        "No Sentinel-side portfolio contract exists or is proposed yet -- "
        "this section has no wired data source."
    ),
)

_MARKET_MOOD_REGIME = MorningBriefSection(
    title=MARKET_MOOD_REGIME_TITLE,
    unavailable_message=(
        "No Sentinel-side market mood/regime contract exists or is "
        "proposed yet -- this section has no wired data source."
    ),
)

_CANDIDATE_SCREENING_SUMMARY = MorningBriefSection(
    title=CANDIDATE_SCREENING_SUMMARY_TITLE,
    unavailable_message=(
        "No Sentinel-side candidate-screening contract exists or is "
        "proposed yet -- this section has no wired data source."
    ),
)

_OVERNIGHT_HOLDINGS_NEWS = MorningBriefSection(
    title=OVERNIGHT_HOLDINGS_NEWS_TITLE,
    unavailable_message=(
        "No Evidence/news producer exists yet -- this section has no "
        "wired data source."
    ),
)


def build_mock_screen() -> MorningBriefScreen:
    """Named to match ui/portfolio_intelligence/mock_data.py's and
    ui/risk_intelligence/mock_data.py's build_mock_screen() so
    gradio_view.py's default-construction pattern stays identical across
    all three screens -- "mock" here means "this package's own fixed local
    state," not fabricated numbers (see module docstring above)."""
    return MorningBriefScreen(
        portfolio_snapshot=_PORTFOLIO_SNAPSHOT,
        market_mood_regime=_MARKET_MOOD_REGIME,
        candidate_screening_summary=_CANDIDATE_SCREENING_SUMMARY,
        overnight_holdings_news=_OVERNIGHT_HOLDINGS_NEWS,
    )
