"""ADR-081 Tier 2: restrictive-only fixes to entry sizing and the earnings gate."""
import sqlite3
import sys
import types

import pytest

from bot import _main_market as mk
from bot.risk import risk_manager as rmod


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE earnings_cache (symbol TEXT PRIMARY KEY, near_earnings INTEGER, cached_at TEXT)")
    yield c
    c.close()


def _fake_yf(monkeypatch, raises: bool):
    class _Ticker:
        def __init__(self, symbol):
            if raises:
                raise RuntimeError("yfinance down")
            self.calendar = {"Earnings Date": []}

    fake = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake)


def test_earnings_lookup_failure_blocks_and_is_not_cached(con, monkeypatch):
    _fake_yf(monkeypatch, raises=True)
    assert mk._is_near_earnings(con, "AAPL") is True  # unknown is not safe
    cached = con.execute("SELECT * FROM earnings_cache WHERE symbol='AAPL'").fetchall()
    assert cached == []  # the failure must not be cached, so the next cycle retries


def test_earnings_lookup_success_is_cached_as_before(con, monkeypatch):
    _fake_yf(monkeypatch, raises=False)
    assert mk._is_near_earnings(con, "AAPL") is False
    rows = con.execute("SELECT near_earnings FROM earnings_cache WHERE symbol='AAPL'").fetchall()
    assert rows == [(0,)]


def test_prefetch_failure_blocks_and_is_not_cached(con, monkeypatch):
    _fake_yf(monkeypatch, raises=True)
    out = mk._prefetch_earnings_parallel(con, ["AAPL", "MSFT"])
    assert out == {"AAPL": True, "MSFT": True}
    assert con.execute("SELECT COUNT(*) FROM earnings_cache").fetchone()[0] == 0


def test_kelly_negative_edge_sizes_to_zero(monkeypatch):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE trades (symbol TEXT, action TEXT, pnl_pct REAL, timestamp TEXT)")
    # 12 closed trades, 2 wins of +1% and 10 losses of -3%: negative expected value.
    rows = [("AAPL", "SELL", 0.01, f"2026-01-{i:02d}") for i in range(1, 3)] + \
           [("AAPL", "SELL", -0.03, f"2026-02-{i:02d}") for i in range(1, 11)]
    c.executemany("INSERT INTO trades VALUES (?,?,?,?)", rows)
    assert rmod.kelly_fraction(c, "AAPL") == 0.0


def test_kelly_positive_edge_keeps_floor_and_cap():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE trades (symbol TEXT, action TEXT, pnl_pct REAL, timestamp TEXT)")
    rows = [("AAPL", "SELL", 0.05, f"2026-01-{i:02d}") for i in range(1, 11)] + \
           [("AAPL", "SELL", -0.01, f"2026-02-{i:02d}") for i in range(1, 4)]
    c.executemany("INSERT INTO trades VALUES (?,?,?,?)", rows)
    f = rmod.kelly_fraction(c, "AAPL")
    assert f >= 0.02
    assert f <= rmod.KELLY_FRACTION_MAX
