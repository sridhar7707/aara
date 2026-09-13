"""Tests for adapters.trades_db_recommendation_diff_source.TradesDbRecommendationDiffSource."""
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from applications.trading_intelligence.adapters.legacy_recommendation_source import (
    LegacyRecommendationSource,
)
from applications.trading_intelligence.adapters.trades_db_recommendation_diff_source import (
    TradesDbRecommendationDiffSource,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError


def _create_recommendations_db(rows):
    """A real, temporary SQLite file with a populated recommendations
    table -- mirrors test_legacy_recommendation_source.py's own fixture."""
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE recommendations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, "
        "prediction_date TEXT NOT NULL, recommendation TEXT, confidence REAL, "
        "prev_recommendation TEXT, price_at_recommendation REAL, created_at TEXT, "
        "UNIQUE(symbol, prediction_date))"
    )
    for symbol, prediction_date, recommendation, confidence in rows:
        conn.execute(
            "INSERT INTO recommendations "
            "(symbol, prediction_date, recommendation, confidence) VALUES (?, ?, ?, ?)",
            (symbol, prediction_date, recommendation, confidence),
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def source_with_db():
    paths = []

    def _make(rows):
        path = _create_recommendations_db(rows)
        paths.append(path)
        return LegacyRecommendationSource(db_path=path)

    yield _make
    for path in paths:
        os.remove(path)


def _now_provider(fixed_now):
    return lambda: fixed_now


def test_get_diff_calls_diff_recommendation_snapshots_when_both_snapshots_are_real(source_with_db):
    recommendation_source = source_with_db([
        ("AAPL", "2026-09-01", "BUY", 0.61),
        ("AAPL", "2026-09-05", "WAIT", 0.48),
    ])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is not None
    assert diff.symbol == "AAPL"
    assert diff.before_recommendation == "BUY"
    assert diff.after_recommendation == "WAIT"
    assert diff.is_unchanged is False


def test_get_diff_returns_none_when_before_snapshot_is_missing(source_with_db):
    recommendation_source = source_with_db([
        ("AAPL", "2026-09-05", "WAIT", 0.48),
    ])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_returns_none_when_after_snapshot_is_missing(source_with_db):
    recommendation_source = source_with_db([
        ("AAPL", "2026-09-01", "BUY", 0.61),
    ])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_returns_none_when_both_snapshots_are_missing(source_with_db):
    recommendation_source = source_with_db([])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is None


def test_get_diff_raises_on_non_healthy_read():
    missing_db_source = LegacyRecommendationSource(db_path="does-not-exist.db")
    diff_source = TradesDbRecommendationDiffSource(
        missing_db_source, now_provider=_now_provider(datetime(2026, 9, 5, tzinfo=timezone.utc)),
    )

    with pytest.raises(TradingIntelligenceReadError):
        diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))


def test_get_diff_uses_exact_yyyy_mm_dd_date_strings(source_with_db, monkeypatch):
    captured_dates = []
    recommendation_source = source_with_db([])
    original_get_snapshot = recommendation_source.get_snapshot

    def _spy(symbol, prediction_date):
        captured_dates.append(prediction_date)
        return original_get_snapshot(symbol, prediction_date)

    monkeypatch.setattr(recommendation_source, "get_snapshot", _spy)
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source,
        now_provider=_now_provider(datetime(2026, 9, 5, 23, 59, tzinfo=timezone.utc)),
    )

    diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 30, 0))

    assert captured_dates == ["2026-09-01", "2026-09-05"]


def test_get_diff_after_date_comes_from_injected_now_provider(source_with_db):
    recommendation_source = source_with_db([
        ("AAPL", "2026-09-01", "BUY", 0.61),
        ("AAPL", "2026-12-25", "BUY", 0.55),
    ])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source,
        now_provider=_now_provider(datetime(2026, 12, 25, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 1, 14, 0, 0))

    assert diff is not None
    assert diff.after_prediction_date == "2026-12-25"


def test_get_diff_same_day_decision_compares_identical_snapshot_naturally(source_with_db):
    """No special-case logic: a same-day decision reads the identical row
    for both 'before' and 'after', which diff_recommendation_snapshots()
    (unmodified) already reports as is_unchanged=True on its own."""
    recommendation_source = source_with_db([
        ("AAPL", "2026-09-05", "BUY", 0.61),
    ])
    diff_source = TradesDbRecommendationDiffSource(
        recommendation_source,
        now_provider=_now_provider(datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc)),
    )

    diff = diff_source.get_diff("AAPL", datetime(2026, 9, 5, 9, 0, 0))

    assert diff is not None
    assert diff.is_unchanged is True
