"""Morning Brief P2 -- the SPY daily-move clause on the Market Mood /
Regime section.

Proves: a HEALTHY LiveMarketQuoteSource quote appends a factual SPY clause
to the existing regime sentence (which is preserved byte-for-byte); the
SPY "as of" date is the yfinance bar date, never a render/now/snapshot
time; any non-HEALTHY quote appends nothing; an unavailable regime
prevents the clause entirely; is_today=False renders "last session".

Adapters are monkeypatched on `bootstrap`, so no DB or network is touched.
"""
from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.adapters.legacy_regime_source import RegimeSnapshot
from applications.trading_intelligence.adapters.live_market_quote_source import MarketQuote
from applications.trading_intelligence.ui.morning_brief.mock_data import build_mock_screen

_REGIME_SENTENCE = "Current market regime: HIGH_VOLATILITY."


def _down(provider):
    return ReadResult.failed(IntegrationHealth.unavailable(provider))


def _healthy_regime():
    return ReadResult.healthy(
        RegimeSnapshot(regime="HIGH_VOLATILITY", as_of="2026-08-31T19:39:45+00:00"),
        "trades_db_regime",
    )


def _quote(**overrides):
    defaults = dict(
        symbol="SPY",
        last=512.34,
        previous_close=508.10,
        pct_change=(512.34 - 508.10) / 508.10 * 100,
        as_of="2026-09-01",
        is_today=True,
    )
    defaults.update(overrides)
    return ReadResult.healthy(MarketQuote(**defaults), "yfinance_market_quote")


def _isolate(monkeypatch, *, regime, spy_quote):
    """Regime + SPY quote controlled per test; every other Morning Brief
    source forced unavailable so only the regime section matters."""
    monkeypatch.setattr(
        bootstrap.LegacyRegimeSource, "get_latest_regime", lambda self: regime
    )
    monkeypatch.setattr(
        bootstrap.LiveMarketQuoteSource, "get_spy_quote", lambda self: spy_quote
    )
    monkeypatch.setattr(
        bootstrap.LegacyPortfolioSnapshotSource,
        "get_latest_portfolio_snapshot",
        lambda self: _down("trades_db_portfolio_snapshot"),
    )
    monkeypatch.setattr(
        bootstrap.LegacyCandidateScreeningSource,
        "get_latest_screening",
        lambda self: _down("trades_db_screening"),
    )
    monkeypatch.setattr(
        bootstrap.LegacyPositionSource,
        "get_open_positions",
        lambda self: _down("trades_db_positions"),
    )


def _regime_section(monkeypatch, *, regime, spy_quote):
    _isolate(monkeypatch, regime=regime, spy_quote=spy_quote)
    return bootstrap._build_morning_brief_screen(db_path=None).market_mood_regime


def test_healthy_quote_appends_the_exact_spy_clause(monkeypatch):
    section = _regime_section(
        monkeypatch, regime=_healthy_regime(), spy_quote=_quote()
    )

    assert section.available_summary == (
        "Current market regime: HIGH_VOLATILITY. "
        "SPY 512.34, prev close 508.10 (+0.83% today) -- daily bar as of 2026-09-01."
    )
    # regime sentence preserved byte-for-byte at the front
    assert section.available_summary.startswith(_REGIME_SENTENCE + " SPY ")
    # `as_of` (the per-section timestamp line) is still the signal_log time,
    # not the SPY bar date
    assert section.as_of is not None and "2026-09-01" not in section.as_of


def test_spy_bar_date_is_used_not_render_or_snapshot_time(monkeypatch):
    section = _regime_section(
        monkeypatch,
        regime=_healthy_regime(),
        spy_quote=_quote(as_of="2026-07-04", is_today=False),
    )
    assert "daily bar as of 2026-07-04." in section.available_summary
    assert "now" not in section.available_summary.lower()


def test_is_today_false_renders_last_session_never_today(monkeypatch):
    section = _regime_section(
        monkeypatch,
        regime=_healthy_regime(),
        spy_quote=_quote(pct_change=-1.234, is_today=False, as_of="2026-08-29"),
    )
    assert "(-1.23% last session) -- daily bar as of 2026-08-29." in section.available_summary
    assert " today)" not in section.available_summary


def _assert_regime_only(section):
    assert section.available_summary == _REGIME_SENTENCE
    assert "SPY" not in section.available_summary
    assert "daily bar" not in section.available_summary


def test_unavailable_quote_leaves_the_regime_only_summary(monkeypatch):
    _assert_regime_only(
        _regime_section(
            monkeypatch,
            regime=_healthy_regime(),
            spy_quote=_down("yfinance_market_quote"),
        )
    )


def test_rate_limited_quote_leaves_the_regime_only_summary(monkeypatch):
    _assert_regime_only(
        _regime_section(
            monkeypatch,
            regime=_healthy_regime(),
            spy_quote=ReadResult.failed(
                IntegrationHealth.rate_limited("yfinance_market_quote")
            ),
        )
    )


def test_not_configured_quote_leaves_the_regime_only_summary(monkeypatch):
    _assert_regime_only(
        _regime_section(
            monkeypatch,
            regime=_healthy_regime(),
            spy_quote=ReadResult.failed(
                IntegrationHealth.not_configured("yfinance_market_quote")
            ),
        )
    )


def test_api_error_quote_leaves_the_regime_only_summary(monkeypatch):
    _assert_regime_only(
        _regime_section(
            monkeypatch,
            regime=_healthy_regime(),
            spy_quote=ReadResult.failed(
                IntegrationHealth.api_error("yfinance_market_quote")
            ),
        )
    )


def test_unavailable_regime_prevents_the_spy_clause(monkeypatch):
    section = _regime_section(
        monkeypatch,
        regime=_down("trades_db_regime"),
        spy_quote=_quote(),  # healthy, but must not be used
    )
    baseline = build_mock_screen().market_mood_regime
    assert section.available_summary is None
    assert section.is_available is False
    assert "SPY" not in (section.available_summary or "")
    assert section.unavailable_message == baseline.unavailable_message
