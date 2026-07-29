"""Startup pre-rendering for dashboard/app.py, extracted to keep app.py under
the 500-line limit. gr.Plot ignores value=callable in Gradio 5.9 and
demo.load() events do not fire reliably, so every chart/HTML panel that
would otherwise be lazy-rendered gets computed upfront here, concurrently,
and passed into app.py as static values."""
from __future__ import annotations

import concurrent.futures as _cf
import traceback as _tb_init

import plotly.graph_objects as _go
from loguru import logger

from dashboard.charts import (
    render_equity_chart, render_allocation_chart,
    render_pnl_chart, render_feature_importance_chart,
    render_returns_histogram, render_winloss_chart,
)
from dashboard.components.capital import render_capital_chart, render_capital_health, render_capital_ledger
from dashboard.components.counterfactual import render_counterfactual_analysis
from dashboard.components.decision_quality import render_decision_quality_summary
from dashboard.components.executive_summary import render_executive_summary
from dashboard.components.market_mood import render_market_mood
from dashboard.components.models import render_institutional_metrics
from dashboard.components.news import render_news_feed_initial


def _safe_fig(fn):
    try:
        return fn()
    except Exception as exc:
        logger.error(f"[startup] chart render failed: {fn.__name__}\n{_tb_init.format_exc()}")
        fig = _go.Figure()
        fig.add_annotation(text=f"Chart error: {exc}", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color="#ff5252"))
        return fig


def _safe_html(fn, fallback=None):
    try:
        return fn()
    except Exception as exc:
        logger.error(f"[startup] HTML render failed: {fn.__name__}\n{_tb_init.format_exc()}")
        if fallback is not None:
            return fallback
        return (
            f'<div style="background:#171a21;border:1px solid #ff5252;'
            f'border-left:3px solid #ff5252;border-radius:8px;padding:16px 20px;margin:8px 0;">'
            f'<div style="font-size:15px;font-weight:700;color:#ff5252;margin-bottom:6px;">'
            f'&#9888; {fn.__name__} unavailable</div>'
            f'<div style="font-size:11px;color:#b0b7c3;line-height:1.7;">'
            f'{type(exc).__name__}: {str(exc)[:120]}<br>Full details in logs/errors.log</div></div>'
        )


def prerender_all() -> dict:
    """Renders every startup panel concurrently and blocks until each is
    ready (or times out), returning the {key: value} dict app.py mounts
    directly as static gr.Plot/gr.HTML values."""
    logger.info("[startup] pre-rendering all components...")
    executor = _cf.ThreadPoolExecutor(max_workers=13)
    chart_futs = {
        "equity":       executor.submit(_safe_fig,  render_equity_chart),
        "alloc":        executor.submit(_safe_fig,  render_allocation_chart),
        "pnl":          executor.submit(_safe_fig,  render_pnl_chart),
        "capital":      executor.submit(_safe_fig,  render_capital_chart),
        "ret_hist":     executor.submit(_safe_fig,  render_returns_histogram),
        "winloss":      executor.submit(_safe_fig,  render_winloss_chart),
        "fi":           executor.submit(_safe_fig,  render_feature_importance_chart),
        "news":         executor.submit(_safe_html, render_news_feed_initial),
        "market_mood":  executor.submit(_safe_html, render_market_mood),
        # These call get_data() which triggers a yfinance fetch on first run;
        # running them in the pool means they run in parallel with charts
        # instead of blocking the main thread after chart pre-rendering completes.
        "exec_summary":   executor.submit(_safe_html, render_executive_summary),
        "metrics":        executor.submit(_safe_html, render_institutional_metrics),
        "cap_health":     executor.submit(_safe_html, render_capital_health),
        "cap_ledger":     executor.submit(_safe_html, render_capital_ledger),
        # trust_ledger.db is pulled from HF at startup (refresh_db_from_hf) and can
        # be slow/stalled the same way trades.db can -- these two read it directly,
        # so they need the same timeout guard as the other network-touching panels
        # above (unguarded gr.HTML(value=fn) previously hung the whole Space launch).
        "decision_quality": executor.submit(_safe_html, render_decision_quality_summary),
        "counterfactual":   executor.submit(_safe_html, render_counterfactual_analysis),
    }

    def _wait(key, timeout):
        try:
            return chart_futs[key].result(timeout=timeout)
        except Exception as exc:
            logger.warning(f"[startup] {key} timed out or failed after {timeout}s")
            if key in ("news", "market_mood", "decision_quality", "counterfactual"):
                return (f'<div style="color:#ff5252;font-size:12px;padding:8px;">'
                        f'&#9888; {key} unavailable: timed out after {timeout}s</div>')
            fig = _go.Figure()
            fig.add_annotation(text=f"Timed out after {timeout}s: {exc}", xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False, font=dict(color="#ff5252"))
            return fig

    ci = {
        "equity":       _wait("equity",       15),
        "alloc":        _wait("alloc",        15),
        "pnl":          _wait("pnl",          15),
        "capital":      _wait("capital",      15),
        "ret_hist":     _wait("ret_hist",     15),
        "winloss":      _wait("winloss",      15),
        "fi":           _wait("fi",           15),
        "news":         _wait("news",         15),
        "market_mood":  _wait("market_mood",  25),  # 20 s yfinance + buffer
        "exec_summary": _wait("exec_summary", 20),
        "metrics":      _wait("metrics",      20),
        "cap_health":   _wait("cap_health",   15),
        "cap_ledger":   _wait("cap_ledger",   15),
        "decision_quality": _wait("decision_quality", 15),
        "counterfactual":   _wait("counterfactual",   15),
    }
    executor.shutdown(wait=False)
    logger.info("[startup] pre-render complete")
    return ci
