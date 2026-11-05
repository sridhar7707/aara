"""Investor View / plain-language Models tab (split from models.py, ADR-079)."""
from __future__ import annotations
import os
from loguru import logger
from dashboard.design_system import (
    BG, SURFACE, BORDER, TEXT1, TEXT2,
    PRIMARY, GAIN, LOSS, NEURAL,
    FONT_VALUE, FONT_LABEL,
    _section, _stat_card,
    _FI_LABELS,
)
import pandas as pd
from dashboard.data import get_data
from dashboard.components.ai_panel import _WHY_MAP
from bot.core.error_logger import safe_render
from dashboard.components.portfolio import _SELL_REASON
from dashboard.components.models_validation import _lstm_loss_display

# ── Render: investor view (plain-language Models tab) ────────────────────────
def _model_quality_fallback() -> str:
    """Return a model-quality card when no closed trades exist yet."""
    import json as _json
    vr_path = "models/validation_report.json"
    if not os.path.exists(vr_path):
        return (
            f'<div style="color:{TEXT2};text-align:center;padding:32px;font-size:{FONT_VALUE};">'
            f'Bot is live and scanning markets.<br>'
            f'<span style="font-size:{FONT_LABEL};">Win Rate and P&L will appear after the first completed trade.</span>'
            f'</div>'
        )
    try:
        with open(vr_path) as fh:
            r = _json.load(fh)
    except Exception:
        return (
            f'<div style="color:{TEXT2};text-align:center;padding:32px;font-size:{FONT_VALUE};">'
            f'Bot is live. Awaiting first trade to show performance metrics.</div>'
        )
    auc      = r.get("xgb_val_auc",  0.0)
    auc_c    = GAIN if auc >= 0.60 else (NEURAL if auc >= 0.55 else LOSS)
    loss_c, loss_val = _lstm_loss_display(r, "Retired")
    generated = r.get("generated_at", "")[:10]

    cards = (
        f'<div class="nt-cards">'
        + _stat_card("Win Rate",          "&mdash;",
                TEXT2, TEXT2, "appears after first closed trade", 0.0)
        + _stat_card("Avg Winning Trade", "&mdash;",
                TEXT2, TEXT2, "appears after first closed trade", 0.06)
        + _stat_card("XGBoost AUC",        f"{auc:.3f}",
                TEXT2, auc_c, "≥0.60 = good · 0.50 = random", 0.12)
        + _stat_card("LSTM Val Loss",     loss_val, TEXT2, loss_c,
                "Retired (ADR-077)" if r.get("lstm_retired") else "≤0.65 = well-trained · 0.69 = random", 0.18)
        + f'</div>'
    )
    explain = (
        f'<div style="background:{BG};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin-top:8px;">'
        f'<div style="font-size:{FONT_LABEL};color:{TEXT2};line-height:1.7;">'
        f'<strong style="color:{TEXT1};">Models trained · awaiting first trade</strong><br>'
        f'Models last trained <b>{generated}</b>. The AI is actively scanning all symbols each cycle. '
        f'Win Rate and P&L metrics appear automatically after the first position closes.'
        f'</div></div>'
    )
    return cards + explain


@safe_render("Investor View")
def render_investor_view() -> str:
    d  = get_data()
    df = d["trades_df"]
    if df.empty:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("🤖","AI Performance","investor summary")}'
            f'{_model_quality_fallback()}'
            f'</div>'
        )

    sells  = df[df["action"].str.startswith("SELL") & (df["action"] != "SELL_RECONCILE")]
    n_s    = len(sells)
    wins   = sells[sells["pnl_pct"] > 0]  if n_s > 0 else pd.DataFrame()
    losses = sells[sells["pnl_pct"] <= 0] if n_s > 0 else pd.DataFrame()
    wr     = len(wins) / n_s if n_s > 0 else 0.0
    avg_w  = float(wins["pnl_pct"].mean()   * 100) if len(wins)   > 0 else 0.0
    avg_l  = float(losses["pnl_pct"].mean() * 100) if len(losses) > 0 else 0.0
    rr     = abs(avg_w / avg_l) if avg_l != 0 else 0.0

    cards = (
        f'<div class="nt-cards">'
        + _stat_card("Win Rate",          f"{wr:.0%}" if n_s > 0 else "&mdash;",
                TEXT2, GAIN if wr >= 0.55 else (NEURAL if wr >= 0.45 else LOSS),
                f"AI correct {len(wins)} of {n_s} closed trades", 0.0)
        + _stat_card("Avg Winning Trade", f"+{avg_w:.1f}%" if avg_w > 0 else "&mdash;",
                TEXT2, GAIN, "Average gain per winning trade", 0.06)
        + _stat_card("Avg Losing Trade",  f"{avg_l:.1f}%"  if avg_l < 0 else "&mdash;",
                TEXT2, LOSS, "Average loss per losing trade",  0.12)
        + _stat_card("Risk / Reward",     f"{rr:.1f}×"     if rr > 0   else "&mdash;",
                TEXT2, GAIN if rr >= 1.5 else (NEURAL if rr >= 1.0 else LOSS),
                "Avg win ÷ avg loss &mdash; >1.5× is good", 0.18)
        + f'</div>'
    )

    # Top buy signals from recent SHAP
    signal_counts: dict[str, int] = {}
    for _, row in df[df["action"] == "BUY"].tail(20).iterrows():
        drv_raw = row.get("feature_drivers")
        if not drv_raw:
            continue
        try:
            import json as _j
            ds = _j.loads(drv_raw) if isinstance(drv_raw, str) else drv_raw
            for feat, val in (ds or []):
                if float(val) > 0:
                    name = _WHY_MAP.get(feat, (_FI_LABELS.get(feat, feat),))[0]
                    signal_counts[name] = signal_counts.get(name, 0) + 1
        except Exception as exc:
            logger.debug(f"parse_signal_counts: {exc}")
    top3 = sorted(signal_counts.items(), key=lambda x: -x[1])[:3]
    sig_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid {BORDER};">'
        f'<span style="font-size:{FONT_VALUE};">📡</span>'
        f'<span style="font-size:{FONT_VALUE};color:{TEXT1};">{name}</span>'
        f'<span style="margin-left:auto;font-size:{FONT_LABEL};color:{TEXT2};">fired {cnt}× recently</span>'
        f'</div>'
        for name, cnt in top3
    ) or f'<div style="color:{TEXT2};font-size:{FONT_LABEL};padding:10px 0;">Building signal history.</div>'

    signals_box = (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin-top:8px;">'
        f'<div style="font-size:{FONT_LABEL};color:{TEXT2};text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;">Most Common Buy Signals</div>'
        f'{sig_rows}</div>'
    )

    last6 = sells.tail(6).iloc[::-1]
    result_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid {BORDER};">'
        f'<span style="font-size:{FONT_VALUE};">{"✅" if float(row.get("pnl_pct",0) or 0) > 0 else "❌"}</span>'
        f'<span style="font-family:Courier New,monospace;font-weight:700;color:{PRIMARY};font-size:{FONT_VALUE};">{row.get("symbol","")}</span>'
        f'<span style="font-size:{FONT_LABEL};color:{TEXT2};">{_SELL_REASON.get(str(row.get("action","")),"Exit")}</span>'
        f'<span style="margin-left:auto;font-weight:700;color:{"" + GAIN if float(row.get("pnl_pct",0) or 0) > 0 else LOSS};">'
        f'{float(row.get("pnl_pct",0) or 0):+.1%}</span>'
        f'</div>'
        for _, row in last6.iterrows()
    ) or f'<div style="color:{TEXT2};font-size:{FONT_LABEL};padding:10px 0;">No closed trades yet.</div>'

    results_box = (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin-top:8px;">'
        f'<div style="font-size:{FONT_LABEL};color:{TEXT2};text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;">Recent Trade Results</div>'
        f'{result_rows}</div>'
    )
    explain = (
        f'<div style="background:{BG};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin-top:8px;">'
        f'<div style="font-size:{FONT_LABEL};color:{TEXT2};line-height:1.7;">'
        f'<strong style="color:{TEXT1};">How TradeGenius AI works:</strong><br>'
        f'Three AI models vote on every trade: an <b>XGBoost</b> pattern engine trained on price history, '
        f'an <b>LSTM</b> that reads momentum, and a <b>FinBERT</b> model that reads financial news. '
        f'The AI only buys when all three agree <em>and</em> risk limits, market regime, and '
        f'position sizing rules all pass. Every position has an automatic stop-loss.'
        f'</div></div>'
    )
    return (f'<div class="nt nt-wrap">'
            f'{_section("🤖","AI Performance","investor summary")}'
            f'{cards}{signals_box}{results_box}{explain}</div>')
