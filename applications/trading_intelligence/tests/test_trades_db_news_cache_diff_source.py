"""Tests for adapters.trades_db_news_cache_diff_source.TradesDbNewsCacheDiffSource."""
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from applications.trading_intelligence.adapters.legacy_news_cache_source import (
    LegacyNewsCacheSource,
)
from applications.trading_intelligence.adapters.trades_db_news_cache_diff_source import (
    TradesDbNewsCacheDiffSource,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError


def _create_news_cache_db(rows):
    """A real, temporary SQLite file with a populated news_cache table,
    matching bot/_main_db.py's own DDL -- mirrors
    test_legacy_news_cache_source.py's own fixture helper."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news_cache (symbol TEXT, fetch_date TEXT, "
        "headlines_json TEXT, cached_at TEXT, PRIMARY KEY (symbol, fetch_date))"
    )
    for symbol, fetch_date, headlines, cached_at in rows:
        conn.execute(
            "INSERT INTO news_cache VALUES (?, ?, ?, ?)",
            (symbol, fetch_date, json.dumps(headlines), cached_at),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def source_with_db():
    paths = []

    def _make(rows):
        path = _create_news_cache_db(rows)
        paths.append(path)
        return LegacyNewsCacheSource(db_path=path)

    yield _make
    for path in paths:
        os.remove(path)


def _now_provider(fixed_now):
    return lambda: fixed_now


def test_get_diff_calls_diff_news_cache_snapshots_when_both_snapshots_are_real(source_with_db):
    news_cache_source = source_with_db([
        ("AAPL", "2026-09-01", ["Headline A"], "2026-09-01 10:00:00"),
        ("AAPL", "2026-09-05", ["Headline A", "Headline B"], "2026-09-05 10:00:00"),
    ])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is not None
    assert diff.symbol == "AAPL"
    assert diff.added_headlines == ("Headline B",)
    assert diff.is_identical is False


def test_get_diff_returns_none_when_before_snapshot_is_missing(source_with_db):
    news_cache_source = source_with_db([
        ("AAPL", "2026-09-05", ["Headline A"], "2026-09-05 10:00:00"),
    ])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_returns_none_when_after_snapshot_is_missing(source_with_db):
    news_cache_source = source_with_db([
        ("AAPL", "2026-09-01", ["Headline A"], "2026-09-01 10:00:00"),
    ])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_returns_none_when_both_snapshots_are_missing(source_with_db):
    news_cache_source = source_with_db([])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_raises_on_non_healthy_read():
    missing_db_source = LegacyNewsCacheSource(db_path="does-not-exist.db")
    diff_source = TradesDbNewsCacheDiffSource(
        missing_db_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    with pytest.raises(TradingIntelligenceReadError):
        diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))


def test_get_diff_uses_exact_yyyy_mm_dd_date_strings(source_with_db, monkeypatch):
    captured_dates = []
    news_cache_source = source_with_db([])
    original_get_snapshot = news_cache_source.get_snapshot

    def _spy(symbol, fetch_date):
        captured_dates.append(fetch_date)
        return original_get_snapshot(symbol, fetch_date)

    monkeypatch.setattr(news_cache_source, "get_snapshot", _spy)
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, 23, 59, tzinfo=timezone.utc)),
    )

    diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 30, 0))

    assert captured_dates == ["2026-09-01", "2026-09-05"]


def test_get_diff_after_date_comes_from_injected_now_provider(source_with_db):
    news_cache_source = source_with_db([
        ("AAPL", "2026-09-01", ["Headline A"], "2026-09-01 10:00:00"),
        ("AAPL", "2026-12-25", ["Headline A"], "2026-12-25 10:00:00"),
    ])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 12, 25, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is not None
    assert diff.after_fetch_date == "2026-12-25"


def test_get_diff_same_day_decision_compares_identical_snapshot_naturally(source_with_db):
    """No special-case logic: a same-day decision reads the identical row
    for both 'before' and 'after', which diff_news_cache_snapshots() (
    unmodified) already reports as is_identical=True on its own."""
    news_cache_source = source_with_db([
        ("AAPL", "2026-09-05", ["Headline A"], "2026-09-05 10:00:00"),
    ])
    diff_source = TradesDbNewsCacheDiffSource(
        news_cache_source, now_provider=_now_provider(datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 5, 9, 0, 0))

    assert diff is not None
    assert diff.is_identical is True
