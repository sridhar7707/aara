"""Tests for Morning Brief's Overnight Holdings News wiring in bootstrap:

- _format_overnight_holdings_news -- the pure formatting turning a real
  AlpacaNewsSource result into the section's available_summary text.
- _build_morning_brief_ui -- that real Alpaca news is attached only when
  real holdings can be determined, that a failure at either adapter
  leaves the section on its existing honest unavailable message, and that
  no other Morning Brief section's behavior changes.

Post-ADR-061 (Category A / Amendment 1): the adapter methods return
ReadResult; the "only when real holdings + real news" trigger is unwrapped
from `.value`. Per ADR-061 A4, MorningBriefSection.health is populated on
every path -- including the unavailable fallback -- so the view can name
the specific failure reason.
"""
from dataclasses import replace

from applications.platform.integrations import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.adapters.alpaca_news_source import (
    HoldingsNewsItem,
    OvernightHoldingsNews,
)
from applications.trading_intelligence.adapters.legacy_position_source import OpenPosition
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen
from applications.trading_intelligence.bootstrap import (
    _build_morning_brief_ui,
    _format_overnight_holdings_news,
)


def _item(headline, symbols=("AAPL",), source="Benzinga"):
    return HoldingsNewsItem(
        headline=headline, symbols=tuple(symbols), source=source,
        created_at="2026-08-27T05:00:00+00:00", url="https://example.test/a",
    )


def _ok(value, provider):
    return ReadResult.healthy(value, provider)


def _down(provider):
    return ReadResult.failed(IntegrationHealth.unavailable(provider))


# --------------------------------------------------------------------------
# _format_overnight_holdings_news (pure -- takes domain objects, unchanged)
# --------------------------------------------------------------------------

def test_format_reports_no_open_holdings_explicitly():
    summary = _format_overnight_holdings_news(OvernightHoldingsNews(items=()), ())

    assert summary == "No open holdings -- no overnight holdings news to report."


def test_format_reports_a_successful_fetch_that_matched_nothing():
    summary = _format_overnight_holdings_news(
        OvernightHoldingsNews(items=()), ("AAPL", "MSFT")
    )

    assert summary == "No recent news for current holdings (AAPL, MSFT)."


def test_format_singular_headline_names_the_latest_and_its_source():
    news = OvernightHoldingsNews(items=(_item("Apple ships a thing"),))

    summary = _format_overnight_holdings_news(news, ("AAPL",))

    assert summary == (
        '1 recent headline for current holdings (AAPL) -- '
        'latest: "Apple ships a thing" (Benzinga).'
    )


def test_format_pluralizes_and_still_names_only_the_latest():
    news = OvernightHoldingsNews(items=(
        _item("Newest", source="Reuters"),
        _item("Older"),
        _item("Oldest"),
    ))

    summary = _format_overnight_holdings_news(news, ("AAPL", "MSFT"))

    assert summary == (
        '3 recent headlines for current holdings (AAPL, MSFT) -- '
        'latest: "Newest" (Reuters).'
    )


def test_format_omits_source_clause_when_provider_gave_no_source():
    news = OvernightHoldingsNews(items=(_item("No source article", source=""),))

    summary = _format_overnight_holdings_news(news, ("AAPL",))

    assert summary == (
        '1 recent headline for current holdings (AAPL) -- latest: "No source article".'
    )


# --------------------------------------------------------------------------
# _build_morning_brief_ui wiring
# --------------------------------------------------------------------------

def _isolate_other_morning_brief_sources(monkeypatch):
    """Force the three non-news real sources to unavailable so a test can
    reason about the Overnight Holdings News section alone."""
    monkeypatch.setattr(
        bootstrap.LegacyCapitalSource,
        "get_capital_summary",
        lambda self: _down("trades_db_capital"),
    )
    monkeypatch.setattr(
        bootstrap.LegacyRegimeSource,
        "get_latest_regime",
        lambda self: _down("trades_db_regime"),
    )
    monkeypatch.setattr(
        bootstrap.LegacyCandidateScreeningSource,
        "get_latest_screening",
        lambda self: _down("trades_db_screening"),
    )


def test_wires_real_alpaca_news_into_the_overnight_section(monkeypatch):
    _isolate_other_morning_brief_sources(monkeypatch)
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource, "get_open_positions",
        lambda self: _ok(
            (
                OpenPosition(symbol="AAPL", quantity=1.0, entry_price=1.0),
                OpenPosition(symbol="MSFT", quantity=1.0, entry_price=1.0),
            ),
            "trades_db_positions",
        ),
    )
    captured = {}

    def _fake_news(self, symbols):
        captured["symbols"] = tuple(symbols)
        return _ok(
            OvernightHoldingsNews(items=(_item("Big AAPL story", symbols=("AAPL",)),)),
            "alpaca_news",
        )

    monkeypatch.setattr(bootstrap.AlpacaNewsSource, "get_overnight_holdings_news", _fake_news)

    screen = _build_morning_brief_ui()._screen
    section = screen.overnight_holdings_news

    assert captured["symbols"] == ("AAPL", "MSFT")  # filtered to real holdings
    assert section.is_available
    assert section.health is not None
    assert section.available_summary == (
        '1 recent headline for current holdings (AAPL, MSFT) -- '
        'latest: "Big AAPL story" (Benzinga).'
    )
    assert section.title == build_mock_screen().overnight_holdings_news.title


def test_overnight_section_stays_unavailable_when_holdings_cannot_be_determined(monkeypatch):
    _isolate_other_morning_brief_sources(monkeypatch)
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource, "get_open_positions",
        lambda self: _down("trades_db_positions"),
    )

    def _must_not_run(self, symbols):
        raise AssertionError("news must not be fetched when holdings are unknown")

    monkeypatch.setattr(bootstrap.AlpacaNewsSource, "get_overnight_holdings_news", _must_not_run)

    section = _build_morning_brief_ui()._screen.overnight_holdings_news
    expected = build_mock_screen().overnight_holdings_news

    assert not section.is_available
    assert section.available_summary is None
    assert section.health is None
    assert section.unavailable_message == expected.unavailable_message


def test_overnight_section_stays_unavailable_when_news_fetch_fails(monkeypatch):
    _isolate_other_morning_brief_sources(monkeypatch)
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource, "get_open_positions",
        lambda self: _ok(
            (OpenPosition(symbol="AAPL", quantity=1.0, entry_price=1.0),),
            "trades_db_positions",
        ),
    )
    monkeypatch.setattr(
        bootstrap.AlpacaNewsSource,
        "get_overnight_holdings_news",
        lambda self, symbols: _down("alpaca_news"),
    )

    section = _build_morning_brief_ui()._screen.overnight_holdings_news
    expected = build_mock_screen().overnight_holdings_news

    assert not section.is_available
    assert section.unavailable_message == expected.unavailable_message
    # ADR-061 A4: the failed news read's health is recorded on the
    # unavailable path so the view can name the reason.
    assert section.health is not None
    assert section.health.status is IntegrationStatus.UNAVAILABLE


def test_overnight_section_reports_empty_holdings_explicitly(monkeypatch):
    _isolate_other_morning_brief_sources(monkeypatch)
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource,
        "get_open_positions",
        lambda self: _ok((), "trades_db_positions"),
    )
    monkeypatch.setattr(
        bootstrap.AlpacaNewsSource, "get_overnight_holdings_news",
        lambda self, symbols: _ok(OvernightHoldingsNews(items=()), "alpaca_news"),
    )

    section = _build_morning_brief_ui()._screen.overnight_holdings_news

    assert section.is_available
    assert section.available_summary == "No open holdings -- no overnight holdings news to report."


def test_other_morning_brief_sections_carry_adapter_health_but_are_otherwise_unchanged(
    monkeypatch,
):
    """The three non-news sections keep their exact existing content --
    title, unavailable_message, and no available_summary. ADR-061 A4 adds
    only the (failed) adapter's IntegrationHealth on the unavailable path,
    so is_available and every other field stay as the baseline mock."""
    _isolate_other_morning_brief_sources(monkeypatch)
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource, "get_open_positions",
        lambda self: _ok(
            (OpenPosition(symbol="AAPL", quantity=1.0, entry_price=1.0),),
            "trades_db_positions",
        ),
    )
    monkeypatch.setattr(
        bootstrap.AlpacaNewsSource, "get_overnight_holdings_news",
        lambda self, symbols: _ok(
            OvernightHoldingsNews(items=(_item("x"),)), "alpaca_news"
        ),
    )

    screen = _build_morning_brief_ui()._screen
    baseline = build_mock_screen()

    for attr in ("portfolio_snapshot", "market_mood_regime", "candidate_screening_summary"):
        section = getattr(screen, attr)
        expected = getattr(baseline, attr)
        assert section.health is not None, f"{attr} should carry the failed adapter health"
        assert section.health.status is IntegrationStatus.UNAVAILABLE
        assert section.is_available is False
        assert replace(section, health=None) == expected, (
            f"{attr} must be untouched apart from the new health field"
        )
