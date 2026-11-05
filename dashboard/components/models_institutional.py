"""Institutional Metrics / Performance Deep Dive (split from models.py, ADR-079)."""
from __future__ import annotations
import datetime
from loguru import logger
from dashboard.design_system import (
    BG, SURFACE, BORDER, TEXT2,
    GAIN, LOSS, NEURAL,
    FONT_LABEL,
    _section, _wrap,
)
import pandas as pd
from dashboard.data import get_data
from bot.core.error_logger import safe_render

# ── Render: institutional metrics ─────────────────────────────────────────────
@safe_render("Institutional Metrics")
def render_institutional_metrics() -> str:
    d  = get_data()
    df = d["trades_df"]

    if df.empty or "portfolio_value" not in df.columns:
        msg = f'<div style="color:{TEXT2};text-align:center;padding:28px;font-size:{FONT_LABEL};">No trade history yet.</div>'
        return f'<div class="nt nt-wrap">{_section("📐","Performance Deep Dive")}{_wrap(msg)}</div>'

    # Exclude SELL_RECONCILE — see render_paper_trading_scorecard for why.
    daily = (df[df["action"] != "SELL_RECONCILE"].dropna(subset=["portfolio_value"])
               .groupby("date")["portfolio_value"].last()
               .reset_index()
               .sort_values("date"))
    daily.columns = ["date", "value"]

    if len(daily) < 3:
        msg = f'<div style="color:{TEXT2};text-align:center;padding:28px;font-size:{FONT_LABEL};">Need ≥ 3 days of history.</div>'
        return f'<div class="nt nt-wrap">{_section("📐","Performance Deep Dive")}{_wrap(msg)}</div>'

    rets   = daily["value"].pct_change().dropna()
    mean_r = float(rets.mean())
    std_r  = float(rets.std())

    sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0

    neg_rets = rets[rets < 0]
    down_std = float(neg_rets.std()) if len(neg_rets) > 1 else std_r
    sortino  = (mean_r / down_std * (252 ** 0.5)) if down_std > 0 else 0.0

    vals  = daily["value"]
    peak  = vals.cummax()
    max_dd = float(((peak - vals) / peak.replace(0, float("nan"))).max())

    n_days  = (pd.to_datetime(daily["date"].iloc[-1]) - pd.to_datetime(daily["date"].iloc[0])).days
    start_v = float(daily["value"].iloc[0])
    end_v   = float(daily["value"].iloc[-1])
    cagr    = ((end_v / start_v) ** (365.0 / n_days) - 1) if n_days > 0 and start_v > 0 else 0.0
    calmar  = (cagr / max_dd) if max_dd > 0 else 0.0

    sells    = df[df["action"].str.startswith("SELL") & (df["action"] != "SELL_RECONCILE")]
    n_s      = len(sells)
    win_rate = float((sells["pnl_pct"] > 0).sum() / n_s) if n_s > 0 else 0.0
    pnl_vals = [float(p) for p in sells["pnl_pct"].dropna()] if n_s > 0 else []
    gross_w  = sum(p for p in pnl_vals if p > 0)
    gross_l  = abs(sum(p for p in pnl_vals if p < 0))
    profit_factor: float | None = round(gross_w / gross_l, 2) if gross_l > 0 else None

    total_return = (end_v - start_v) / start_v if start_v > 0 else 0.0
    scratch_count = sum(1 for p in pnl_vals if p == 0)
    alpha_inc: float | None = None
    alpha_60d: float | None = None
    try:
        from bot.monitor.dashboard_data import spy_return_since as _spy_rs
        _spy = _spy_rs(str(daily["date"].iloc[0]))
        if _spy is not None:
            alpha_inc = round(total_return - _spy, 4)
        _s60 = datetime.date.today() - datetime.timedelta(days=60)
        _d60 = daily[daily["date"] >= _s60]
        if len(_d60) >= 2:
            _r60 = float(_d60["value"].iloc[-1]) / float(_d60["value"].iloc[0]) - 1
            _spy60 = _spy_rs(_s60.isoformat())
            if _spy60 is not None:
                alpha_60d = round(_r60 - _spy60, 4)
    except Exception as exc:
        logger.debug(f"institutional_metrics: alpha_calc: {exc}")

    def _row(label, val_str, color, desc):
        return (
            f'<tr><td style="padding:10px 14px;border-bottom:1px solid {BORDER};'
            f'background:{SURFACE};color:{TEXT2} !important;font-size:{FONT_LABEL};font-weight:600;">{label}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {BORDER};'
            f'background:{SURFACE};font-family:-apple-system,monospace;'
            f'color:{color} !important;font-weight:700;">{val_str}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid {BORDER};'
            f'background:{SURFACE};color:{TEXT2} !important;font-size:{FONT_LABEL};">{desc}</td></tr>'
        )

    sh_c = GAIN if sharpe > 1 else (NEURAL if sharpe > 0.5 else LOSS)
    so_c = GAIN if sortino > 1.5 else (NEURAL if sortino > 0.8 else LOSS)
    dd_c = GAIN if max_dd < 0.05 else (NEURAL if max_dd < 0.12 else LOSS)
    ca_c = GAIN if calmar > 2 else (NEURAL if calmar > 1 else LOSS)
    wr_c = GAIN if win_rate > 0.55 else (NEURAL if win_rate > 0.45 else LOSS)
    pf_c     = GAIN if profit_factor is not None and profit_factor > 1.5 else (NEURAL if profit_factor is not None and profit_factor > 1.0 else LOSS)
    al_inc_c = GAIN if alpha_inc is not None and alpha_inc > 0 else (NEURAL if alpha_inc is not None and alpha_inc > -0.02 else LOSS)
    al60_c   = GAIN if alpha_60d is not None and alpha_60d > 0 else (NEURAL if alpha_60d is not None and alpha_60d > -0.02 else LOSS)

    pf_str     = f"{profit_factor:.2f}" if profit_factor is not None else "n/a"
    al_inc_str = f"{alpha_inc:+.2%}" if alpha_inc is not None else "n/a"
    al60_str   = f"{alpha_60d:+.2%}" if alpha_60d is not None else "n/a"

    rows = (
        _row("Return quality vs. risk taken", f"{sharpe:.2f}", sh_c,
             "Sharpe ratio &mdash; how much return per unit of total risk. &gt;1.0 = good, &gt;2.0 = excellent")
        + _row("How well losses are controlled", f"{sortino:.2f}", so_c,
               "Sortino ratio &mdash; like Sharpe but only penalises losing months, not winning volatility")
        + _row("Worst drop from peak", f"{max_dd:.1%}", dd_c,
               "Max drawdown &mdash; biggest drop from peak to trough")
        + _row("Return vs. worst-case loss", f"{calmar:.2f}", ca_c,
               "Calmar ratio &mdash; annualised return divided by max drawdown. Higher = better recovery")
        + _row("Trades that made money", f"{win_rate:.1%}", wr_c,
               "Win rate &mdash; % of closed trades that were profitable (target: &gt;55%)")
        + _row("Gross wins &divide; gross losses", pf_str, pf_c,
               f"Profit factor &mdash; total gains &divide; total losses. &gt;1.5 = good ({scratch_count} scratch)")
        + _row("Alpha vs. S&amp;P 500 (since launch)", al_inc_str, al_inc_c,
               "Inception-to-date outperformance vs. the S&amp;P 500 benchmark")
        + _row("Alpha vs. S&amp;P 500 (rolling 60d)", al60_str, al60_c,
               "Rolling 60-day alpha &mdash; validates whether win rate is beating the market now")
    )
    help_block = (
        f'<div style="background:{BG};border-top:1px solid {BORDER};'
        f'padding:8px 14px;font-size:{FONT_LABEL};color:{TEXT2};line-height:1.6;">'
        f'All metrics computed from trade history since launch. '
        f'Need at least 30 days of history for reliable estimates &mdash; early numbers will fluctuate.'
        f'</div>'
    )
    n_str = f"{n_days} days of history" if n_days > 0 else "&mdash;"
    table = _wrap(f'<table class="nt-tbl" style="width:100%">{rows}</table>' + help_block)
    return (f'<div class="nt nt-wrap">'
            f'{_section("📐","Performance Deep Dive", n_str)}{table}</div>')
