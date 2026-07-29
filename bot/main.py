"""Main trading loop — runs every 5 minutes via GitHub Actions."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
import traceback
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, datetime, timedelta, timezone
import pandas as pd
from loguru import logger
from bot.core.error_logger import log_exception

from config import (
    SYMBOLS, TRADE_DB_PATH,
    MARKET_OPEN_BUFFER_MINS, MARKET_CLOSE_BUFFER_MINS,
    EARNINGS_WINDOW_DAYS,
    MAX_HOLD_DAYS, KELLY_LOOKBACK_TRADES, KELLY_FRACTION_MAX,
    CORRELATION_THRESHOLD, ENTRY_REGIMES, MIN_VOLUME_RATIO,
    PDT_MAX_DAY_TRADES, PDT_WINDOW_DAYS, PAPER_SIM_CAPITAL,
    MAX_RISK_PER_TRADE_PCT,
    ATR_STOP_MULTIPLIER, ATR_MIN_STOP_PCT, ATR_MAX_STOP_PCT, STOP_LOSS_PCT,
    MIN_RR_RATIO, MIN_TP_PCT,
    MAX_SECTOR_EXPOSURE_PCT, MAX_POSITION_DRIFT_PCT, MIN_CASH_RESERVE_PCT,
    MAX_POSITION_PCT, SECTOR_MAP,
)
from bot.execution.base import Executor
from bot.execution.factory import get_executor
from bot.strategy.features import compute_features, FEATURE_COLS
from bot.strategy.regime_classifier import RegimeClassifier
from bot.strategy.xgb_predictor import XGBPredictor
from bot.strategy.lstm_predictor import LSTMPredictor
from bot.strategy.sentiment import batch_sentiment_scores
from bot.strategy.macro import _get_cached as _get_macro_cached
from bot.strategy.reddit_sentiment import get_wsb_sentiment
from bot.strategy.ensemble import ensemble_signal, action_to_int, BUY_FRACTION, ensemble_confidence
from bot.strategy.signal_gate import check_signal_gate
from bot.risk.risk_manager import RiskManager, _business_days_between, kelly_fraction as _kelly_fraction
import bot.monitor.telegram_bot as tg

# Sub-module imports (helpers extracted to keep this file under 500 lines)
from bot._main_signals import record_signal, update_signal_outcomes
from bot._main_db import (
    RiskSnapshot,
    _anchor_daily_start, _enable_wal_mode,
    _load_risk_state, _log_recommendation, _log_signal, _record_snapshot,
    _save_risk_state, _week_key, log_trade,
    init_db as _init_db_core,
)


def init_db() -> sqlite3.Connection:
    """Wrapper so monkeypatching bot.main.TRADE_DB_PATH in tests still works."""
    return _init_db_core(TRADE_DB_PATH)


def _apply_sim_capital(portfolio_value: float, available_cash: float) -> tuple[float, float, bool]:
    """Cap equity to PAPER_SIM_CAPITAL for small-account dry-run mechanics."""
    if PAPER_SIM_CAPITAL and PAPER_SIM_CAPITAL > 0:
        return (min(portfolio_value, PAPER_SIM_CAPITAL),
                min(available_cash, PAPER_SIM_CAPITAL),
                True)
    return portfolio_value, available_cash, False
from bot._main_positions import (
    BarData, PositionState,
    _check_time_exit, _delete_position_state, _is_wash_sale_risk,
    _load_position_state, _maybe_record_day_trade,
    _opened_today, _passes_correlation_gate, _reconcile_positions,
    _signal_sell, _trim_position, _upsert_position_state,
)
from bot._main_reconcile import _fetch_positions_for_reconcile
from bot._main_market import (
    _import_screener_picks, _is_market_hours, _is_near_earnings,
    _load_today_universe, _log_buy_skip, _wsb,
    _log_cycle_summary, _maybe_push_db,
)
from bot._main_cycle import (
    EntryContext,
    _handle_exits, _handle_entry,
)
from bot._main_prep import prepare_cycle_context
from bot.capital.pool import load_active_pool as _load_pool, compute_tradeable_capital
from bot._main_runner import (
    _do_clean_db, _do_reset_daily_start, end_of_day_summary, run_loop,
)
from bot.trust_ledger.connection import get_ledger_conn
from bot.trust_ledger.candidates import get_todays_candidate_event_id
from ledger.integrity import get_active_pointer
from bot._main_candidates import record_candidate_safe
from bot._main_trust_decisions import ExitLedgerContext, record_data_quality_safe, record_risk_evaluation_safe

os.makedirs("logs", exist_ok=True)
if not os.getenv("_BOT_LOG_HANDLER_ADDED"):
    logger.add("logs/trading.log", rotation="1 week", retention="4 weeks", level="INFO")
    os.environ["_BOT_LOG_HANDLER_ADDED"] = "1"

_HALT_FILE        = "data/HALT_TRADING"
_last_hf_sync: float = 0.0
_HF_SYNC_INTERVAL: float = 900
_stop_fired_today: set[str] = set()
_stop_fired_date: str = ""
_sym_errors: dict[str, int] = {}
_SYM_ERROR_SKIP_THRESHOLD = 5   # skip a symbol after this many consecutive failures


def run(
    mode: str = "paper",
    _regime_clf: RegimeClassifier | None = None,
    _xgb: XGBPredictor | None = None,
    _lstm: LSTMPredictor | None = None,
    _client: Executor | None = None,
) -> None:
    logger.info(f"=== Trading cycle start | mode={mode} ===")

    # Emergency override: create data/HALT_TRADING file to pause without canceling the workflow.
    if os.path.exists(_HALT_FILE):
        logger.warning("HALT_TRADING file detected — cycle skipped. Remove file to resume.")
        tg._send("⛔ <b>EMERGENCY HALT ACTIVE</b> — bot paused. Delete data/HALT_TRADING to resume.")
        return

    global _last_hf_sync, _stop_fired_today, _stop_fired_date
    today_str = date.today().isoformat()
    if _stop_fired_date != today_str:
        _stop_fired_today = set()
        _stop_fired_date = today_str
    client = _client if _client is not None else get_executor()
    if not _is_market_hours(client.api):
        logger.info("Market is closed — cycle skipped (no trades, no DB write). "
                    "Dashboard will keep showing the last synced values.")
        return

    con = init_db()
    trust_conn = get_ledger_conn()
    # Fetched once per cycle, not per symbol -- the active manifest changes
    # only on a deliberate promotion, never mid-cycle.
    _active_manifest_id = get_active_pointer(trust_conn)

    active_symbols, _universe_payload = _load_today_universe()
    _import_screener_picks(con, _universe_payload)

    rs: RiskSnapshot = _load_risk_state(con)
    daily_start = rs.daily_start  # captured before the anchor-fill below -- None here means
                                   # this is the first cycle of the day (used further down)

    # Anchor daily_start to the account's value at yesterday's close (not current
    # live price), so Day P&L means "today's gain" rather than gain-since-inception.
    if rs.daily_start is None:
        rs.daily_start, _src = _anchor_daily_start(con)
        if rs.daily_start is not None:
            logger.info(f"Daily start anchored to {_src}: ${rs.daily_start:.2f}")

    risk = RiskManager(
        daily_start_value=rs.daily_start,
        day_trade_dates=rs.day_trade_dates,
        weekly_start_value=rs.weekly_start,
        daily_warning_sent=rs.daily_warning_sent,
        weekly_halt_alerted=rs.weekly_halt_alerted,
        portfolio_high=rs.portfolio_high,
    )

    regime_clf = _regime_clf if _regime_clf is not None else RegimeClassifier()
    xgb        = _xgb        if _xgb        is not None else XGBPredictor()
    lstm       = _lstm       if _lstm       is not None else LSTMPredictor()

    if lstm.is_degraded:
        _tg_key = f"lstm_degraded_{today_str}"
        if not os.path.exists(f"data/.{_tg_key}"):
            tg._send(
                f"⚠️ <b>LSTM model degraded</b> — val_loss={lstm.val_loss:.4f} (near-random).\n"
                f"LSTM weight transferred to XGB for today's cycle.\n"
                f"Run <code>python scripts/train_model.py</code> or trigger the weekly retrain workflow."
            )
            Path(f"data/.{_tg_key}").touch()

    # Single get_account() call — serves both portfolio-value check and compliance block below.
    try:
        acct = client.get_account()
    except Exception as _ae:
        logger.error(f"Alpaca get_account() failed — aborting cycle: {_ae}")
        tg._send("🚨 Alpaca get_account() failed — check API credentials. Bot cycle aborted.")
        con.close()
        trust_conn.close()
        return
    real_portfolio_value = float(acct.portfolio_value)
    real_available_cash  = float(acct.cash)
    if real_portfolio_value <= 0:
        logger.error(
            f"Alpaca returned portfolio_value=${real_portfolio_value:.2f} — likely an auth/connection "
            "failure (check ALPACA_KEY/ALPACA_SECRET). Dashboard would show $0.00. Aborting cycle."
        )
        tg._send("🚨 Alpaca account value is $0.00 — check API credentials. Bot cycle aborted.")
        con.close()
        trust_conn.close()
        return

    # Sanity check: reject any reading that is less than half the last known value.
    # Prevents a transient API error or wrong-account connection from triggering a
    # mass SELL_RECONCILE that phantom-closes all held positions in the DB.
    _last_snap = con.execute(
        "SELECT portfolio_value FROM portfolio_snapshots "
        "WHERE portfolio_value > 0 ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    # _sanity_blocked=True: block reconcile (prevents phantom SELL_RECONCILE storm) and
    # new entries (can't size positions without correct account value), but exit management
    # still runs every cycle so stop-losses and gap-down floors are never suppressed.
    _sanity_blocked = _last_snap and real_portfolio_value < _last_snap[0] * 0.50
    if _sanity_blocked:
        logger.error(
            f"Portfolio value sanity check FAILED: Alpaca reports ${real_portfolio_value:,.2f} "
            f"but last snapshot was ${_last_snap[0]:,.2f} — drop >50%. "
            "Likely wrong account or transient API error. Blocking reconcile and new entries."
        )
        tg._send(
            f"🚨 Portfolio value sanity check failed — Alpaca reports ${real_portfolio_value:,.0f} "
            f"vs last known ${_last_snap[0]:,.0f}. Reconcile + buys blocked. Check API key / account."
        )

    logger.info(f"Alpaca connection OK — account value ${real_portfolio_value:,.2f}")
    # Paper sim-capital: size/risk-check as if the account were small (dry-run).
    # We keep the real values separately so the dashboard always shows the true account equity.
    portfolio_value, available_cash, _sim_capital = _apply_sim_capital(real_portfolio_value, real_available_cash)
    if _sim_capital:
        logger.warning(
            f"PAPER_SIM_CAPITAL active — sizing & risk as if account = "
            f"${portfolio_value:,.2f} (real account ${real_portfolio_value:,.2f})"
        )
    risk.update_portfolio_high(portfolio_value)

    # Brokerage compliance: validate account standing before placing any orders
    try:
        # ① Account status gate — Alpaca can suspend accounts for policy violations
        acct_status     = getattr(acct, "status",          "ACTIVE")
        trading_blocked = getattr(acct, "trading_blocked", False)
        account_blocked = getattr(acct, "account_blocked", False)
        if acct_status != "ACTIVE" or trading_blocked or account_blocked:
            status_msg = (f"status={acct_status}, trading_blocked={trading_blocked}, "
                          f"account_blocked={account_blocked}")
            logger.error(f"Account not tradeable ({status_msg}) — aborting cycle")
            record_data_quality_safe(trust_conn, "alpaca_account", "DOWN", status_msg)
            tg._send(f"🚨 Account not tradeable ({status_msg}) — bot halted. Check Alpaca dashboard.")
            con.close()
            trust_conn.close()
            return
        # ② PDT flag and equity check
        if getattr(acct, "pattern_day_trader", False):
            logger.warning("Alpaca account is flagged as Pattern Day Trader — PDT limits apply.")
        pdt_equity = float(getattr(acct, "equity", 0) or 0)
        # Under sim-capital, use the simulated equity so the PDT limit (under $25k)
        # actually applies — that's a key small-account behaviour to dry-run.
        if _sim_capital:
            pdt_equity = min(pdt_equity, PAPER_SIM_CAPITAL)
        pdt_exempt = pdt_equity >= 25_000
        if pdt_exempt:
            logger.info(f"Account equity ${pdt_equity:,.2f} ≥ $25,000 — PDT day-trade limits waived.")
        logger.info(f"Account standing verified — status=ACTIVE, equity=${pdt_equity:,.2f}")
    except Exception as e:
        logger.warning(f"Account compliance check failed: {e}")
        record_data_quality_safe(trust_conn, "alpaca_account", "DEGRADED", f"compliance check raised: {e}")
        pdt_exempt = False

    positions       = _fetch_positions_for_reconcile(client, con, trust_conn)
    if not _sanity_blocked:
        _reconcile_positions(con, positions, portfolio_value=portfolio_value, client=client)

    (buy_order_syms, sell_order_syms, macro_score, macro_cap, macro_halt,
     bars_map, sentiments, spy_5bar_return, vs_spy_today, earnings_map,
     news_data_timestamp) = prepare_cycle_context(
        con, client, risk, mode, daily_start, real_portfolio_value,
        real_available_cash, portfolio_value, positions, active_symbols,
    )

    # Compute once per cycle — avoids N identical DB reads inside _handle_entry.
    _tradeable_capital = compute_tradeable_capital(con, portfolio_value)
    # Track remaining profits pool across symbols so aggregate buys can't exceed it.
    _remaining_tradeable = _tradeable_capital
    _capital_pool = _load_pool(con, initial_amount=_tradeable_capital)

    _cycle_deployed_notional = 0.0

    # ── Per-symbol decision loop ──────────────────────────────────────────────
    for symbol in active_symbols:
        if _sym_errors.get(symbol, 0) >= _SYM_ERROR_SKIP_THRESHOLD:
            logger.warning(
                f"{symbol}: skipping — {_sym_errors[symbol]} consecutive failures "
                "(possible feed or API bug; reset by restarting the bot)"
            )
            continue
        try:
            bars_5m, bars_daily = bars_map.get(symbol, (pd.DataFrame(), pd.DataFrame()))
            # Use daily bars for XGB/LSTM/regime (matches training data; never < 60 rows).
            # Fall back to 5-min only when daily fetch fails.
            sig_bars = bars_daily if not bars_daily.empty else bars_5m
            if sig_bars.empty:
                # No persisted record of this previously (silent continue) --
                # now counted the same as a processing failure so a symbol
                # with no data for 5 straight cycles gets a candidate_evaluation_event
                # (evaluation_completed=False) instead of vanishing with no audit trail.
                _sym_errors[symbol] = _sym_errors.get(symbol, 0) + 1
                if _sym_errors[symbol] >= _SYM_ERROR_SKIP_THRESHOLD:
                    record_candidate_safe(
                        trust_conn, symbol, today_str, _universe_payload,
                        data_available=False, required_models_available=False,
                        evaluation_completed=False,
                    )
                continue

            latest = sig_bars.iloc[-1]
            # Prefer the freshest intraday close for price-sensitive calcs (limit orders, ATR stops).
            # Fall back to daily close when 5-min bars are not yet available (early morning).
            current_price = float(
                bars_5m.iloc[-1]["close"] if not bars_5m.empty else latest["close"]
            )
            current_atr   = float(latest.get("atr", 0) or 0)
            volume_ratio  = float(latest.get("volume_ratio", 1.0) or 1.0)
            regime_code   = regime_clf.predict(latest)
            regime_name   = regime_clf.regime_name(regime_code)

            xgb_prob          = xgb.predict_proba(latest)
            lstm_prob         = lstm.predict_proba(sig_bars)
            sentiment         = sentiments.get(symbol, 0.0)
            action_str, ensemble_size = ensemble_signal(
                xgb_prob, lstm_prob, sentiment, regime_name, macro_score=macro_score
            )
            action = action_to_int(action_str)

            # Decision Intelligence Phase 1A — candidate_evaluation_events, written
            # once per (symbol, trading day) per phase1a_requirements.md Section 4.1.
            _models_ok = xgb.model is not None and lstm.model is not None and not lstm.is_degraded
            record_candidate_safe(trust_conn, symbol, today_str, _universe_payload,
                                  data_available=True, required_models_available=_models_ok,
                                  evaluation_completed=True)

            # Log every evaluated signal so the dashboard can show live model
            # output even on cycles where no trade fires.
            _log_signal(con, symbol, xgb_prob, lstm_prob, sentiment,
                        macro_score, regime_name, action_str)

            # Record per-symbol recommendation for every cycle so Rec History widget
            # shows what the bot was thinking even when no trade fires.
            try:
                from database.services.analytics_service import analytics_service as _as
                _ens_conf = ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)
                _as.save_recommendation(symbol, action_str, float(_ens_conf),
                                        price=current_price)
                _log_recommendation(con, symbol, action_str, float(_ens_conf),
                                    price=current_price)
            except Exception as _re:
                logger.debug(f"save_recommendation({symbol}): {_re}")

            # ── High-confidence signal gate (user-facing signals) ─────────────
            # Fires independently of the bot's position/cash gates so users get
            # the signal even when the bot itself can't trade (e.g. no cash).
            if action == 1 and not macro_halt and regime_name in ENTRY_REGIMES:
                _sg_passed, _sg_meta = check_signal_gate(
                    symbol, xgb_prob, lstm_prob, macro_score,
                    bars_daily, volume_ratio, vs_spy_today,
                )
                if _sg_passed:
                    _ens_score = ensemble_confidence(xgb_prob, lstm_prob, sentiment, macro_score)
                    record_signal(
                        con, symbol, _sg_meta,
                        xgb_prob, lstm_prob, _ens_score, macro_score,
                    )

            _exit_ledger_ctx = ExitLedgerContext(
                trust_conn=trust_conn,
                candidate_event_id=get_todays_candidate_event_id(trust_conn, symbol, today_str),
                deployment_manifest_id=_active_manifest_id,
                xgb_prob=xgb_prob, lstm_prob=lstm_prob, sentiment=sentiment, macro_score=macro_score,
                risk=risk, news_data_timestamp=news_data_timestamp,
            )
            if _handle_exits(con, client, risk, symbol, positions, sell_order_syms,
                             current_price, current_atr, regime_name, portfolio_value,
                             action, pdt_exempt, _stop_fired_today, pool=_capital_pool,
                             ledger_ctx=_exit_ledger_ctx):
                continue

            # ── Entry gates (applied in order of cheapness) ───────────────────
            if action != 1 or _sanity_blocked:
                continue

            _cash_before = available_cash
            available_cash = _handle_entry(
                con, client, risk, symbol,
                EntryContext(
                    positions=positions, buy_order_syms=buy_order_syms,
                    earnings_map=earnings_map, bars_map=bars_map,
                    sig_bars=sig_bars, latest=latest,
                    current_price=current_price, current_atr=current_atr,
                    regime_name=regime_name, portfolio_value=portfolio_value,
                    available_cash=available_cash,
                    xgb_prob=xgb_prob, lstm_prob=lstm_prob,
                    macro_score=macro_score, macro_cap=macro_cap,
                    macro_halt=macro_halt, spy_5bar_return=spy_5bar_return,
                    vs_spy_today=vs_spy_today, sentiments=sentiments,
                    ensemble_size=ensemble_size, xgb=xgb,
                    stop_fired_today=_stop_fired_today, volume_ratio=volume_ratio,
                    tradeable_capital=_remaining_tradeable, pool=_capital_pool,
                    lstm=lstm, trust_conn=trust_conn,
                    candidate_event_id=get_todays_candidate_event_id(trust_conn, symbol, today_str),
                    deployment_manifest_id=_active_manifest_id,
                    news_data_timestamp=news_data_timestamp,
                ),
            )
            _deployed = _cash_before - available_cash
            if _deployed > 0.0:
                _remaining_tradeable = max(0.0, _remaining_tradeable - _deployed)
                _cycle_deployed_notional += _deployed

            _sym_errors.pop(symbol, None)   # reset failure streak on success

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            _sym_errors[symbol] = _sym_errors.get(symbol, 0) + 1
            if _sym_errors[symbol] >= 3:
                logger.warning(
                    f"{symbol} has failed {_sym_errors[symbol]} consecutive cycles "
                    f"— possible feed or feature bug"
                )
            if _sym_errors[symbol] >= _SYM_ERROR_SKIP_THRESHOLD:
                record_candidate_safe(
                    trust_conn, symbol, today_str, _universe_payload,
                    data_available=False, required_models_available=False,
                    evaluation_completed=False,
                )

    con.commit()  # flush all batched signal_log inserts in one fsync (was 25 individual commits)

    # Resolve pending signals against latest prices (target/stop hit checks)
    try:
        _live_prices = {sym: float(bars_map[sym].bars_5m.iloc[-1]["close"])
                        for sym in active_symbols
                        if sym in bars_map and not bars_map[sym].bars_5m.empty}
        update_signal_outcomes(con, _live_prices)
    except Exception as _se:
        logger.debug(f"update_signal_outcomes: {_se}")

    _sizing_base = _capital_pool.tradeable_cash if _capital_pool else portfolio_value
    record_risk_evaluation_safe(con, trust_conn, risk, portfolio_value, _sizing_base, _cycle_deployed_notional)

    _log_cycle_summary(con)
    logger.info("=== Trading cycle complete ===")
    con.close()
    trust_conn.close()
    _last_hf_sync = _maybe_push_db(_last_hf_sync, _HF_SYNC_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",    default="paper", choices=["paper", "live"])
    parser.add_argument("--summary", action="store_true",
                        help="Send end-of-day Telegram summary and exit")
    parser.add_argument("--loop",    action="store_true",
                        help="Long-running mode: load models once, loop until market close")
    parser.add_argument("--reset-daily-start", action="store_true",
                        help="Clear stale daily_start anchor so Day P&L resets on next cycle")
    parser.add_argument("--clean-db", action="store_true",
                        help="Wipe all bot data for a clean start (reset Alpaca paper account first)")
    args = parser.parse_args()
    try:
        if args.clean_db:
            _do_clean_db()
        elif args.reset_daily_start:
            _do_reset_daily_start()
        elif args.summary:
            end_of_day_summary()
        elif args.loop:
            run_loop(mode=args.mode)
        else:
            run(mode=args.mode)
    except Exception:
        tb = traceback.format_exc()
        logger.error("Bot crashed:\n" + tb)
        sys.stdout.write(f"::error title=Trading Bot Crash::{tb.splitlines()[-1]} — see step log\n")
        sys.stdout.flush()
        sys.exit(1)
