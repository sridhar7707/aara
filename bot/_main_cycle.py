"""Per-symbol cycle logic extracted from bot/main.py: fetch, exits, and entries."""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from loguru import logger

import bot.monitor.telegram_bot as tg
from bot.execution.alpaca_client import AlpacaClient
from bot.risk.risk_manager import RiskManager, kelly_fraction as _kelly_fraction
from bot.strategy.ensemble import BUY_FRACTION, ensemble_confidence
from config import (
    ATR_MAX_STOP_PCT, ATR_MIN_STOP_PCT, ATR_STOP_MULTIPLIER,
    CASH_USE_FRACTION,
    ENTRY_REGIMES, KELLY_FRACTION_MAX,
    MAX_POSITION_DRIFT_PCT, MAX_POSITION_PCT,
    MAX_RISK_PER_TRADE_PCT, MAX_SECTOR_EXPOSURE_PCT,
    MIN_CASH_RESERVE_PCT, MIN_RR_RATIO, MIN_TP_PCT,
    MACD_CONFIRMATION_MIN, MIN_VOLUME_RATIO, XGB_MIN_CONFIDENCE,
    RS_LOOKBACK_BARS, SECTOR_MAP, STOP_LOSS_PCT,
)
from bot._main_db import log_trade, _save_risk_state
from database.trade_journal import open_entry as _journal_open
from bot.capital.pool import CapitalPool, update_on_buy as _pool_buy
from bot.decision.daily_actions import record as _rec_action
from bot._main_market import _log_buy_skip
from bot._main_positions import (
    BarData,
    _TP_FLOOR, _atr_tp_pct,
    _handle_exits, _is_wash_sale_risk,
    _passes_correlation_gate,
    _upsert_position_state,
)
from bot._main_trust_decisions import EntryDecisionRecorder


@dataclass
class EntryContext:
    """All per-symbol signal and market data needed by _handle_entry."""
    positions: dict
    buy_order_syms: set
    earnings_map: dict
    bars_map: dict
    sig_bars: pd.DataFrame
    latest: Any
    current_price: float
    current_atr: float
    regime_name: str
    portfolio_value: float
    available_cash: float
    xgb_prob: float
    lstm_prob: float
    macro_score: float
    macro_cap: float
    macro_halt: bool
    spy_5bar_return: float | None
    vs_spy_today: float
    sentiments: dict
    ensemble_size: float
    xgb: Any
    stop_fired_today: set
    volume_ratio: float
    tradeable_capital: float
    pool: CapitalPool | None = None
    lstm: Any = None
    trust_conn: Any = None
    candidate_event_id: str | None = None
    deployment_manifest_id: str | None = None


def _handle_entry(
    con: sqlite3.Connection, client: AlpacaClient, risk: RiskManager,
    symbol: str, ctx: EntryContext,
) -> float:
    """Process entry gates and buy execution. Returns updated available_cash."""
    available_cash = ctx.available_cash  # mutable local; all other fields accessed via ctx

    _price_ts = getattr(ctx.latest, "name", None)
    _price_ts_iso = _price_ts.isoformat() if hasattr(_price_ts, "isoformat") else None
    recorder = EntryDecisionRecorder(
        ctx.trust_conn, ctx.candidate_event_id, ctx.deployment_manifest_id, symbol,
        ctx.xgb_prob, ctx.lstm_prob, ctx.sentiments.get(symbol, 0.0), ctx.macro_score,
        ctx.regime_name, ctx.portfolio_value, ctx.available_cash, _price_ts_iso,
        lstm_is_degraded=getattr(ctx.lstm, "is_degraded", False),
        lstm_val_loss=getattr(ctx.lstm, "val_loss", None),
    )

    # Gate 0 — VIX emergency halt: no new positions when VIX >= 40
    if ctx.macro_halt:
        _log_buy_skip(symbol, "VIX emergency halt")
        recorder.reject("vix_halt", "VIX emergency halt")
        return available_cash

    # Gate 1 — Regime: only buy in trending or ranging markets
    if ctx.regime_name not in ENTRY_REGIMES:
        _detail = f"regime={ctx.regime_name} (allowed: {ENTRY_REGIMES})"
        _log_buy_skip(symbol, _detail)
        recorder.reject("regime", _detail)
        return available_cash

    # Gate 2 — Volume: confirm institutional participation
    if ctx.volume_ratio < MIN_VOLUME_RATIO:
        _detail = f"volume ratio {ctx.volume_ratio:.2f} < {MIN_VOLUME_RATIO}"
        _log_buy_skip(symbol, _detail)
        recorder.reject("volume", _detail)
        return available_cash

    # Gate 3 — XGB minimum confidence: live trades show 62% WR at >=0.55 vs 25% below
    if ctx.xgb_prob < XGB_MIN_CONFIDENCE:
        _detail = f"xgb_prob {ctx.xgb_prob:.3f} < min {XGB_MIN_CONFIDENCE:.2f}"
        _log_buy_skip(symbol, _detail)
        recorder.reject("xgb_confidence", _detail)
        return available_cash

    # Gate 4 — Relative strength: stock must be outperforming SPY over last N bars
    if ctx.spy_5bar_return is not None and symbol != "SPY":
        stock_5bar = ctx.sig_bars["close"].pct_change(RS_LOOKBACK_BARS).iloc[-1]
        if not math.isnan(stock_5bar) and float(stock_5bar) < ctx.spy_5bar_return:
            _detail = f"RS weak ({stock_5bar:.2%} vs SPY {ctx.spy_5bar_return:.2%})"
            _log_buy_skip(symbol, _detail)
            recorder.reject("relative_strength", _detail)
            return available_cash

    # Gate 5 — Open order: no duplicate limit buy submissions
    if symbol in ctx.buy_order_syms:
        _log_buy_skip(symbol, "open buy order already pending")
        recorder.reject("open_order", "open buy order already pending")
        return available_cash

    # Gate 6 — Earnings proximity (prefetched in parallel before loop)
    if ctx.earnings_map.get(symbol, False):
        _log_buy_skip(symbol, "earnings proximity")
        recorder.reject("earnings_proximity", "earnings proximity")
        return available_cash

    # Gate 7 — Correlation: avoid adding a position highly correlated with existing holdings.
    _corr_ok, _corr_reason = _passes_correlation_gate(symbol, ctx.positions, ctx.bars_map)
    if not _corr_ok:
        recorder.reject("correlation", _corr_reason)
        return available_cash

    # Gate 7.5 — Wash-sale guard (IRS IRC §1091): block re-buy within 30 days of a loss sale
    if _is_wash_sale_risk(con, symbol):
        _log_buy_skip(symbol, "wash-sale guard active")
        recorder.reject("wash_sale", "wash-sale guard active")
        return available_cash

    # Gate 7.7 — Stop re-entry block: don't re-buy a symbol whose stop fired today
    if symbol in ctx.stop_fired_today:
        _detail = "stop-loss fired earlier today (re-entry blocked)"
        _log_buy_skip(symbol, _detail)
        recorder.reject("stop_reentry", _detail)
        return available_cash

    # Gate 7.9 — MACD confirmation (daily bars only — intraday MACD oscillates too fast)
    # Disabled by default (MACD_CONFIRMATION_MIN=-inf). Set to 0.0 to require positive crossover.
    if not math.isinf(MACD_CONFIRMATION_MIN):
        _daily_bars = ctx.bars_map.get(symbol, BarData(pd.DataFrame(), pd.DataFrame())).bars_daily
        if not _daily_bars.empty:
            _macd_diff = float(_daily_bars.iloc[-1].get("macd_diff", 0.0))
            if _macd_diff <= MACD_CONFIRMATION_MIN:
                _detail = f"MACD gate: daily macd_diff={_macd_diff:.4f} <= min={MACD_CONFIRMATION_MIN}"
                _log_buy_skip(symbol, _detail)
                recorder.reject("macd", _detail)
                return available_cash

    # Gate 8 — Cash and risk approval
    # ensemble_size: STRONG_BUY=0.20, BUY=0.12 — use as confidence multiplier on Kelly
    kelly_f      = _kelly_fraction(con, symbol)
    confidence   = ctx.ensemble_size / BUY_FRACTION  # 1.0 for BUY, 1.67 for STRONG_BUY
    pos_fraction = min(kelly_f * ctx.macro_cap * confidence, KELLY_FRACTION_MAX)

    # Reinvestment guard: tradeable_capital is pre-computed once per cycle by main.py
    # using compute_tradeable_capital() so we avoid per-symbol DB reads here.
    if ctx.tradeable_capital <= 0.0:
        _detail = "no tradeable capital (profits only mode, no profits yet)"
        _log_buy_skip(symbol, _detail)
        recorder.reject("tradeable_capital", _detail)
        return available_cash
    notional = ctx.tradeable_capital * pos_fraction
    if notional <= 0.0:
        _detail = f"zero position size (kelly={kelly_f:.3f}, macro_cap={ctx.macro_cap:.2f})"
        _log_buy_skip(symbol, _detail)
        recorder.reject("position_size", _detail)
        return available_cash

    # Risk-per-trade cap: size so max dollar loss ≤ MAX_RISK_PER_TRADE_PCT of portfolio.
    # Derives the implied stop % from ATR (same formula as risk_manager), then back-calculates
    # max safe notional — volatile stocks get smaller positions automatically.
    if ctx.current_atr and ctx.current_atr > 0 and ctx.current_price > 0:
        stop_pct = max(ATR_MIN_STOP_PCT, min(ATR_MAX_STOP_PCT,
                       (ATR_STOP_MULTIPLIER * ctx.current_atr) / ctx.current_price))
        tp_target_pct = _atr_tp_pct(ctx.current_atr, ctx.current_price)
    else:
        stop_pct = STOP_LOSS_PCT
        tp_target_pct = _TP_FLOOR

    # Gate 8a — Minimum absolute profit target: not worth entering if upside < MIN_TP_PCT
    if tp_target_pct < MIN_TP_PCT:
        _detail = f"TP target {tp_target_pct:.1%} < min {MIN_TP_PCT:.1%}"
        _log_buy_skip(symbol, _detail)
        recorder.reject("tp_target", _detail)
        return available_cash

    # Gate 8b — Minimum risk/reward: require TP ≥ MIN_RR_RATIO × stop distance
    rr_ratio = tp_target_pct / stop_pct
    if rr_ratio < MIN_RR_RATIO:
        _detail = f"R:R {rr_ratio:.2f} < min {MIN_RR_RATIO} (TP={tp_target_pct:.1%}, stop={stop_pct:.1%})"
        _log_buy_skip(symbol, _detail)
        recorder.reject("risk_reward", _detail)
        return available_cash

    max_risk_notional = (ctx.portfolio_value * MAX_RISK_PER_TRADE_PCT) / stop_pct
    if notional > max_risk_notional:
        logger.info(
            f"BUY {symbol}: notional capped ${notional:.0f}→${max_risk_notional:.0f} "
            f"(stop_pct={stop_pct:.1%}, max_risk={MAX_RISK_PER_TRADE_PCT:.1%})"
        )
        notional = max_risk_notional

    # Gate 8c — Sector exposure cap: total portfolio value in this sector ≤ MAX_SECTOR_EXPOSURE_PCT
    _sym_sector = SECTOR_MAP.get(symbol, "Unknown")
    if _sym_sector not in ("Unknown", "Broad_ETF"):
        _sector_val = sum(
            float(getattr(pos, "market_value", 0) or 0)
            for sym, pos in ctx.positions.items()
            if SECTOR_MAP.get(sym, "Unknown") == _sym_sector
        )
        _sector_pct = _sector_val / ctx.portfolio_value if ctx.portfolio_value > 0 else 0
        if _sector_pct >= MAX_SECTOR_EXPOSURE_PCT:
            _detail = f"{_sym_sector} sector at {_sector_pct:.1%} of portfolio (max {MAX_SECTOR_EXPOSURE_PCT:.0%})"
            _log_buy_skip(symbol, _detail)
            recorder.reject("sector_exposure", _detail)
            return available_cash

    # Gate 8e — Cash reserve: always keep MIN_CASH_RESERVE_PCT uninvested
    _min_reserve = ctx.portfolio_value * MIN_CASH_RESERVE_PCT
    if notional > available_cash * CASH_USE_FRACTION:
        _reason = f"need ${notional:.2f}, running cash ${available_cash:.2f}"
        logger.warning(f"BUY {symbol} skipped — {_reason}")
        recorder.reject("cash_use_fraction", _reason)
        return available_cash
    if available_cash - notional < _min_reserve:
        _reason = (f"would breach cash reserve (need ${notional:.0f}, "
                   f"reserve=${_min_reserve:.0f}, cash=${available_cash:.0f})")
        logger.info(f"BUY {symbol} skipped — {_reason}")
        recorder.reject("cash_reserve_min", _reason)
        return available_cash
    _managed = ctx.pool.tradeable_cash if ctx.pool else None
    if not risk.approve_buy(symbol, notional, ctx.portfolio_value,
                            ctx.portfolio_value, ctx.positions, managed_capital=_managed):
        _reason = "risk.approve_buy() declined (portfolio-level risk check)"  # was previously silent
        logger.info(f"BUY {symbol} skipped — {_reason}")
        recorder.reject("risk_manager_approval", _reason)
        return available_cash

    result = client.buy(symbol, notional, limit_price=ctx.current_price)
    if result:
        filled_qty = client.wait_for_fill(result["order_id"], timeout_secs=15)
        if filled_qty > 0:
            # Use actual fill price for P&L accuracy; fall back to limit estimate
            _actual_fill = client.get_fill_price(result["order_id"])
            if _actual_fill is None:
                fill_price = ctx.current_price
                logger.warning(
                    f"BUY {symbol}: actual fill price unavailable — "
                    f"using limit estimate ${ctx.current_price:.2f} (audit: cost basis may differ)"
                )
            else:
                fill_price = _actual_fill
                slippage_bps = (_actual_fill - ctx.current_price) / ctx.current_price * 10_000
                logger.info(
                    f"BUY {symbol}: filled ${_actual_fill:.2f} "
                    f"({slippage_bps:+.1f} bps vs limit ${ctx.current_price:.2f})"
                )
            fill_shares = notional / fill_price
            _drivers = ctx.xgb.explain(ctx.latest)
            recorder.record_executed(notional, fill_price, fill_shares, xgb_drivers=_drivers)
            _sent_s = ctx.sentiments.get(symbol, 0.0)
            _ens_score = ensemble_confidence(ctx.xgb_prob, ctx.lstm_prob, _sent_s, ctx.macro_score)
            _sym_sector_tg = SECTOR_MAP.get(symbol, "")
            _sect_pct_tg = 0.0
            if _sym_sector_tg and _sym_sector_tg not in ("Unknown", "Broad_ETF") and ctx.portfolio_value > 0:
                _existing_sv = sum(
                    float(getattr(p, "market_value", 0) or 0)
                    for s2, p in ctx.positions.items()
                    if SECTOR_MAP.get(s2, "") == _sym_sector_tg
                )
                _sect_pct_tg = (_existing_sv + notional) / ctx.portfolio_value * 100
            _cash_pct_tg = ((available_cash - notional) / ctx.portfolio_value * 100
                            if ctx.portfolio_value > 0 else 0.0)
            tg.alert_buy(symbol, fill_shares, fill_price,
                         ctx.regime_name, ctx.portfolio_value, ctx.vs_spy_today * 100,
                         notional=notional,
                         xgb_prob=ctx.xgb_prob, lstm_prob=ctx.lstm_prob,
                         sentiment_score=_sent_s,
                         ensemble_score=_ens_score,
                         drivers=_drivers,
                         sector=_sym_sector_tg,
                         sector_pct_after=_sect_pct_tg,
                         cash_pct_after=_cash_pct_tg)
            _ai_rsn = (
                f"Bought {symbol} at ${fill_price:.2f}. "
                f"XGB: {ctx.xgb_prob:.0%}, LSTM: {ctx.lstm_prob:.0%}, regime: {ctx.regime_name}. "
                f"Stop: {stop_pct:.1%}, target: {tp_target_pct:.1%}, R:R: {rr_ratio:.2f}x."
            )
            _trade_id = log_trade(con, symbol, "BUY", fill_shares,
                                  fill_price, notional, ctx.regime_name, ctx.portfolio_value, 0,
                                  xgb_prob=ctx.xgb_prob, lstm_prob=ctx.lstm_prob,
                                  sentiment_score=ctx.sentiments.get(symbol, 0.0),
                                  macro_score=ctx.macro_score,
                                  order_id=result.get("order_id"),
                                  feature_drivers=json.dumps(_drivers) if _drivers is not None else None,
                                  ai_reasoning=_ai_rsn,
                                  stop_loss=round(fill_price * (1 - stop_pct), 4),
                                  take_profit=round(fill_price * (1 + tp_target_pct), 4),
                                  risk_reward_ratio=round(rr_ratio, 4))
            try:
                _journal_open(
                    con, symbol, _trade_id,
                    entry_reason=_ai_rsn,
                    entry_signals={
                        "xgb_prob": ctx.xgb_prob, "lstm_prob": ctx.lstm_prob,
                        "macro_score": ctx.macro_score, "regime": ctx.regime_name,
                        "stop_pct": round(stop_pct, 4), "tp_pct": round(tp_target_pct, 4),
                        "rr_ratio": round(rr_ratio, 3), "volume_ratio": round(ctx.volume_ratio, 3),
                    },
                    entry_confidence=ctx.xgb_prob,
                    pattern_tags=[ctx.regime_name, SECTOR_MAP.get(symbol, "Unknown")],
                )
            except Exception as _je:
                logger.warning(f"Journal open failed for {symbol} (non-fatal): {_je}")
            if ctx.pool:
                _pool_buy(con, ctx.pool.id, notional, symbol=symbol)
            _rec_action(con, "buy", symbol, reasoning=_ai_rsn,
                        confidence=int(ctx.xgb_prob * 100), status="executed")
            _upsert_position_state(con, symbol, fill_price, fill_price, ctx.current_atr, fill_shares)
            available_cash -= notional
            ctx.buy_order_syms.discard(symbol)  # order is now filled, not pending
        else:
            logger.warning(f"BUY {symbol} order did not fill — position state NOT recorded")
            recorder.record_order_not_filled("order submitted but did not fill within timeout")
    else:
        recorder.record_order_not_filled("order submission failed (client.buy() returned None)")

    return available_cash
