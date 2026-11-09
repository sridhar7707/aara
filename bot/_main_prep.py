"""Once-per-cycle preparation glue, extracted from bot/main.py::run() to keep
that file under the project's 500-line limit — everything here runs exactly
once per cycle, before the per-symbol decision loop starts."""
from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, timezone

import pandas as pd
from loguru import logger

import bot.monitor.telegram_bot as tg
from bot.execution.alpaca_client import AlpacaClient
from bot.risk.risk_manager import RiskManager
from bot._main_db import _get_macro_from_db, _record_snapshot, _save_risk_state


def write_heartbeat_if_consistent(
    con: sqlite3.Connection, client: AlpacaClient, positions: dict,
    real_portfolio_value: float, real_available_cash: float,
) -> bool:
    """Record the real account value on every cycle (ADR-088, revised 2026-11-08).

    Skipping snapshots was rejected: the skipped points are the deepest-drawdown readings,
    so skipping them biases max drawdown and Sharpe. The value is always written. The
    open-position count comes from the live read; if that read is empty while the database
    holds open positions, the database count is written and the mismatch is logged.
    Returns True (kept for the caller's signature).
    """
    db_count = con.execute("SELECT COUNT(*) FROM position_state").fetchone()[0]
    open_count = len(positions) if positions else db_count
    if not positions and db_count:
        _logger.warning(
            f"Heartbeat: positions read empty while the database holds {db_count} open "
            "position(s); recording the account value with the database count (ADR-088)."
        )
    _record_snapshot(con, real_portfolio_value, real_available_cash, open_count)
    return True
from bot.db.macro_cache import (
    get_macro_halt_reason as _get_macro_halt_reason_from_db,
    REASON_DATA_UNAVAILABLE,
)
from bot._main_market import (
    _compute_sentiments, _load_premarket_sentiment, _prefetch_earnings_parallel, prefetch_bars,
)
from config import RS_LOOKBACK_BARS

_logger = logger


def prepare_cycle_context(
    con: sqlite3.Connection, client: AlpacaClient, risk: RiskManager, mode: str,
    daily_start: float | None, real_portfolio_value: float, real_available_cash: float,
    portfolio_value: float, positions: dict, active_symbols: list[str],
) -> tuple[set, set, float, float, bool, dict, dict, float | None, float, dict, str | None]:
    """Halt-state restore, first-cycle-of-day alert, daily risk reset, connection
    telemetry, heartbeat snapshot, loss-limit alerts, macro state, and market
    data prefetch (bars/sentiment/earnings/SPY context) — everything the
    per-symbol loop needs but that only needs to run once per cycle.

    Returns (buy_order_syms, sell_order_syms, macro_score, macro_cap, macro_halt,
    bars_map, sentiments, spy_5bar_return, vs_spy_today, earnings_map,
    news_data_timestamp).
    """
    buy_order_syms, sell_order_syms = client.get_open_order_symbols()

    # Restore intraday halt — persists across 5-min cycles so a mid-day breach
    # can't be traded through when the risk object is reconstructed each cycle.
    _halt_row = con.execute(
        "SELECT value FROM risk_state WHERE key='trading_halted_date'"
    ).fetchone()
    if _halt_row and _halt_row[0] == date.today().isoformat():
        risk.halted = True
        _logger.warning("Halt state restored from DB — daily loss limit was breached earlier today")

    # First cycle of the day — daily_start was None before reset_daily sets it
    if daily_start is None:
        tg.alert_bot_started(mode, real_portfolio_value)

    # Always reset daily using the REAL account value so the dashboard's Day P&L
    # baseline matches what Alpaca actually shows — not the sim-capped value.
    risk.reset_daily(real_portfolio_value)
    _save_risk_state(con, risk)

    _logger.info(
        f"Portfolio: ${real_portfolio_value:.2f} (sim: ${portfolio_value:.2f}) | "
        f"Cash: ${real_available_cash:.2f} | "
        f"Open positions: {list(positions.keys())} | "
        f"Pending buys: {buy_order_syms} | Pending sells: {sell_order_syms}"
    )
    # Heartbeat snapshot — always stores the REAL account value so the dashboard
    # portfolio total is correct regardless of PAPER_SIM_CAPITAL.
    write_heartbeat_if_consistent(con, client, positions, real_portfolio_value, real_available_cash)
    if sell_order_syms:
        _logger.warning(
            f"Open sell orders detected for {len(sell_order_syms)} symbol(s): {sell_order_syms} "
            "— exit management paused for these symbols this cycle"
        )

    # Early warning: once per day when portfolio crosses 50% of daily loss limit
    if risk.check_daily_loss_warning(portfolio_value):
        pnl_warn = (portfolio_value - risk.daily_start_value) / risk.daily_start_value
        tg.alert_risk_warning(portfolio_value, pnl_warn)
        risk.daily_warning_sent = True
        _save_risk_state(con, risk)

    macro_score, macro_cap, macro_halt = _get_macro_from_db(con)
    macro_halt_reason = _get_macro_halt_reason_from_db(con)
    _logger.info(f"Macro: score={macro_score:.2f}, cap={macro_cap:.1f}x, halt={macro_halt}")
    if macro_halt:
        # Amendment 1 to ADR-010: macro_halt=True has two causes — a genuine VIX
        # breach, or FRED/macro data being unavailable (fail-closed). Only the
        # former is a "VIX halt"; the latter already got its own, accurate
        # Telegram alert from bot/db/macro_cache.py::get_macro() at the point of
        # failure, so alert_vix_halt() must not also fire for it. If reason is
        # None (no observational metadata yet — e.g. a within-TTL cached halt
        # written before this amendment shipped), default to the pre-amendment
        # behavior rather than staying silent about an active halt.
        if macro_halt_reason == REASON_DATA_UNAVAILABLE:
            _logger.warning("Macro data unavailable — no new buys this cycle (FRED outage, not a VIX breach)")
        else:
            _logger.warning("VIX emergency halt active — no new buys this cycle")
            tg.alert_vix_halt()  # fires every cycle — VIX crisis events warrant repeated alerts

    # Weekly loss circuit breaker alert — sent once per week when limit is first hit
    if not risk.check_weekly_loss(portfolio_value) and not risk.weekly_halt_alerted:
        wk_pnl = (portfolio_value - risk.weekly_start_value) / risk.weekly_start_value
        tg.alert_weekly_loss_limit(portfolio_value, wk_pnl)
        risk.weekly_halt_alerted = True
        _save_risk_state(con, risk)

    premarket_sentiment, news_data_timestamp = _load_premarket_sentiment()
    if not premarket_sentiment:
        _logger.warning(
            "Pre-market sentiment unavailable — sentiment defaults to neutral (0.0) this cycle. "
            "NewsAPI quota (100 req/day) is not consumed in-cycle."
        )

    bars_map   = prefetch_bars(active_symbols, client)
    sentiments = _compute_sentiments(active_symbols, premarket_sentiment)

    # Pre-compute SPY N-bar return for relative strength gate (daily bars so it matches sig_bars)
    _, spy_daily = bars_map.get("SPY", (pd.DataFrame(), pd.DataFrame()))
    spy_5bar_return: float | None = None
    if not spy_daily.empty and len(spy_daily) > RS_LOOKBACK_BARS:
        v = spy_daily["close"].pct_change(RS_LOOKBACK_BARS).iloc[-1]
        if not math.isnan(v):
            spy_5bar_return = float(v)

    # Use already-fetched SPY daily bars (yfinance) — avoids redundant Alpaca call that
    # returns only 1 bar on the IEX free tier
    vs_spy_today = 0.0
    if not spy_daily.empty and len(spy_daily) > 1:
        _v = spy_daily["close"].pct_change().iloc[-1]
        if not math.isnan(_v):
            vs_spy_today = float(_v)

    # Prefetch earnings proximity in parallel — avoids 25 sequential yfinance HTTP calls
    earnings_map = _prefetch_earnings_parallel(con, active_symbols)

    return (buy_order_syms, sell_order_syms, macro_score, macro_cap, macro_halt,
            bars_map, sentiments, spy_5bar_return, vs_spy_today, earnings_map,
            news_data_timestamp)


TRUSTED_KEY = "last_trusted_portfolio_value"
SANITY_DROP_LIMIT = 0.50


def load_trusted_value(con: sqlite3.Connection) -> float | None:
    row = con.execute("SELECT value FROM risk_state WHERE key = ?", (TRUSTED_KEY,)).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def save_trusted_value(con: sqlite3.Connection, value: float) -> None:
    con.execute(
        "INSERT INTO risk_state (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (TRUSTED_KEY, repr(float(value)), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()


def sanity_check(con: sqlite3.Connection, real_value: float) -> tuple[bool, float | None]:
    """Return (blocked, baseline). Baseline = last trusted value, else the latest snapshot
    (first run only). A blocked reading is never saved, so it cannot become the baseline."""
    baseline = load_trusted_value(con)
    if baseline is None:
        row = con.execute(
            "SELECT portfolio_value FROM portfolio_snapshots "
            "WHERE portfolio_value > 0 ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        baseline = float(row[0]) if row else None
    blocked = bool(baseline) and real_value < baseline * SANITY_DROP_LIMIT
    if not blocked:
        save_trusted_value(con, real_value)
        record_trusted_anchors(con, real_value)
    return bool(blocked), baseline


def current_week_key() -> str:
    return date.today().strftime("%G-W%V")


def record_trusted_anchors(con: sqlite3.Connection, value: float) -> None:
    """Record once-only anchors from trusted readings (decided 2026-11-09): the first trusted
    value ever (capital pool fallback) and the first trusted value of each ISO week (weekly
    P&L baseline). Blocked readings never reach here."""
    now = datetime.now(timezone.utc).isoformat()
    for key in ["first_trusted_value", f"week_trusted_start:{current_week_key()}"]:
        if con.execute("SELECT 1 FROM risk_state WHERE key = ?", (key,)).fetchone() is None:
            con.execute(
                "INSERT INTO risk_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, repr(float(value)), now),
            )
    con.commit()
