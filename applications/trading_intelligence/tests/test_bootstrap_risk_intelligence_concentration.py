"""Concentration, Risk Parameters & Drawdown Context sprint: Risk
Intelligence's Concentration section.

Reuses the SAME positions -> prices -> _build_portfolio_holdings() chain
Portfolio Intelligence's own Holdings/Allocation by Holding already uses
(LegacyPositionSource + LivePriceSource + bootstrap._build_portfolio_
holdings) -- invoked a second, independent time here in
_build_risk_intelligence_screen(). No new adapter, no new market-data
source, no recomputed weight.
"""
import sqlite3
import tempfile
from unittest.mock import patch

from applications.platform.integrations import IntegrationHealth, ReadResult
from applications.trading_intelligence import bootstrap
from applications.trading_intelligence.ui.risk_intelligence.screen import ConcentrationHolding

_PRICES_METHOD = (
    "applications.trading_intelligence.adapters."
    "live_price_source.LivePriceSource.get_current_prices"
)

_DDL = """
CREATE TABLE position_state (symbol TEXT, shares REAL, entry_price REAL);
CREATE TABLE portfolio_snapshots (
    timestamp TEXT PRIMARY KEY, portfolio_value REAL, available_cash REAL,
    open_positions INTEGER
);
CREATE TABLE risk_state (
    key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
);
"""


def _ok(value):
    return ReadResult.healthy(value, "live_prices")


def _trades_db(rows=()):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    for symbol, shares, entry_price in rows:
        conn.execute(
            "INSERT INTO position_state (symbol, shares, entry_price) VALUES (?, ?, ?)",
            (symbol, shares, entry_price),
        )
    conn.commit()
    conn.close()
    return path


def _no_position_state_table_db():
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE risk_state (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);"
    )
    conn.commit()
    conn.close()
    return path


# --- populated -------------------------------------------------------------


def test_concentration_populated_from_real_positions_and_prices():
    db_path = _trades_db([("AAPL", 10.0, 190.0), ("MSFT", 4.0, 410.0)])
    try:
        with patch(_PRICES_METHOD, return_value=_ok({"AAPL": 200.0, "MSFT": 420.0})):
            screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        assert screen.concentration_is_available is True
        assert screen.concentration_is_empty is False
        by_symbol = {h.symbol: h for h in screen.concentration_holdings}
        # AAPL: 10*200=2000, MSFT: 4*420=1680, total=3680
        assert round(by_symbol["AAPL"].weight_pct, 2) == round(2000 / 3680 * 100, 2)
        assert round(by_symbol["MSFT"].weight_pct, 2) == round(1680 / 3680 * 100, 2)
        assert all(isinstance(h, ConcentrationHolding) for h in screen.concentration_holdings)
    finally:
        import os
        os.remove(db_path)


def test_concentration_weight_pct_matches_build_portfolio_holdings_verbatim():
    """Regression guard: this section must not recompute a weight itself --
    it reuses bootstrap._build_portfolio_holdings' own PortfolioHolding.
    weight_pct, field for field."""
    from applications.trading_intelligence.adapters.legacy_position_source import OpenPosition

    db_path = _trades_db([("AAPL", 10.0, 190.0), ("MSFT", 4.0, 410.0)])
    try:
        with patch(_PRICES_METHOD, return_value=_ok({"AAPL": 200.0, "MSFT": 420.0})):
            screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        direct = bootstrap._build_portfolio_holdings(
            (
                OpenPosition(symbol="AAPL", quantity=10.0, entry_price=190.0),
                OpenPosition(symbol="MSFT", quantity=4.0, entry_price=410.0),
            ),
            {"AAPL": 200.0, "MSFT": 420.0},
        )
        expected = {h.symbol: h.weight_pct for h in direct}
        actual = {h.symbol: h.weight_pct for h in screen.concentration_holdings}
        assert actual == expected
    finally:
        import os
        os.remove(db_path)


# --- empty -------------------------------------------------------------


def test_concentration_empty_when_no_open_positions():
    db_path = _trades_db([])
    try:
        screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        assert screen.concentration_is_available is True
        assert screen.concentration_is_empty is True
        assert screen.concentration_holdings == ()
    finally:
        import os
        os.remove(db_path)


# --- unavailable ---------------------------------------------------------


def test_concentration_unavailable_when_position_state_table_is_missing():
    db_path = _no_position_state_table_db()
    try:
        screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        assert screen.concentration_is_available is False
        assert screen.concentration_holdings is None
        assert screen.concentration_health is not None
        assert not screen.concentration_health.is_healthy
    finally:
        import os
        os.remove(db_path)


def test_concentration_unavailable_when_no_trades_db_at_all():
    screen = bootstrap._build_risk_intelligence_screen(db_path="no-such-trades-db-zzz.db")

    assert screen.concentration_is_available is False
    assert screen.concentration_holdings is None


def test_source_failure_does_not_fabricate_concentration_when_prices_fail():
    """Real open positions exist, but the live price read fails -- must
    never mix a real position with a fabricated/zero price, and must never
    silently fall back to an empty (healthy-looking) concentration list."""
    db_path = _trades_db([("AAPL", 10.0, 190.0)])
    try:
        failed = ReadResult.failed(IntegrationHealth.unavailable("live_prices"))
        with patch(_PRICES_METHOD, return_value=failed):
            screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        assert screen.concentration_is_available is False
        assert screen.concentration_holdings is None
        assert screen.concentration_health is not None
        assert not screen.concentration_health.is_healthy
    finally:
        import os
        os.remove(db_path)


# --- independence from existing Risk State / Drawdown behavior -----------


def test_concentration_is_independent_of_current_risk_state_availability():
    """No risk_governor_state row -> current risk state stays unavailable,
    but a real, independently-fetched concentration must still populate --
    same independence drawdown_history already has."""
    db_path = _trades_db([("AAPL", 10.0, 190.0)])
    try:
        with patch(_PRICES_METHOD, return_value=_ok({"AAPL": 200.0})):
            screen = bootstrap._build_risk_intelligence_screen(db_path=db_path)

        assert screen.is_available is False  # current risk state: unavailable
        assert screen.concentration_is_available is True  # concentration: still real
    finally:
        import os
        os.remove(db_path)


def test_existing_risk_state_and_drawdown_behavior_remain_intact():
    """Regression guard: adding Concentration must not disturb the
    existing current-state / drawdown-history wiring in the same
    function."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO risk_state (key, value, updated_at) VALUES "
        "('risk_governor_state', 'WARNING', '2026-09-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots VALUES "
        "('2026-09-01T00:00:00+00:00', 100000.0, 0.0, 0)"
    )
    conn.commit()
    conn.close()
    try:
        screen = bootstrap._build_risk_intelligence_screen(db_path=path)

        assert screen.is_available is True
        assert screen.current.state == "WARNING"
        assert screen.drawdown_history_is_available is True
        assert len(screen.drawdown_history) == 1
        # No positions inserted -> concentration is real-empty, not unavailable.
        assert screen.concentration_is_available is True
        assert screen.concentration_holdings == ()
    finally:
        import os
        os.remove(path)
