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
import sqlite3

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

        CREATE TABLE position_state (symbol TEXT, shares REAL, entry_price REAL);
        INSERT INTO position_state (symbol, shares, entry_price) VALUES ('AAPL', 10.0, 190.0);
        INSERT INTO position_state (symbol, shares, entry_price) VALUES ('MSFT', 4.0, 410.0);

        CREATE TABLE signal_log (id INTEGER PRIMARY KEY, regime TEXT);
        INSERT INTO signal_log (regime) VALUES ('RISK_ON');
        INSERT INTO signal_log (regime) VALUES ('NEUTRAL_HIGH_VOL');

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

    monkeypatch.setattr(bootstrap, "AlpacaNewsSource", _NoNews)
    monkeypatch.setattr(bootstrap, "LivePriceSource", _NoPrices)
    monkeypatch.setattr(bootstrap, "AlpacaPaperSource", _NoAccount)
    monkeypatch.setattr(bootstrap, "AlpacaPaperOrdersSource", _NoOrders)


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
    assert "12,345.67" in screen.portfolio_snapshot.available_summary


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
