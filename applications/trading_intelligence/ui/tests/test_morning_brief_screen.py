from applications.trading_intelligence.ui.morning_brief.screen import (
    CANDIDATE_SCREENING_SUMMARY_TITLE,
    MARKET_MOOD_REGIME_TITLE,
    OVERNIGHT_HOLDINGS_NEWS_TITLE,
    PORTFOLIO_SNAPSHOT_TITLE,
    MorningBriefScreen,
    MorningBriefSection,
)


def _make_screen(**overrides):
    defaults = dict(
        portfolio_snapshot=MorningBriefSection(
            title=PORTFOLIO_SNAPSHOT_TITLE, unavailable_message="unavailable-1",
        ),
        market_mood_regime=MorningBriefSection(
            title=MARKET_MOOD_REGIME_TITLE, unavailable_message="unavailable-2",
        ),
        candidate_screening_summary=MorningBriefSection(
            title=CANDIDATE_SCREENING_SUMMARY_TITLE, unavailable_message="unavailable-3",
        ),
        overnight_holdings_news=MorningBriefSection(
            title=OVERNIGHT_HOLDINGS_NEWS_TITLE, unavailable_message="unavailable-4",
        ),
    )
    defaults.update(overrides)
    return MorningBriefScreen(**defaults)


def test_frozen_ia_section_titles_are_exact():
    """These four literal strings are the frozen IA's own "Required
    information" wording (docs/products/AARA_TRADING_INTELLIGENCE_UI_
    SPECIFICATION.md Section 2) -- this test locks them in verbatim."""
    assert PORTFOLIO_SNAPSHOT_TITLE == "Portfolio Snapshot"
    assert MARKET_MOOD_REGIME_TITLE == "Market Mood / Regime"
    assert CANDIDATE_SCREENING_SUMMARY_TITLE == "Candidate Screening Summary"
    assert OVERNIGHT_HOLDINGS_NEWS_TITLE == "Overnight Holdings News"


def test_sections_property_returns_all_four_in_frozen_ia_order():
    screen = _make_screen()

    titles = [section.title for section in screen.sections]

    assert titles == [
        PORTFOLIO_SNAPSHOT_TITLE,
        MARKET_MOOD_REGIME_TITLE,
        CANDIDATE_SCREENING_SUMMARY_TITLE,
        OVERNIGHT_HOLDINGS_NEWS_TITLE,
    ]


def test_screen_is_empty_when_every_section_is_unavailable():
    """The default/mock screen -- no section carries available_summary --
    stays empty, matching this shell's original all-unavailable shape."""
    screen = _make_screen()

    assert screen.is_empty is True


def test_screen_is_not_empty_when_at_least_one_section_is_available():
    screen = _make_screen(
        portfolio_snapshot=MorningBriefSection(
            title=PORTFOLIO_SNAPSHOT_TITLE, unavailable_message="unavailable-1",
            available_summary="Total value $10,000.00.",
        ),
    )

    assert screen.is_empty is False


def test_screen_is_empty_again_once_the_only_available_section_reverts():
    available_screen = _make_screen(
        market_mood_regime=MorningBriefSection(
            title=MARKET_MOOD_REGIME_TITLE, unavailable_message="unavailable-2",
            available_summary="Current market regime: TRENDING_UP.",
        ),
    )
    reverted_screen = _make_screen()

    assert available_screen.is_empty is False
    assert reverted_screen.is_empty is True


def test_section_is_available_only_when_available_summary_is_set():
    unavailable_section = MorningBriefSection(
        title=PORTFOLIO_SNAPSHOT_TITLE, unavailable_message="unavailable-1",
    )
    available_section = MorningBriefSection(
        title=PORTFOLIO_SNAPSHOT_TITLE, unavailable_message="unavailable-1",
        available_summary="Total value $10,000.00.",
    )

    assert unavailable_section.is_available is False
    assert available_section.is_available is True


def test_empty_state_message_is_a_fixed_honest_string():
    screen = _make_screen()

    assert screen.empty_state_message == "Morning Brief has no wired data sources yet."


def test_each_section_carries_its_own_unavailable_message():
    screen = _make_screen(
        portfolio_snapshot=MorningBriefSection(
            title=PORTFOLIO_SNAPSHOT_TITLE, unavailable_message="no portfolio source",
        ),
    )

    assert screen.portfolio_snapshot.unavailable_message == "no portfolio source"
