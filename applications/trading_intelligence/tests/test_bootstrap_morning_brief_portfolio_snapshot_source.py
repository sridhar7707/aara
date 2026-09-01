"""Proves the P0 freshness fix: Morning Brief's Portfolio Snapshot section
is built from trades.db's `portfolio_snapshots` (the freshest operational
portfolio value, appended every bot cycle), NOT the stale `capital_pools`
accounting row (whose production value has been frozen since 2026-07-27).

Both tables are populated in the fixture with deliberately different
numbers, so the test can assert which one reached the UI.
"""
import sqlite3

import pytest

from applications.platform.integrations import IntegrationHealth, IntegrationStatus, ReadResult
from applications.trading_intelligence import bootstrap


@pytest.fixture
def _no_alpaca_news(monkeypatch):
    """Keep the Overnight Holdings News branch offline/deterministic -- it
    is irrelevant to this test, which only inspects Portfolio Snapshot."""
    class _NoNews:
        def get_overnight_holdings_news(self, *_a, **_k):
            return ReadResult.failed(IntegrationHealth.unavailable("alpaca_news"))

    monkeypatch.setattr(bootstrap, "AlpacaNewsSource", _NoNews)


def _trades_db_with_stale_pool_and_fresh_snapshot(tmp_path):
    """capital_pools active row is stale (total 96,933.32 / 38,850.78 cash /
    58,082.54 invested -- the real production values, frozen 2026-07-27);
    portfolio_snapshots has a newer, different row."""
    path = tmp_path / "trades.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE capital_pools (
            id INTEGER PRIMARY KEY, name TEXT, status TEXT,
            allocated_amount REAL, available_cash REAL, invested_amount REAL,
            reserve REAL, realized_profit REAL, profit_withdrawn REAL
        );
        INSERT INTO capital_pools
            (name, status, allocated_amount, available_cash, invested_amount,
             reserve, realized_profit, profit_withdrawn)
        VALUES ('default', 'active', 96933.32, 38850.78, 58082.54, 0.0, 0.0, 0.0);

        CREATE TABLE portfolio_snapshots (
            timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
            open_positions INTEGER
        );
        INSERT INTO portfolio_snapshots VALUES ('2026-08-29T19:39:42+00:00', 99000.0, 55000.0, 5);
        INSERT INTO portfolio_snapshots VALUES ('2026-08-31T19:39:42+00:00', 100029.85, 59869.06, 5);
        """
    )
    conn.commit()
    conn.close()
    return str(path)


def test_portfolio_snapshot_uses_portfolio_snapshots_not_stale_capital_pools(
    tmp_path, _no_alpaca_news
):
    db_path = _trades_db_with_stale_pool_and_fresh_snapshot(tmp_path)

    screen = bootstrap._build_morning_brief_screen(db_path=db_path)
    section = screen.portfolio_snapshot

    assert section.is_available
    assert section.health.status is IntegrationStatus.HEALTHY

    summary = section.available_summary
    # From the latest portfolio_snapshots row: 100,029.85 value,
    # 59,869.06 cash, 40,160.79 invested (= value - cash).
    assert summary == (
        "Total value $100,029.85 ($59,869.06 cash, $40,160.79 invested)."
    )
    # None of the stale capital_pools figures leaked through.
    assert "96,933.32" not in summary
    assert "38,850.78" not in summary
    assert "58,082.54" not in summary


def test_portfolio_snapshot_unavailable_when_only_stale_capital_pools_exists(
    tmp_path, _no_alpaca_news
):
    """With no portfolio_snapshots table at all, the section falls back to
    its honest unavailable state -- it never silently reverts to reading
    capital_pools."""
    path = tmp_path / "trades.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE capital_pools (
            id INTEGER PRIMARY KEY, name TEXT, status TEXT,
            allocated_amount REAL, available_cash REAL, invested_amount REAL,
            reserve REAL, realized_profit REAL, profit_withdrawn REAL
        );
        INSERT INTO capital_pools
            (name, status, allocated_amount, available_cash, invested_amount,
             reserve, realized_profit, profit_withdrawn)
        VALUES ('default', 'active', 96933.32, 38850.78, 58082.54, 0.0, 0.0, 0.0);
        """
    )
    conn.commit()
    conn.close()

    screen = bootstrap._build_morning_brief_screen(db_path=str(path))
    section = screen.portfolio_snapshot

    assert not section.is_available
    assert section.available_summary is None
    assert section.health.status is IntegrationStatus.API_ERROR
