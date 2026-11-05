"""Paper Trading Scorecard (split from models.py, ADR-079)."""
from __future__ import annotations
import time as _time
from loguru import logger
from dashboard.design_system import (
    TEXT2, GAIN, LOSS, NEURAL,
    _card, _empty_state, _section, _stat_card,
)
import pandas as pd
from dashboard.data import get_data, get_db_conn
from bot.core.error_logger import safe_render

# ── Paper Trading Scorecard ───────────────────────────────────────────────────
_BENCH_CACHE: dict = {}
_BENCH_CACHE_TS: float = 0.0
_BENCH_CACHE_TTL: float = 3600.0


@safe_render("Paper Trading Scorecard")
def render_paper_trading_scorecard() -> str:
    global _BENCH_CACHE, _BENCH_CACHE_TS
    import yfinance as yf

    d  = get_data()
    df = d.get("trades_df", pd.DataFrame())

    if df.empty:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("🏆", "Paper Trading Scorecard", "vs market")}'
            f'{_card(_empty_state("📊", "No history yet", "Scorecard activates after the first trade."))}'
            f'</div>'
        )

    # Exclude SELL_RECONCILE — see charts.py render_equity_chart for why.
    daily = (df[df["action"] != "SELL_RECONCILE"].dropna(subset=["portfolio_value"])
               .groupby("date")["portfolio_value"].last()
               .reset_index().sort_values("date"))
    daily.columns = ["date", "value"]

    if len(daily) < 2:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("🏆", "Paper Trading Scorecard", "vs market")}'
            f'{_card(_empty_state("📊", "Need ≥ 2 days", "Building history &mdash; check back tomorrow."))}'
            f'</div>'
        )

    start_date = str(daily["date"].iloc[0])
    bot_start  = float(daily["value"].iloc[0])
    bot_end    = float(daily["value"].iloc[-1])
    bot_ret    = (bot_end / bot_start - 1) if bot_start > 0 else 0.0
    n_days     = (pd.to_datetime(daily["date"].iloc[-1]) - pd.to_datetime(daily["date"].iloc[0])).days

    rets   = daily["value"].pct_change().dropna()
    std_r  = float(rets.std())
    mean_r = float(rets.mean())
    sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0
    peak   = daily["value"].cummax()
    max_dd = float(((peak - daily["value"]) / peak.replace(0, float("nan"))).max())

    sells    = df[df["action"].str.startswith("SELL") & (df["action"] != "SELL_RECONCILE")]
    win_rate = float((sells["pnl_pct"] > 0).sum() / len(sells)) if len(sells) > 0 else 0.0

    # AI follow rate: % of BUY recommendations executed as actual BUY trades (last 30 days)
    follow_rate: float | None = None
    try:
        with get_db_conn() as _con:
            _res = _con.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN EXISTS (
                            SELECT 1 FROM trades t
                            WHERE t.symbol = r.symbol
                              AND date(t.timestamp) = r.prediction_date
                              AND t.action = 'BUY'
                          ) THEN 1 ELSE 0 END) AS executed
                   FROM recommendations r
                   WHERE r.recommendation = 'BUY'
                     AND r.prediction_date >= date('now', '-30 days')"""
            ).fetchone()
            if _res and _res[0] > 0:
                follow_rate = float(_res[1]) / float(_res[0])
    except Exception as _fe:
        logger.debug(f"ai_follow_rate: {_fe}")

    # SPY/QQQ returns over the same period (1-hour cache)
    spy_ret = qqq_ret = None
    if _time.time() - _BENCH_CACHE_TS < _BENCH_CACHE_TTL and _BENCH_CACHE:
        spy_ret = _BENCH_CACHE.get("spy")
        qqq_ret = _BENCH_CACHE.get("qqq")
    else:
        try:
            _bd = yf.download(["SPY", "QQQ"], start=start_date, progress=False, auto_adjust=True)
            for sym, key in [("SPY", "spy"), ("QQQ", "qqq")]:
                try:
                    _col = (_bd["Close"][sym] if isinstance(_bd["Close"], pd.DataFrame)
                            else _bd["Close"]).dropna()
                    if len(_col) >= 2:
                        _BENCH_CACHE[key] = float(_col.iloc[-1] / _col.iloc[0] - 1)
                except Exception as exc:
                    logger.debug(f"institutional_metrics: {sym} benchmark fetch: {exc}")
            _BENCH_CACHE_TS = _time.time()
            spy_ret = _BENCH_CACHE.get("spy")
            qqq_ret = _BENCH_CACHE.get("qqq")
        except Exception as _be:
            logger.debug(f"benchmark_fetch: {_be}")

    def _vs(bench):
        if bench is None:
            return "&mdash;"
        diff = bot_ret - bench
        return f"{'+'if diff>=0 else ''}{diff:.1%}"

    def _vc(bench):
        return (GAIN if bot_ret >= bench else LOSS) if bench is not None else TEXT2

    bot_c = GAIN if bot_ret > 0 else LOSS
    sh_c  = GAIN if sharpe > 1 else (NEURAL if sharpe > 0.5 else LOSS)
    dd_c  = GAIN if max_dd < 0.05 else (NEURAL if max_dd < 0.12 else LOSS)
    wr_c  = GAIN if win_rate >= 0.55 else (NEURAL if win_rate >= 0.45 else LOSS)
    fr_c  = (GAIN if follow_rate is not None and follow_rate > 0.15 else TEXT2)

    spy_sub = f"SPY: {spy_ret:+.1%}" if spy_ret is not None else "loading…"
    qqq_sub = f"QQQ: {qqq_ret:+.1%}" if qqq_ret is not None else "loading…"

    row1 = (
        f'<div class="nt-cards">'
        + _stat_card("Bot Return",   f"{bot_ret:+.1%}", TEXT2, bot_c,
                     f"since {start_date}", 0.0)
        + _stat_card("vs SPY",       _vs(spy_ret),      TEXT2, _vc(spy_ret), spy_sub, 0.06)
        + _stat_card("vs QQQ",       _vs(qqq_ret),      TEXT2, _vc(qqq_ret), qqq_sub, 0.12)
        + _stat_card("Win Rate",     f"{win_rate:.0%}" if len(sells) > 0 else "&mdash;",
                     TEXT2, wr_c, f"{len(sells)} closed trades", 0.18)
        + f'</div>'
    )
    row2 = (
        f'<div class="nt-cards">'
        + _stat_card("Risk-Adjusted Return", f"{sharpe:.2f}", TEXT2, sh_c,
                     ">1.0 = good · >2.0 = excellent", 0.0)
        + _stat_card("Worst Portfolio Dip", f"{max_dd:.1%}", TEXT2, dd_c,
                     "Biggest drop from peak to bottom", 0.06)
        + _stat_card("Signals Executed",
                     f"{follow_rate:.0%}" if follow_rate is not None else "&mdash;",
                     TEXT2, fr_c, "% of buy signals the bot acted on (30d)", 0.12)
        + _stat_card("Days Running",    str(n_days),       TEXT2, TEXT2,
                     f"since {start_date}", 0.18)
        + f'</div>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🏆", "Paper Trading Scorecard", f"vs SPY · {n_days} days")}'
        f'{row1}{row2}'
        f'</div>'
    )
