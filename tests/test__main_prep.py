"""Tests for bot/_main_prep.py::prepare_cycle_context — the once-per-cycle
orchestration glue extracted from bot/main.py::run().

External I/O (Alpaca client, market data prefetch, Telegram) is faked/mocked;
the sqlite connection is real (:memory:) so halt-restore and risk-state
persistence are verified end to end, matching this repo's existing style
(tests/phase1a/test_data_quality.py).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import bot._main_db as main_db
import bot._main_prep as prep
from bot.risk.risk_manager import RiskManager
from config import DAILY_LOSS_LIMIT_PCT, DAILY_LOSS_WARNING_PCT, WEEKLY_LOSS_LIMIT_PCT


class _FakeClient:
    def __init__(self, buy=None, sell=None):
        self._buy = buy or set()
        self._sell = sell or set()

    def get_open_order_symbols(self):
        return self._buy, self._sell


@pytest.fixture
def con():
    c = main_db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _stub_market_and_telegram(monkeypatch):
    """Neutral stand-ins for every external call prepare_cycle_context makes,
    beyond the DB and RiskManager. Individual tests override as needed."""
    calls = {"bot_started": [], "vix_halt": [], "risk_warning": [], "weekly_loss": []}
    monkeypatch.setattr(prep.tg, "alert_bot_started", lambda mode, pv: calls["bot_started"].append((mode, pv)))
    monkeypatch.setattr(prep.tg, "alert_vix_halt", lambda: calls["vix_halt"].append(True))
    monkeypatch.setattr(prep.tg, "alert_risk_warning", lambda pv, pnl: calls["risk_warning"].append((pv, pnl)))
    monkeypatch.setattr(prep.tg, "alert_weekly_loss_limit", lambda pv, pnl: calls["weekly_loss"].append((pv, pnl)))
    monkeypatch.setattr(prep, "_get_macro_from_db", lambda con: (0.5, 1.0, False))
    monkeypatch.setattr(prep, "_load_premarket_sentiment", lambda: ({"AAPL": 0.1}, "2026-07-29T12:00:00+00:00"))
    monkeypatch.setattr(prep, "prefetch_bars", lambda syms, client: {})
    monkeypatch.setattr(prep, "_compute_sentiments", lambda syms, premarket: {"AAPL": 0.1})
    monkeypatch.setattr(prep, "_prefetch_earnings_parallel", lambda con, syms: {"AAPL": False})
    return calls


def _call(con, client, risk, **overrides):
    kwargs = dict(
        con=con, client=client, risk=risk, mode="paper",
        daily_start=None, real_portfolio_value=100_000.0, real_available_cash=50_000.0,
        portfolio_value=100_000.0, positions={}, active_symbols=["AAPL"],
    )
    kwargs.update(overrides)
    return prep.prepare_cycle_context(**kwargs)


def test_first_cycle_of_day_sends_bot_started_alert(con, _stub_market_and_telegram):
    risk = RiskManager()
    _call(con, _FakeClient(), risk, daily_start=None)
    assert len(_stub_market_and_telegram["bot_started"]) == 1


def test_subsequent_cycle_does_not_resend_bot_started_alert(con, _stub_market_and_telegram):
    risk = RiskManager()
    _call(con, _FakeClient(), risk, daily_start=100_000.0)
    assert _stub_market_and_telegram["bot_started"] == []


def test_halt_state_restored_from_db_when_breached_today(con, _stub_market_and_telegram):
    con.execute(
        "INSERT OR REPLACE INTO risk_state (key, value, updated_at) VALUES (?,?,?)",
        ("trading_halted_date", date.today().isoformat(), "2026-07-29T00:00:00+00:00"),
    )
    con.commit()
    # Mid-day cycle restart: daily_start_value is already set (as it would be via
    # _load_risk_state in bot/main.py) — matters because RiskManager.reset_daily()
    # clears .halted whenever daily_start_value is None, which would otherwise mask
    # this test's own halt-restore assertion.
    risk = RiskManager(daily_start_value=100_000.0)
    assert risk.halted is False
    _call(con, _FakeClient(), risk, daily_start=100_000.0)
    assert risk.halted is True


def test_halt_state_not_restored_when_breach_was_a_prior_day(con, _stub_market_and_telegram):
    con.execute(
        "INSERT OR REPLACE INTO risk_state (key, value, updated_at) VALUES (?,?,?)",
        ("trading_halted_date", "2000-01-01", "2000-01-01T00:00:00+00:00"),
    )
    con.commit()
    risk = RiskManager()
    _call(con, _FakeClient(), risk)
    assert risk.halted is False


def test_macro_halt_triggers_vix_alert(con, _stub_market_and_telegram, monkeypatch):
    monkeypatch.setattr(prep, "_get_macro_from_db", lambda con: (0.9, 0.0, True))
    risk = RiskManager()
    result = _call(con, _FakeClient(), risk)
    assert len(_stub_market_and_telegram["vix_halt"]) == 1
    assert result[2:5] == (0.9, 0.0, True)  # macro_score, macro_cap, macro_halt


def test_macro_no_halt_does_not_alert(con, _stub_market_and_telegram):
    risk = RiskManager()
    _call(con, _FakeClient(), risk)
    assert _stub_market_and_telegram["vix_halt"] == []


def test_daily_loss_warning_zone_alerts_and_persists(con, _stub_market_and_telegram):
    risk = RiskManager(daily_start_value=100_000.0)
    warn_pct = (DAILY_LOSS_WARNING_PCT + DAILY_LOSS_LIMIT_PCT) / 2  # squarely inside the warning zone
    pv = 100_000.0 * (1 - warn_pct)
    _call(con, _FakeClient(), risk, daily_start=100_000.0, portfolio_value=pv)
    assert len(_stub_market_and_telegram["risk_warning"]) == 1
    assert risk.daily_warning_sent is True
    row = con.execute("SELECT value FROM risk_state WHERE key='daily_warning_sent_date'").fetchone()
    assert row[0] == date.today().isoformat()


def test_daily_loss_within_safe_zone_does_not_alert(con, _stub_market_and_telegram):
    risk = RiskManager(daily_start_value=100_000.0)
    _call(con, _FakeClient(), risk, daily_start=100_000.0, portfolio_value=99_900.0)
    assert _stub_market_and_telegram["risk_warning"] == []


def test_weekly_loss_breach_alerts_and_persists(con, _stub_market_and_telegram):
    risk = RiskManager(daily_start_value=100_000.0, weekly_start_value=100_000.0)
    pv = 100_000.0 * (1 - (WEEKLY_LOSS_LIMIT_PCT + 0.01))  # past the weekly circuit breaker
    _call(con, _FakeClient(), risk, daily_start=100_000.0, portfolio_value=pv)
    assert len(_stub_market_and_telegram["weekly_loss"]) == 1
    assert risk.weekly_halt_alerted is True
    row = con.execute("SELECT value FROM risk_state WHERE key='weekly_halt_alerted_week'").fetchone()
    assert row is not None and row[0] != ""


def test_weekly_loss_already_alerted_this_week_does_not_resend(con, _stub_market_and_telegram):
    risk = RiskManager(daily_start_value=100_000.0, weekly_start_value=100_000.0, weekly_halt_alerted=True)
    pv = 100_000.0 * (1 - (WEEKLY_LOSS_LIMIT_PCT + 0.01))
    _call(con, _FakeClient(), risk, daily_start=100_000.0, portfolio_value=pv)
    assert _stub_market_and_telegram["weekly_loss"] == []


def test_spy_returns_computed_from_prefetched_daily_bars(con, _stub_market_and_telegram, monkeypatch):
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]  # 6 bars, RS_LOOKBACK_BARS default 5
    spy_daily = pd.DataFrame({"close": closes})
    monkeypatch.setattr(prep, "prefetch_bars", lambda syms, client: {"SPY": (pd.DataFrame(), spy_daily)})

    result = _call(con, _FakeClient(), RiskManager())
    spy_5bar_return, vs_spy_today = result[7], result[8]

    expected_5bar = (closes[-1] - closes[0]) / closes[0]
    expected_today = (closes[-1] - closes[-2]) / closes[-2]
    assert spy_5bar_return == pytest.approx(expected_5bar)
    assert vs_spy_today == pytest.approx(expected_today)


def test_spy_returns_none_and_zero_without_spy_bars(con, _stub_market_and_telegram):
    result = _call(con, _FakeClient(), RiskManager())
    spy_5bar_return, vs_spy_today = result[7], result[8]
    assert spy_5bar_return is None
    assert vs_spy_today == 0.0


def test_returns_open_order_symbols_from_client(con, _stub_market_and_telegram):
    client = _FakeClient(buy={"AAPL"}, sell={"MSFT"})
    result = _call(con, client, RiskManager())
    assert result[0] == {"AAPL"}
    assert result[1] == {"MSFT"}


def test_returns_news_data_timestamp_from_premarket_sentiment(con, _stub_market_and_telegram):
    result = _call(con, _FakeClient(), RiskManager())
    assert result[10] == "2026-07-29T12:00:00+00:00"
