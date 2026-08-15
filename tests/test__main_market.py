"""Tests for bot/_main_market.py.

Covers _load_premarket_sentiment -- the (scores, saved_at) contract that
threads news_data_timestamp through to decision_events.market_context
(Phase 1A prerequisite #1, CURRENT_ARCHITECTURE.md) -- and, per ADR-026,
the two market-data pipeline defect corrections: _is_market_hours()'s
get_calendar() call shape (Fix 1) and _fetch_symbol()'s preservation of
valid yfinance daily bars when only the Alpaca 5-min feed is stale
(Fix 2)."""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
from alpaca.trading.requests import GetCalendarRequest

from bot._main_market import _fetch_symbol, _is_market_hours, _load_premarket_sentiment
import bot._main_market as main_market


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


# --- _is_market_hours / get_calendar (ADR-026 Fix 1) ---

class _FixedDatetime:
    """Stand-in for the module's `datetime` name -- datetime.datetime itself
    can't be monkeypatched (built-in/immutable type), so _is_market_hours'
    `from datetime import datetime; datetime.now(tz)` call is redirected at
    the module level instead. now() still returns a real datetime instance
    (a fixed Monday) so every other real-datetime method _is_market_hours
    calls on it (.weekday(), .replace(), arithmetic with timedelta) works
    unmodified."""
    _fixed = datetime(2026, 8, 17, 10, 0, 0)  # a real Monday, 10:00 local

    @classmethod
    def now(cls, tz=None):
        return cls._fixed.replace(tzinfo=tz) if tz else cls._fixed


def test_is_market_hours_calls_get_calendar_with_typed_request(monkeypatch):
    """ADR-026 Fix 1: get_calendar() must be called with a GetCalendarRequest
    via filters=, not bare start=/end= kwargs -- the shape the currently
    installed alpaca-py SDK actually requires."""
    main_market._market_holiday_cache.clear()
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)

    mock_api = MagicMock()
    mock_api.get_calendar.return_value = [MagicMock()]  # non-empty → not a holiday

    _is_market_hours(alpaca_api=mock_api)

    assert mock_api.get_calendar.call_count == 1
    _, kwargs = mock_api.get_calendar.call_args
    assert "filters" in kwargs
    assert isinstance(kwargs["filters"], GetCalendarRequest)
    assert kwargs["filters"].start == date(2026, 8, 17)
    assert kwargs["filters"].end == date(2026, 8, 17)
    # Old, broken call shape must not be used.
    assert "start" not in kwargs
    assert "end" not in kwargs


def test_is_market_hours_falls_back_when_get_calendar_still_raises(monkeypatch):
    """The existing fallback (hardcoded holiday list) must still work if
    get_calendar() raises for any reason -- ADR-026 fixes the call shape,
    it does not remove this safety net."""
    main_market._market_holiday_cache.clear()
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)

    mock_api = MagicMock()
    mock_api.get_calendar.side_effect = TypeError("boom")

    result = _is_market_hours(alpaca_api=mock_api)

    assert isinstance(result, bool)  # did not raise; fell back cleanly


# --- _fetch_symbol (ADR-026 Fix 2) ---

def _stale_5m_bars() -> pd.DataFrame:
    old_ts = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=45)
    return pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex([old_ts]))


def test_fetch_symbol_preserves_daily_bars_when_5m_feed_stale():
    """ADR-026 Fix 2: a stale Alpaca 5-min feed must empty only bars_5m --
    a genuinely fetched yfinance daily bar for the same symbol must still
    be returned, not discarded alongside the unrelated stale feed."""
    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()

    yf_batch = {"AAPL": pd.DataFrame({
        "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0],
    })}

    fake_daily = pd.DataFrame({"close": [150.0]})
    with patch("bot._main_market.compute_features", return_value=fake_daily) as mock_cf:
        symbol, bars_5m, bars_daily = _fetch_symbol("AAPL", client, yf_batch)

    assert symbol == "AAPL"
    assert bars_5m.empty
    assert not bars_daily.empty
    assert bars_daily.equals(fake_daily)
    mock_cf.assert_called_once()


def test_fetch_symbol_both_empty_when_yfinance_also_has_nothing():
    """Control case: if yfinance's own batch has nothing for the symbol
    either, both feeds are correctly empty -- Fix 2 only stops a stale
    5-min feed from discarding a daily bar that genuinely exists."""
    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()

    symbol, bars_5m, bars_daily = _fetch_symbol("ZZZZ", client, yf_batch={})

    assert symbol == "ZZZZ"
    assert bars_5m.empty
    assert bars_daily.empty
