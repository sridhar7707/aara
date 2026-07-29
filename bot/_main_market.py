"""Market data, universe, and sentiment helpers extracted from bot/main.py."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import yfinance as yf
from loguru import logger

from bot.execution.alpaca_client import AlpacaClient
from bot.strategy.features import compute_features
from bot.strategy.reddit_sentiment import get_wsb_sentiment
from bot._main_positions import BarData
from config import EARNINGS_WINDOW_DAYS, MARKET_OPEN_BUFFER_MINS, MARKET_CLOSE_BUFFER_MINS, SYMBOLS

_UNIVERSE_PATH   = "data/universe_today.json"
# All ETF-like instruments in the universe — no earnings dates, skip earnings prefetch.
# Keep in sync with config.SYMBOLS whenever new ETFs are added.
_ETF_SYMBOLS     = {"VOO", "QQQ", "SPY", "VTI", "ARKK", "IWM", "GLD", "XLE", "XLF", "XLV"}
_EARNINGS_DB_TTL = 12 * 3600

_wsb_cache: dict[str, tuple[float, dict]] = {}
_WSB_CACHE_TTL = 300  # seconds — matches the trading cycle interval
_market_holiday_cache: dict[str, bool] = {}  # date_str → is_holiday (one Alpaca API call per day)

_US_MARKET_HOLIDAYS = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
    "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
}


def _load_today_universe() -> tuple[list[str], dict]:
    """Return (symbols, payload) for today's screened universe, or (config.SYMBOLS, {})."""
    if not os.path.exists(_UNIVERSE_PATH):
        return list(SYMBOLS), {}
    try:
        with open(_UNIVERSE_PATH) as f:
            payload = json.load(f)
        if payload.get("date") != date.today().isoformat():
            logger.info("Universe file is from a prior day — using config.SYMBOLS")
            return list(SYMBOLS), {}
        syms = payload.get("symbols", [])
        if not syms:
            return list(SYMBOLS), {}
        logger.info(f"Loaded screened universe: {len(syms)} symbols ({syms[:5]}...)")
        return syms, payload
    except Exception as exc:
        logger.warning(f"Failed to load screened universe: {exc} — using config.SYMBOLS")
        return list(SYMBOLS), {}


def _import_screener_picks(con, payload: dict) -> None:
    """Write pre-market screener factor scores from universe_today.json into screener_log.

    Called once per session (first cycle) — subsequent calls are no-ops because we
    check whether the screened_at timestamp is already present.  This is the only
    path for screener data to reach the bot's trades.db: the premarket runner's
    local DB is discarded; only universe_today.json crosses the job boundary via cache.
    """
    picks      = payload.get("picks")
    screened_at = payload.get("screened_at")
    if not picks or not screened_at:
        return
    try:
        existing = con.execute(
            "SELECT COUNT(*) FROM screener_log WHERE screened_at = ?", (screened_at,)
        ).fetchone()[0]
        if existing:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        con.execute("DELETE FROM screener_log WHERE screened_at < ?", (cutoff,))
        rows = [
            (screened_at, p["symbol"], p.get("rank"), p.get("composite_score"),
             p.get("analyst_signal", 0.0), p.get("etf_momentum"),
             p.get("regime"), p.get("sector"))
            for p in picks
        ]
        con.executemany(
            "INSERT INTO screener_log "
            "(screened_at,symbol,rank,composite_score,analyst_signal,etf_momentum,regime,sector) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()
        logger.info(f"Imported {len(rows)} screener picks into screener_log")
    except Exception as exc:
        logger.warning(f"screener_log import failed (non-fatal): {exc}")


def _log_buy_skip(symbol: str, reason: str) -> None:
    """Log a standardized reason why a candidate buy was skipped. The Trust
    Ledger (EntryDecisionRecorder.reject(), phase0_decisions.md #17/#18) is
    the audit trail for this now — decision_log is retired."""
    logger.info(f"BUY {symbol} skipped — {reason}")


def _is_market_hours(alpaca_api=None) -> bool:
    import zoneinfo
    et = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    if et.weekday() >= 5:
        return False
    today_str = et.strftime("%Y-%m-%d")
    # Cache the holiday result per day — only one Alpaca API call per session
    is_holiday = _market_holiday_cache.get(today_str)
    if is_holiday is None:
        if alpaca_api is not None:
            try:
                cal = alpaca_api.get_calendar(start=today_str, end=today_str)
                is_holiday = len(cal) == 0
            except Exception as e:
                logger.warning(f"Alpaca calendar check failed — using hardcoded holidays: {e}")
                is_holiday = today_str in _US_MARKET_HOLIDAYS
        else:
            is_holiday = today_str in _US_MARKET_HOLIDAYS
        _market_holiday_cache[today_str] = is_holiday
    if is_holiday:
        logger.info("NYSE holiday — skipping cycle.")
        return False
    base = et.replace(second=0, microsecond=0)
    tradeable_open  = base.replace(hour=9,  minute=30) + timedelta(minutes=MARKET_OPEN_BUFFER_MINS)
    tradeable_close = base.replace(hour=16, minute=0)  - timedelta(minutes=MARKET_CLOSE_BUFFER_MINS)
    in_window = tradeable_open <= et < tradeable_close
    if not in_window:
        logger.info(
            f"Outside tradeable window ({tradeable_open.strftime('%H:%M')}–"
            f"{tradeable_close.strftime('%H:%M')} ET) — skipping cycle."
        )
    return in_window


def _is_near_earnings(con, symbol: str) -> bool:
    if symbol in _ETF_SYMBOLS:
        return False
    now = time.time()
    row = con.execute(
        "SELECT near_earnings, cached_at FROM earnings_cache WHERE symbol=?", (symbol,)
    ).fetchone()
    if row:
        try:
            if now - datetime.fromisoformat(row[1]).timestamp() < _EARNINGS_DB_TTL:
                return bool(row[0])
        except (ValueError, TypeError):
            pass
    try:
        import yfinance as yf
        cal = yf.Ticker(symbol).calendar
        if cal is None:
            near = False
        else:
            dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else (
                cal.loc["Earnings Date"].tolist() if "Earnings Date" in cal.index else []
            )
            if not dates:
                near = False
            else:
                nearest = pd.to_datetime(dates[0]).date()
                near = abs((nearest - date.today()).days) <= EARNINGS_WINDOW_DAYS
                if near:
                    logger.info(f"Earnings guard: {symbol} — {nearest} within {EARNINGS_WINDOW_DAYS}d")
    except Exception as e:
        logger.warning(f"Earnings check failed for {symbol} — assuming safe: {e}")
        near = False
    con.execute(
        "INSERT OR REPLACE INTO earnings_cache (symbol, near_earnings, cached_at) VALUES (?,?,?)",
        (symbol, int(near), datetime.now(timezone.utc).isoformat())
    )
    con.commit()
    return near


def _prefetch_earnings_parallel(con, symbols: list[str]) -> dict[str, bool]:
    """Bulk-fetch earnings proximity: one SQL read, parallel yfinance for misses, one batch write.

    Replaces 25 sequential yfinance HTTP calls (1–5 s each on cache miss) with a
    single parallel burst capped at 8 threads.
    """
    now = time.time()
    placeholders = ",".join("?" * len(symbols))
    rows = con.execute(
        f"SELECT symbol, near_earnings, cached_at FROM earnings_cache WHERE symbol IN ({placeholders})",
        symbols,
    ).fetchall()

    result: dict[str, bool] = {}
    for sym, near, cached_at in rows:
        try:
            if now - datetime.fromisoformat(cached_at).timestamp() < _EARNINGS_DB_TTL:
                result[sym] = bool(near)
        except (ValueError, TypeError):
            pass

    for sym in symbols:
        if sym in _ETF_SYMBOLS:
            result[sym] = False

    stale = [s for s in symbols if s not in result and s not in _ETF_SYMBOLS]
    if not stale:
        return {s: result.get(s, False) for s in symbols}

    def _fetch_one(symbol: str) -> tuple[str, bool]:
        try:
            import yfinance as yf
            cal = yf.Ticker(symbol).calendar
            if cal is None:
                return symbol, False
            dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else (
                cal.loc["Earnings Date"].tolist() if "Earnings Date" in cal.index else []
            )
            if not dates:
                return symbol, False
            nearest = pd.to_datetime(dates[0]).date()
            near = abs((nearest - date.today()).days) <= EARNINGS_WINDOW_DAYS
            if near:
                logger.info(f"Earnings guard: {symbol} — {nearest} within {EARNINGS_WINDOW_DAYS}d")
            return symbol, near
        except Exception as e:
            logger.warning(f"Earnings prefetch failed for {symbol}: {e}")
            return symbol, False

    logger.info(f"Earnings prefetch: {len(stale)} cache misses — fetching in parallel")
    with ThreadPoolExecutor(max_workers=min(len(stale), 8)) as pool:
        fresh = dict(pool.map(_fetch_one, stale))

    ts = datetime.now(timezone.utc).isoformat()
    con.executemany(
        "INSERT OR REPLACE INTO earnings_cache (symbol, near_earnings, cached_at) VALUES (?,?,?)",
        [(sym, int(near), ts) for sym, near in fresh.items()],
    )
    con.commit()
    result.update(fresh)
    return {s: result.get(s, False) for s in symbols}


def _wsb(symbol: str) -> tuple[str, dict]:
    """Fetch WSB sentiment with a 5-min module-level cache to avoid Reddit rate limits."""
    now = time.time()
    cached_ts, cached_result = _wsb_cache.get(symbol, (0.0, None))
    if cached_result is not None and now - cached_ts < _WSB_CACHE_TTL:
        return symbol, cached_result
    try:
        result = get_wsb_sentiment(symbol)
    except Exception as exc:
        logger.debug(f"wsb_sentiment_fetch {symbol}: {exc}")
        result = {"mentions": 0, "sentiment": 0.0}
    _wsb_cache[symbol] = (now, result)
    return symbol, result


def _load_premarket_sentiment() -> dict[str, float]:
    """Load pre-computed FinBERT scores from today's prefetch run, if available."""
    path = "data/sentiment_today.json"
    try:
        if os.path.exists(path):
            with open(path) as f:
                payload = json.load(f)
            if payload.get("date") == date.today().isoformat():
                scores = payload.get("scores", {})
                if scores:
                    logger.info(f"Loaded pre-market sentiment: {len(scores)} symbols")
                    return scores
    except Exception as e:
        logger.warning(f"Failed to load pre-market sentiment: {e}")
    return {}


def _compute_sentiments(
    active_symbols: list[str], premarket_sentiment: dict | None,
) -> dict[str, float]:
    """Blend FinBERT pre-market scores with WSB real-time scores per symbol."""
    import math
    from concurrent.futures import ThreadPoolExecutor
    if premarket_sentiment:
        finbert = premarket_sentiment
        logger.info("Using pre-market FinBERT sentiment — skipping in-cycle BERT pass")
    else:
        finbert = {sym: 0.0 for sym in active_symbols}
    with ThreadPoolExecutor(max_workers=6) as pool:
        wsb_map = dict(pool.map(_wsb, active_symbols))
    sentiments: dict[str, float] = {}
    for sym in active_symbols:
        wsb   = wsb_map[sym]
        score = finbert.get(sym, 0.0)
        if wsb["mentions"] > 0:
            w = min(0.50, math.log1p(wsb["mentions"]) / 10)
            sentiments[sym] = score * (1 - w) + wsb["sentiment"] * w
        else:
            sentiments[sym] = score
    return sentiments


def _log_cycle_summary(con) -> None:
    """Log DB row counts and latest portfolio value at end of every cycle."""
    import sqlite3
    from datetime import date
    try:
        n_trades = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        n_today  = con.execute(
            "SELECT COUNT(*) FROM trades WHERE timestamp LIKE ?",
            (date.today().isoformat() + "%",),
        ).fetchone()[0]
        n_pos  = con.execute("SELECT COUNT(*) FROM position_state").fetchone()[0]
        last   = con.execute(
            "SELECT portfolio_value FROM trades ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        last_pv = f"${last[0]:,.2f}" if last else "NONE"
        logger.info(
            f"DB summary — trades total={n_trades} (today={n_today}), "
            f"open_positions={n_pos}, latest portfolio_value={last_pv}"
        )
        if n_trades == 0:
            logger.warning(
                "trades table is EMPTY — dashboard will show $0.00 because portfolio value is "
                "derived from the latest trade row. No trade has executed yet (gates blocking, "
                "no buy signal, or first run). This is expected until the first fill."
            )
    except Exception as _e:
        logger.warning(f"End-of-cycle DB summary failed: {_e}")


def _maybe_push_db(last_sync: float, interval: float) -> float:
    """Push trades.db and data/trust_ledger.db to HuggingFace if interval has
    elapsed. Returns updated timestamp. Both sync on the same interval since
    a GitHub Actions runner is ephemeral either way -- whatever isn't pushed
    before the job ends is gone, ledger included."""
    import time
    try:
        from bot.monitor.sync_db import push_db, push_ledger_db
        now = time.time()
        if now - last_sync > interval:
            trades_ok = push_db()
            if not trades_ok:
                logger.warning("trades.db sync to HuggingFace FAILED — dashboard will show stale data")
            ledger_ok = push_ledger_db()
            if not ledger_ok:
                logger.warning("trust_ledger.db sync to HuggingFace FAILED — ledger data since last "
                                "successful push will be lost when this runner is torn down")
            if trades_ok or ledger_ok:
                return now
        else:
            logger.debug(f"HF sync skipped — last push {time.time() - last_sync:.0f}s ago")
    except Exception as _e:
        logger.warning(f"HF DB sync skipped: {_e}")
    return last_sync


def _fetch_symbol(symbol: str, client: AlpacaClient, yf_batch: dict) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    """Return (symbol, bars_5m, bars_daily).

    bars_5m  — intraday 5-min bars; empty when not enough today yet (< 60 bars) or
               stale (feed broken).  Used for current price only.
    bars_daily — 1-year daily OHLCV from yfinance; used for XGB/LSTM/regime (matches training).
    Both empty → skip this symbol entirely (feed is stale/broken).
    """
    feed_stale = False
    bars_5m    = pd.DataFrame()

    try:
        raw = client.get_bars(symbol, timeframe="5Min", limit=10)
        if not raw.empty:
            last_ts  = raw.index[-1]
            now_utc  = pd.Timestamp.now(tz="UTC")
            last_utc = (last_ts.tz_localize("UTC")
                        if last_ts.tzinfo is None else last_ts.tz_convert("UTC"))
            age_mins = (now_utc - last_utc).total_seconds() / 60
            if age_mins > 30:
                logger.warning(
                    f"Stale bars for {symbol}: last bar is {age_mins:.0f}m old — skipping"
                )
                feed_stale = True
            else:
                bars_5m = raw
    except ValueError:
        # Not enough intraday bars yet (normal early-day condition with IEX free tier)
        pass
    except Exception as e:
        logger.warning(f"5min bar fetch failed for {symbol}: {e}")
        feed_stale = True

    if feed_stale:
        return symbol, pd.DataFrame(), pd.DataFrame()

    # Daily bars from pre-fetched batch (thread-safe; computed before thread pool)
    bars_daily = pd.DataFrame()
    raw_d = yf_batch.get(symbol)
    if raw_d is not None and not raw_d.empty:
        try:
            spy_raw   = yf_batch.get("SPY")
            spy_close = spy_raw["close"] if (spy_raw is not None and not spy_raw.empty) else None
            bars_daily = compute_features(raw_d, spy_close=spy_close)
        except Exception as e:
            logger.warning(f"Daily bar features failed for {symbol}: {e}")

    return symbol, bars_5m, bars_daily


def prefetch_bars(active_symbols: list[str], client: AlpacaClient) -> dict[str, BarData]:
    """Batch-fetch daily bars (yfinance) + 5-min bars (Alpaca) for all symbols.
    Returns bars_map: {symbol: (bars_5m_df, bars_daily_df)}. yfinance download
    is one batched call to avoid rate limits; 5-min bars fetch in parallel."""
    import bot.monitor.telegram_bot as _tg
    _yf_batch: dict[str, pd.DataFrame] = {}
    try:
        _batch_syms = list(active_symbols)
        if "SPY" not in _batch_syms:
            _batch_syms.append("SPY")
        _raw = yf.download(_batch_syms, period="2y", interval="1d",
                           progress=False, auto_adjust=True, group_by="ticker")
        for _sym in _batch_syms:
            try:
                _df = _raw[_sym].copy()
                _df.columns = [c.lower() for c in _df.columns]
                _df = _df[["open", "high", "low", "close", "volume"]].dropna()
                if not _df.empty:
                    _yf_batch[_sym] = _df
            except Exception as _e:
                logger.debug(f"yfinance batch skip {_sym}: {_e}")
        loaded, total = len(_yf_batch), len(_batch_syms)
        logger.info(f"yfinance batch: {loaded}/{total} symbols loaded")
        if "SPY" not in _yf_batch:
            logger.warning("SPY missing from yfinance batch — relative strength gate disabled")
            _tg.send("⚠️ <b>SPY data missing</b> — relative strength gate disabled.")
        if loaded < total * 0.5:
            _tg.send(
                f"⚠️ <b>yfinance data degraded</b> — only {loaded}/{total} symbols loaded.\n"
                "Yahoo Finance may have changed their API format. "
                "XGB/LSTM signals falling back to 5-min bars (out-of-distribution).\n"
                "Check: <code>pip install --upgrade yfinance</code>"
            )
    except Exception as _e:
        logger.warning(f"yfinance batch prefetch failed: {_e}")
        _tg.send(
            f"⚠️ <b>yfinance batch fetch failed</b> — {_e}\n"
            "Daily bars unavailable this cycle. Check if Yahoo Finance format changed."
        )

    with ThreadPoolExecutor(max_workers=min(len(active_symbols), 8)) as pool:
        futures = [pool.submit(_fetch_symbol, sym, client, _yf_batch) for sym in active_symbols]
        fetched = [f.result() for f in futures]

    bars_map = {sym: BarData(bars_5m=b5, bars_daily=bd) for sym, b5, bd in fetched}
    _n_5m = sum(1 for _, b5, _ in fetched if not b5.empty)
    if _n_5m < len(active_symbols) * 0.5:
        _tg.send(
            f"⚠️ <b>Alpaca feed degraded</b> — only {_n_5m}/{len(active_symbols)} symbols "
            "have live 5-min bars. Most symbols will be skipped this cycle."
        )
    return bars_map
