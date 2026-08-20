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
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from alpaca.trading.requests import GetCalendarRequest

import config
from bot._main_market import (
    _fetch_symbol, _is_market_hours, _load_premarket_sentiment, _trim_incomplete_daily_bar,
)
import bot._main_market as main_market
from bot.strategy.features import compute_features, FEATURE_COLS_V4
from tests.conftest import make_ohlcv


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


# --- ADR-040: exclude in-progress "today" daily bar before compute_features() ---

def _daily_ohlcv(n: int = 270, end: date = date(2026, 8, 17), seed: int = 42) -> pd.DataFrame:
    """Realistic daily OHLCV (via conftest.make_ohlcv) with a business-day
    DatetimeIndex ending at `end` -- mirrors the shape prefetch_bars() hands
    _fetch_symbol() (yf_batch[sym] indexed by trading date, as yf.download()
    returns it)."""
    df = make_ohlcv(n, seed=seed)
    df.index = pd.bdate_range(end=end, periods=n)
    return df


# _FixedDatetime._fixed is 2026-08-17 10:00 local (a real Monday) -- reused
# here so "today" in America/New_York resolves the same way it does for the
# _is_market_hours tests above. The prior business day is Friday 2026-08-14.

def test_trim_incomplete_daily_bar_drops_todays_row(monkeypatch):
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    df = _daily_ohlcv(270, end=date(2026, 8, 17))
    expected = df.iloc[:-1]

    result = _trim_incomplete_daily_bar(df)

    pd.testing.assert_frame_equal(result, expected)


def test_trim_incomplete_daily_bar_noop_when_last_row_not_today(monkeypatch):
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    df = _daily_ohlcv(270, end=date(2026, 8, 14))  # last row is Friday, not "today"

    result = _trim_incomplete_daily_bar(df)

    pd.testing.assert_frame_equal(result, df)


def test_trim_incomplete_daily_bar_handles_none():
    assert _trim_incomplete_daily_bar(None) is None


def test_trim_incomplete_daily_bar_handles_empty():
    result = _trim_incomplete_daily_bar(pd.DataFrame())
    assert result.empty


def test_fetch_symbol_excludes_in_progress_today_bar(monkeypatch):
    """ADR-040 §5 item 1: an in-progress "today" daily bar must not reach
    compute_features() -- bars_daily's last index date must be the prior
    completed session, not today."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    raw = _daily_ohlcv(270, end=date(2026, 8, 17))
    expected_last = raw.index[-2]  # prior completed session

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": raw.copy()}

    _, _, bars_daily = _fetch_symbol("AAPL", client, yf_batch)

    assert bars_daily.index[-1] == expected_last
    assert bars_daily.index[-1].date() != date(2026, 8, 17)


def test_fetch_symbol_daily_features_match_pretrimmed_reference(monkeypatch):
    """ADR-040 §5 items 2 & 4: bars_daily's latest row, across every one of
    the 22 FEATURE_COLS_V4 columns, must be bit-identical to computing
    features directly on the raw frame with the synthetic today-row removed
    beforehand -- proving the trim point is equivalent to computing features
    on an already-pre-trimmed frame."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    raw = _daily_ohlcv(280, end=date(2026, 8, 17))

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": raw.copy()}

    _, _, bars_daily = _fetch_symbol("AAPL", client, yf_batch)
    reference = compute_features(raw.iloc[:-1].copy())

    assert len(FEATURE_COLS_V4) == 22
    for col in FEATURE_COLS_V4:
        assert bars_daily.iloc[-1][col] == reference.iloc[-1][col], f"mismatch in {col}"


def test_min_volume_ratio_gate_unchanged():
    """ADR-040 §5 item 6: this ADR's trim must not require, and did not
    receive, any change to MIN_VOLUME_RATIO or the Gate 2 comparison that
    reads it -- both stay exactly as they were before this ADR."""
    assert config.MIN_VOLUME_RATIO == 0.3

    cycle_src = (Path(__file__).parent.parent / "bot" / "_main_cycle.py").read_text(encoding="utf-8")
    lines = cycle_src.splitlines()
    assert lines[109] == "    if ctx.volume_ratio < MIN_VOLUME_RATIO:"  # line 110 (1-indexed)


def test_fetch_symbol_spy_rs_trim_before_close_derivation(monkeypatch):
    """ADR-040 §5 item 7 (part 1): for a non-SPY symbol, an in-progress
    "today" SPY bar must be trimmed before spy_close is derived from it --
    rs_vs_spy_21d/63d must match a reference computed from SPY with that
    row excluded, not from the untrimmed SPY close."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)

    aapl_raw = _daily_ohlcv(280, end=date(2026, 8, 14), seed=1)  # AAPL: historical, not "today"
    spy_hist = _daily_ohlcv(280, end=date(2026, 8, 14), seed=2)  # same date index as aapl_raw
    today_row = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=[pd.Timestamp(date(2026, 8, 17))],
    )
    spy_raw = pd.concat([spy_hist, today_row])  # SPY: last row IS "today"

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": aapl_raw.copy(), "SPY": spy_raw.copy()}

    _, _, bars_daily = _fetch_symbol("AAPL", client, yf_batch)

    reference = compute_features(aapl_raw.copy(), spy_close=spy_hist["close"])

    assert bars_daily.iloc[-1]["rs_vs_spy_21d"] == reference.iloc[-1]["rs_vs_spy_21d"]
    assert bars_daily.iloc[-1]["rs_vs_spy_63d"] == reference.iloc[-1]["rs_vs_spy_63d"]


def test_fetch_symbol_spy_missing_key_stays_safe(monkeypatch):
    """ADR-040 §5 item 7 (part 2): the trim must preserve the existing
    missing-SPY safety -- no "SPY" key in yf_batch at all must still return
    successfully, with rs_vs_spy_21d/63d at their existing null-SPY default."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    aapl_raw = _daily_ohlcv(270, end=date(2026, 8, 14), seed=1)

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": aapl_raw.copy()}  # no "SPY" key at all

    symbol, bars_5m, bars_daily = _fetch_symbol("AAPL", client, yf_batch)

    assert symbol == "AAPL"
    assert not bars_daily.empty
    assert (bars_daily["rs_vs_spy_21d"] == 0.0).all()
    assert (bars_daily["rs_vs_spy_63d"] == 0.0).all()


def test_fetch_symbol_spy_empty_frame_stays_safe(monkeypatch):
    """ADR-040 §5 item 7 (part 2): an empty "SPY" frame in yf_batch must
    also stay safe -- same existing null-SPY default, no exception."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    aapl_raw = _daily_ohlcv(270, end=date(2026, 8, 14), seed=1)

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": aapl_raw.copy(), "SPY": pd.DataFrame()}

    symbol, bars_5m, bars_daily = _fetch_symbol("AAPL", client, yf_batch)

    assert symbol == "AAPL"
    assert not bars_daily.empty
    assert (bars_daily["rs_vs_spy_21d"] == 0.0).all()
    assert (bars_daily["rs_vs_spy_63d"] == 0.0).all()


def test_fetch_symbol_bit_identical_predictions_for_historical_fixture(monkeypatch):
    """ADR-040 §5 item 5: the trim only activates when the last row is
    dated "today". For an already-complete historical fixture, bars_daily
    must be bit-identical to computing features on the untrimmed raw data --
    and therefore XGB/LSTM predict_proba on that identical input produce
    bit-identical output, whether or not ADR-040's trim code runs."""
    monkeypatch.setattr(main_market, "datetime", _FixedDatetime)
    raw = _daily_ohlcv(300, end=date(2026, 8, 10), seed=3)  # a week before "today" -- unambiguously historical

    client = MagicMock()
    client.get_bars.return_value = _stale_5m_bars()
    yf_batch = {"AAPL": raw.copy()}

    _, _, bars_daily = _fetch_symbol("AAPL", client, yf_batch)
    reference = compute_features(raw.copy())  # untrimmed -- trim must have been a no-op here

    pd.testing.assert_frame_equal(bars_daily, reference)

    from bot.strategy.xgb_predictor import XGBPredictor
    from bot.strategy.lstm_predictor import LSTMPredictor
    xgb = XGBPredictor()
    lstm = LSTMPredictor()
    if xgb.model is None or lstm.model is None:
        pytest.skip("No trained XGB/LSTM model on disk -- bit-identical predict_proba check requires one")

    assert xgb.predict_proba(bars_daily.iloc[-1]) == xgb.predict_proba(reference.iloc[-1])
    assert lstm.predict_proba(bars_daily) == lstm.predict_proba(reference)
