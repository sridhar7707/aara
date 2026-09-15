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


# --- Decision Activity & Risk State Context sprint --------------------


def test_decision_activity_unavailable_by_default():
    """No decision_activity_summary supplied -> unavailable, matching
    every other None-vs-string convention on this screen
    (MorningBriefSection.is_available)."""
    screen = _make_screen()

    assert screen.decision_activity_is_available is False
    assert screen.decision_activity_summary is None


def test_decision_activity_populated():
    screen = _make_screen(
        decision_activity_summary="3 BUY decisions in the last 24h, 1 already resolved.",
    )

    assert screen.decision_activity_is_available is True
    assert screen.decision_activity_summary == (
        "3 BUY decisions in the last 24h, 1 already resolved."
    )


def test_decision_activity_populated_with_a_real_zero_count():
    """A HEALTHY read with zero recent decisions is a real fact, not
    unavailable -- same distinction is_available already makes for every
    other section (an empty tuple/zero count is available, None is not)."""
    screen = _make_screen(
        decision_activity_summary="0 BUY decisions in the last 24h, 0 already resolved.",
    )

    assert screen.decision_activity_is_available is True


def test_current_risk_state_unavailable_by_default():
    screen = _make_screen()

    assert screen.current_risk_state_is_available is False
    assert screen.current_risk_state_summary is None


def test_current_risk_state_populated():
    screen = _make_screen(
        current_risk_state_summary="Current risk state: NORMAL (as of 2026-09-01 14:00 CDT).",
    )

    assert screen.current_risk_state_is_available is True
    assert screen.current_risk_state_summary == (
        "Current risk state: NORMAL (as of 2026-09-01 14:00 CDT)."
    )


def test_decision_activity_and_risk_state_are_independent():
    """One being unavailable must never affect the other's availability --
    same independence convention drawdown_history/portfolio_history
    already have relative to their own sibling fields."""
    only_decision_activity = _make_screen(
        decision_activity_summary="1 BUY decisions in the last 24h, 0 already resolved.",
    )
    only_risk_state = _make_screen(
        current_risk_state_summary="Current risk state: WARNING (as of 2026-09-01 14:00 CDT).",
    )

    assert only_decision_activity.decision_activity_is_available is True
    assert only_decision_activity.current_risk_state_is_available is False

    assert only_risk_state.decision_activity_is_available is False
    assert only_risk_state.current_risk_state_is_available is True


def test_decision_activity_and_risk_state_do_not_affect_is_empty():
    """These two additive facts are not part of the frozen four-section IA
    -- screen.is_empty must stay keyed on the four sections only, exactly
    as portfolio_history already is."""
    screen = _make_screen(
        decision_activity_summary="2 BUY decisions in the last 24h, 2 already resolved.",
        current_risk_state_summary="Current risk state: NORMAL (as of 2026-09-01 14:00 CDT).",
    )

    assert screen.is_empty is True


def test_screen_stays_frozen_for_decision_activity_and_risk_state_fields():
    import dataclasses
    import pytest

    screen = _make_screen()
    with pytest.raises(dataclasses.FrozenInstanceError):
        screen.decision_activity_summary = "should not be settable"
    with pytest.raises(dataclasses.FrozenInstanceError):
        screen.current_risk_state_summary = "should not be settable"
