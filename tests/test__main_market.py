"""Tests for bot/_main_market.py::_load_premarket_sentiment -- the
(scores, saved_at) contract that threads news_data_timestamp through to
decision_events.market_context (Phase 1A prerequisite #1,
CURRENT_ARCHITECTURE.md)."""
from __future__ import annotations

import json
import os

from bot._main_market import _load_premarket_sentiment


def test_load_premarket_sentiment_returns_scores_and_saved_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    from datetime import date
    with open("data/sentiment_today.json", "w") as f:
        json.dump({
            "date": date.today().isoformat(),
            "saved_at": "2026-07-29T12:00:00+00:00",
            "scores": {"AAPL": 0.5, "MSFT": -0.2},
        }, f)

    scores, saved_at = _load_premarket_sentiment()

    assert scores == {"AAPL": 0.5, "MSFT": -0.2}
    assert saved_at == "2026-07-29T12:00:00+00:00"


def test_load_premarket_sentiment_missing_file_returns_empty_and_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    scores, saved_at = _load_premarket_sentiment()

    assert scores == {}
    assert saved_at is None


def test_load_premarket_sentiment_stale_date_returns_empty_and_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    with open("data/sentiment_today.json", "w") as f:
        json.dump({
            "date": "2020-01-01",
            "saved_at": "2020-01-01T12:00:00+00:00",
            "scores": {"AAPL": 0.5},
        }, f)

    scores, saved_at = _load_premarket_sentiment()

    assert scores == {}
    assert saved_at is None


def test_load_premarket_sentiment_empty_scores_returns_empty_and_none(tmp_path, monkeypatch):
    """An empty scores dict is treated the same as no snapshot at all --
    _compute_sentiments falls back to WSB-only, so there's no premarket
    news timestamp to report either."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    from datetime import date
    with open("data/sentiment_today.json", "w") as f:
        json.dump({
            "date": date.today().isoformat(),
            "saved_at": "2026-07-29T12:00:00+00:00",
            "scores": {},
        }, f)

    scores, saved_at = _load_premarket_sentiment()

    assert scores == {}
    assert saved_at is None
