"""Bootstrap wiring for the ADR-055 `trades.db` snapshot.

Proves that when `bootstrap.fetch_trades_db_snapshot()` yields a real
local snapshot path, that path is threaded through every
`_build_*_ui` -> screen-provider -> `legacy_*_source.py` adapter for the
three legacy-trades.db-backed screens (Morning Brief, Portfolio
Intelligence, Risk Intelligence), so those sections render real rows from
the snapshot; and when it yields `None`, the adapters keep their own
`"trades.db"` default and every section stays on its existing
honest-unavailable / illustrative fallback -- no fabricated data.

Also pins the ADR-055 Section 2.6 staleness rule: persisted `screened_at`
and `risk_state.updated_at` values are rendered from the snapshot
verbatim / as the same instant, never as "today" and never dropped.

A real temporary SQLite file with the five authorized Group-C operational
tables stands in for the fetched snapshot; network-touching collaborators
(live prices, Alpaca) are stubbed so the test is offline and
deterministic.
"""
import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import gradio as gr
import pytest

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence import bootstrap


def _snap_ok(path):
    return ReadResult.healthy(path, "hf_trades_db_snapshot")


def _snap_absent():
    return ReadResult.failed(
        IntegrationHealth.not_configured("hf_trades_db_snapshot")
    )


def _adapter_down(provider):
    return ReadResult.failed(IntegrationHealth.unavailable(provider))


def _make_fixture_snapshot(tmp_path):
    """A real temp SQLite file shaped like the bot's published trades.db,
    populated in the five tables the legacy_* adapters read."""
    path = tmp_path / "fetched_snapshot.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE capital_pools (
            id INTEGER PRIMARY KEY, allocated_amount REAL, available_cash REAL,
            invested_amount REAL, reserve REAL, realized_profit REAL, status TEXT
        );
        INSERT INTO capital_pools
            (allocated_amount, available_cash, invested_amount, reserve, realized_profit, status)
        VALUES (50000.0, 12345.67, 37000.0, 654.33, 1200.5, 'active');

        CREATE TABLE portfolio_snapshots (
            timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
            open_positions INTEGER
        );
        INSERT INTO portfolio_snapshots VALUES ('2026-08-30T19:39:42+00:00', 80000.0, 20000.0, 5);
        INSERT INTO portfolio_snapshots VALUES ('2026-08-31T19:39:42+00:00', 88000.0, 25000.0, 5);

        CREATE TABLE position_state (symbol TEXT, shares REAL, entry_price REAL);
        INSERT INTO position_state (symbol, shares, entry_price) VALUES ('AAPL', 10.0, 190.0);
        INSERT INTO position_state (symbol, shares, entry_price) VALUES ('MSFT', 4.0, 410.0);

        CREATE TABLE signal_log (id INTEGER PRIMARY KEY, timestamp TEXT, regime TEXT);
        INSERT INTO signal_log (timestamp, regime)
        VALUES ('2026-08-31T13:10:00+00:00', 'RISK_ON');
        INSERT INTO signal_log (timestamp, regime)
        VALUES ('2026-08-31T19:39:45+00:00', 'NEUTRAL_HIGH_VOL');

        CREATE TABLE risk_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
        INSERT INTO risk_state (key, value, updated_at)
        VALUES ('risk_governor_state', 'WARNING', '2026-08-20T15:03:38+00:00');

        CREATE TABLE screener_log (
            symbol TEXT, rank INTEGER, composite_score REAL, sector TEXT, screened_at TEXT
        );
        INSERT INTO screener_log (symbol, rank, composite_score, sector, screened_at)
        VALUES ('NVDA', 1, 0.91, 'Technology', '2020-01-02');
        """
    )
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def offline(monkeypatch):
    """Stub every network-touching collaborator bootstrap would call while
    assembling the three screens, so only the SQLite snapshot matters."""
    class _NoNews:
        def get_overnight_holdings_news(self, *_a, **_k):
            return _adapter_down("alpaca_news")

    class _NoPrices:
        def get_current_prices(self, *_a, **_k):
            return _adapter_down("yfinance")

    class _NoAccount:
        def get_account(self):
            return _adapter_down("alpaca_paper")

        def get_positions(self):
            return _adapter_down("alpaca_paper")

    class _NoOrders:
        def get_recent_orders(self):
            return _adapter_down("alpaca_paper_orders")

    class _NoMarketQuote:
        def get_spy_quote(self):
            return _adapter_down("yfinance_market_quote")

    monkeypatch.setattr(bootstrap, "AlpacaNewsSource", _NoNews)
    monkeypatch.setattr(bootstrap, "LivePriceSource", _NoPrices)
    monkeypatch.setattr(bootstrap, "AlpacaPaperSource", _NoAccount)
    monkeypatch.setattr(bootstrap, "AlpacaPaperOrdersSource", _NoOrders)
    monkeypatch.setattr(bootstrap, "LiveMarketQuoteSource", _NoMarketQuote)


# --- screen providers read real snapshot rows ------------------------------

def test_risk_screen_reads_real_state_from_snapshot(tmp_path, offline):
    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_risk_intelligence_screen(db_path=snap)
    assert screen.current is not None
    assert screen.current.state == "WARNING"


def test_risk_screen_unavailable_when_no_snapshot(tmp_path, monkeypatch, offline):
    monkeypatch.chdir(tmp_path)  # no ./trades.db here
    screen = bootstrap._build_risk_intelligence_screen(db_path=None)
    assert screen.current is None


def test_portfolio_screen_capital_is_real_from_snapshot(tmp_path, offline):
    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_portfolio_intelligence_screen(db_path=snap)
    assert screen.capital is not None
    assert screen.capital.available_cash == 12345.67
    assert screen.capital.invested_amount == 37000.0


def test_portfolio_screen_capital_unavailable_when_no_snapshot(
    tmp_path, monkeypatch, offline
):
    monkeypatch.chdir(tmp_path)
    screen = bootstrap._build_portfolio_intelligence_screen(db_path=None)
    assert screen.capital is None


def test_morning_brief_regime_and_capital_real_from_snapshot(tmp_path, offline):
    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_morning_brief_screen(db_path=snap)
    assert "NEUTRAL_HIGH_VOL" in screen.market_mood_regime.available_summary
    # Portfolio Snapshot now comes from the latest portfolio_snapshots row
    # (88,000.00 value / 25,000.00 cash / 63,000.00 invested), NOT the
    # stale capital_pools accounting row (12,345.67 cash).
    summary = screen.portfolio_snapshot.available_summary
    assert "88,000.00" in summary
    assert "25,000.00 cash" in summary
    assert "63,000.00 invested" in summary
    assert "12,345.67" not in summary


def test_morning_brief_portfolio_section_as_of_is_the_portfolio_snapshots_timestamp(
    tmp_path, offline
):
    """P1 per-section freshness: Portfolio Snapshot's `as_of` is the latest
    portfolio_snapshots row's own timestamp (2026-08-31T19:39:42Z ->
    14:39 CDT), not the render clock and not capital_pools.updated_at."""
    snap = _make_fixture_snapshot(tmp_path)
    section = bootstrap._build_morning_brief_screen(db_path=snap).portfolio_snapshot
    assert section.as_of == "2026-08-31 14:39 CDT"


def test_morning_brief_regime_section_as_of_is_the_signal_log_timestamp(tmp_path, offline):
    """Market Mood / Regime's `as_of` is signal_log.timestamp of the row
    the regime label came from (2026-08-31T19:39:45Z -> 14:39 CDT); the
    regime string itself is unchanged."""
    snap = _make_fixture_snapshot(tmp_path)
    section = bootstrap._build_morning_brief_screen(db_path=snap).market_mood_regime
    assert section.available_summary == "Current market regime: NEUTRAL_HIGH_VOL."
    assert section.as_of == "2026-08-31 14:39 CDT"


def test_morning_brief_screening_section_as_of_is_screener_log_screened_at(
    tmp_path, offline
):
    """Candidate Screening Summary's `as_of` is screener_log.screened_at --
    the same authoritative timestamp the summary body already states as a
    date (2020-01-02), rendered here with the wall-clock convention."""
    snap = _make_fixture_snapshot(tmp_path)
    section = bootstrap._build_morning_brief_screen(
        db_path=snap
    ).candidate_screening_summary
    assert "2020-01-02" in section.available_summary  # body: persisted date, not today
    # date-only screened_at -> midnight UTC -> 2020-01-01 18:00 CST
    assert section.as_of == "2020-01-01 18:00 CST"


def test_morning_brief_news_section_as_of_is_the_live_fetch_instant_not_snapshot_time(
    tmp_path, monkeypatch, offline
):
    """Overnight Holdings News' `as_of` is the instant the live Alpaca News
    GET returned -- captured via bootstrap._now_utc(), NOT any trades.db
    snapshot timestamp. It differs from the portfolio_snapshots-derived
    `as_of` and moves with each build/Refresh."""
    from applications.trading_intelligence.adapters.alpaca_news_source import (
        HoldingsNewsItem,
        OvernightHoldingsNews,
    )

    class _LiveNews:
        def get_overnight_holdings_news(self, symbols):
            return ReadResult.healthy(
                OvernightHoldingsNews(
                    items=(
                        HoldingsNewsItem(
                            headline="AAPL up", symbols=("AAPL",), source="Benzinga",
                            created_at="2026-09-01T05:00:00+00:00",
                            url="https://example.test/a",
                        ),
                    )
                ),
                "alpaca_news",
            )

    monkeypatch.setattr(bootstrap, "AlpacaNewsSource", _LiveNews)
    monkeypatch.setattr(
        bootstrap,
        "_now_utc",
        lambda: datetime(2026, 9, 1, 12, 34, tzinfo=timezone.utc),
    )

    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_morning_brief_screen(db_path=snap)
    news = screen.overnight_holdings_news

    assert news.is_available
    assert news.as_of == "2026-09-01 07:34 CDT"  # 12:34 UTC -> CDT fetch instant
    # not the portfolio_snapshots-derived section timestamp
    assert news.as_of != screen.portfolio_snapshot.as_of
    # not any trades.db snapshot timestamp present in the fixture
    assert "2026-08-31" not in news.as_of


def test_morning_brief_section_as_of_is_none_on_the_unavailable_path(tmp_path, offline):
    """No trades.db -> every trades.db-backed section stays unavailable and
    carries no `as_of` (never a fabricated timestamp)."""
    screen = bootstrap._build_morning_brief_screen(db_path=str(tmp_path / "nope.db"))
    for attr in (
        "portfolio_snapshot",
        "market_mood_regime",
        "candidate_screening_summary",
        "overnight_holdings_news",
    ):
        assert getattr(screen, attr).as_of is None


def _html_strings(demo):
    return [
        b.value
        for b in demo.blocks.values()
        if isinstance(b, gr.HTML) and isinstance(getattr(b, "value", None), str)
    ]


def test_morning_brief_ui_shows_snapshot_fetch_time_separate_from_render_clock(
    tmp_path, offline
):
    """ADR-055 snapshot-age visibility: the built Morning Brief carries a
    'Rendered at ...' line (render clock) AND a separate 'Operational data
    snapshot: ...' line whose timestamp is the fetched snapshot file's
    mtime -- i.e. when this process obtained it. Refresh does not
    re-download, so this is derived read-only from os.path.getmtime."""
    snap = _make_fixture_snapshot(tmp_path)

    demo = bootstrap._build_morning_brief_ui(snap).build()
    combined = "\n".join(_html_strings(demo))

    expected_stamp = (
        datetime.fromtimestamp(os.path.getmtime(snap), timezone.utc)
        .astimezone(ZoneInfo("America/Chicago"))
        .strftime("%Y-%m-%d %H:%M %Z")
    )

    assert "Rendered at " in combined
    assert f"Operational data snapshot: {expected_stamp}" in combined
    assert "not re-downloaded on Refresh" in combined


def test_morning_brief_ui_snapshot_line_unavailable_when_no_snapshot_path(offline):
    demo = bootstrap._build_morning_brief_ui(None).build()
    combined = "\n".join(_html_strings(demo))

    assert "Rendered at " in combined
    assert "Operational data snapshot: unavailable" in combined


def test_portfolio_intelligence_ui_shows_snapshot_fetch_time_separate_from_render_clock(
    tmp_path, offline
):
    """Same ADR-055 snapshot-age visibility as Morning Brief: Portfolio
    Intelligence's Capital Summary / Allocation / Holdings positions come
    from the fetched trades.db snapshot, so the built page carries a
    'Rendered at ...' render clock AND a separate 'Operational data
    snapshot: ...' line (the fetched file's mtime), annotated so a Refresh
    is not mistaken for a re-download."""
    snap = _make_fixture_snapshot(tmp_path)

    demo = bootstrap._build_portfolio_intelligence_ui(snap).build()
    combined = "\n".join(_html_strings(demo))

    expected_stamp = (
        datetime.fromtimestamp(os.path.getmtime(snap), timezone.utc)
        .astimezone(ZoneInfo("America/Chicago"))
        .strftime("%Y-%m-%d %H:%M %Z")
    )

    assert "Rendered at " in combined
    assert f"Operational data snapshot: {expected_stamp}" in combined
    assert "not re-downloaded on Refresh" in combined


def test_portfolio_intelligence_ui_snapshot_line_unavailable_when_no_snapshot_path(offline):
    demo = bootstrap._build_portfolio_intelligence_ui(None).build()
    combined = "\n".join(_html_strings(demo))

    assert "Rendered at " in combined
    assert "Operational data snapshot: unavailable" in combined


def test_risk_intelligence_ui_shows_snapshot_fetch_time_separate_from_render_clock(
    tmp_path, offline
):
    """Same ADR-055 snapshot-age visibility as Morning Brief / Portfolio
    Intelligence: Risk Intelligence's `risk_state` read comes from the
    fetched trades.db snapshot, so the built page carries a 'Rendered at
    ...' render clock AND a separate 'Operational data snapshot: ...' line
    (the fetched file's mtime), annotated so a Refresh is not mistaken for
    a re-download. Replaces the earlier ambiguous 'As of {render clock}'
    single line."""
    snap = _make_fixture_snapshot(tmp_path)

    demo = bootstrap._build_risk_intelligence_ui(snap).build()
    combined = "\n".join(_html_strings(demo))

    expected_stamp = (
        datetime.fromtimestamp(os.path.getmtime(snap), timezone.utc)
        .astimezone(ZoneInfo("America/Chicago"))
        .strftime("%Y-%m-%d %H:%M %Z")
    )

    assert "Rendered at " in combined
    assert f"Operational data snapshot: {expected_stamp}" in combined
    assert "not re-downloaded on Refresh" in combined
    # the render-clock line must not use the old "As of " wording
    assert "As of " not in combined


def test_risk_intelligence_ui_snapshot_line_unavailable_when_no_snapshot_path(offline):
    demo = bootstrap._build_risk_intelligence_ui(None).build()
    combined = "\n".join(_html_strings(demo))

    assert "Rendered at " in combined
    assert "Operational data snapshot: unavailable" in combined


def test_snapshot_fetched_at_helper_reads_the_file_mtime(tmp_path):
    snap = _make_fixture_snapshot(tmp_path)
    result = bootstrap._snapshot_fetched_at(snap)
    assert result == datetime.fromtimestamp(os.path.getmtime(snap), timezone.utc)

    assert bootstrap._snapshot_fetched_at(None) is None
    assert bootstrap._snapshot_fetched_at(str(tmp_path / "missing.db")) is None


def test_morning_brief_unavailable_when_no_snapshot(tmp_path, monkeypatch, offline):
    monkeypatch.chdir(tmp_path)
    illustrative = bootstrap.build_mock_morning_brief_screen()
    screen = bootstrap._build_morning_brief_screen(db_path=None)
    # unchanged from the illustrative screen -- no fabricated real data
    assert screen.market_mood_regime.available_summary == (
        illustrative.market_mood_regime.available_summary
    )
    assert screen.portfolio_snapshot.available_summary == (
        illustrative.portfolio_snapshot.available_summary
    )


# --- ADR-055 Section 2.6: staleness stays visible / verbatim ---------------

def test_screened_at_is_rendered_verbatim_not_today(tmp_path, offline):
    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_morning_brief_screen(db_path=snap)
    summary = screen.candidate_screening_summary.available_summary
    assert "2020-01-02" in summary  # the persisted date, not the run date


def test_risk_as_of_preserves_the_persisted_instant(tmp_path, offline):
    snap = _make_fixture_snapshot(tmp_path)
    screen = bootstrap._build_risk_intelligence_screen(db_path=snap)
    # 15:03:38 UTC on 2026-08-20 == 10:03 America/Chicago (CDT) -- same
    # instant, converted for display, never fabricated or dropped.
    assert screen.current.as_of == "2026-08-20 10:03 CDT"


def test_risk_as_of_unparseable_value_passes_through_unchanged(tmp_path, offline):
    path = tmp_path / "odd.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE risk_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO risk_state (key, value, updated_at) VALUES (?, ?, ?)",
        ("risk_governor_state", "DEFENSIVE", "last cycle"),
    )
    conn.commit()
    conn.close()
    screen = bootstrap._build_risk_intelligence_screen(db_path=str(path))
    assert screen.current.as_of == "last cycle"


# --- full composition threads the snapshot path all the way down ----------

def _recording_factory(real_cls, seen):
    """Stand-in for a legacy adapter class that records the db_path each
    instance was constructed with, then delegates to the real class."""
    def _factory(*args, **kwargs):
        seen.append(kwargs.get("db_path", args[0] if args else None))
        return real_cls(*args, **kwargs)

    return _factory


def test_build_app_threads_snapshot_path_into_every_legacy_adapter(
    tmp_path, monkeypatch, offline
):
    snap = _make_fixture_snapshot(tmp_path)
    monkeypatch.setattr(bootstrap, "fetch_trades_db_snapshot", lambda: _snap_ok(snap))

    seen = {}
    for name in (
        "LegacyCapitalSource",
        "LegacyPortfolioSnapshotSource",
        "LegacyRegimeSource",
        "LegacyCandidateScreeningSource",
        "LegacyPositionSource",
        "LegacyRiskStateSource",
    ):
        seen[name] = []
        monkeypatch.setattr(
            bootstrap, name, _recording_factory(getattr(bootstrap, name), seen[name])
        )

    bootstrap.build_trading_intelligence_app()

    for name, paths in seen.items():
        assert paths, f"{name} was never constructed"
        assert all(p == snap for p in paths), f"{name} got {paths!r}, expected {snap!r}"


def test_build_app_without_snapshot_leaves_adapters_on_default(
    tmp_path, monkeypatch, offline
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap, "fetch_trades_db_snapshot", lambda: _snap_absent())

    seen = []
    monkeypatch.setattr(
        bootstrap,
        "LegacyRiskStateSource",
        _recording_factory(bootstrap.LegacyRiskStateSource, seen),
    )

    bootstrap.build_trading_intelligence_app()

    assert seen
    assert all(p is None for p in seen)  # no db_path kwarg -> adapter default
