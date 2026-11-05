"""Model Validation Report (split from models.py, ADR-079)."""
from __future__ import annotations
import os
from dashboard.design_system import (
    BG, SURFACE, BORDER, TEXT1, TEXT2,
    GAIN, LOSS, NEURAL,
    FONT_LABEL,
    _section, _wrap,
)
from bot.core.error_logger import safe_render


def _lstm_loss_display(r: dict, retired_text: str) -> tuple:
    val_loss = r.get("lstm_val_loss", 1.0)
    return (TEXT2, retired_text) if r.get("lstm_retired") else (
        GAIN if val_loss < 0.65 else (NEURAL if val_loss < 0.70 else LOSS), f"{val_loss:.4f}")

@safe_render("Validation Report")
def render_validation_report() -> str:
    import json as _json
    vr_path = "models/validation_report.json"
    if not os.path.exists(vr_path):
        msg = (f'<div style="color:{TEXT2};text-align:center;padding:28px;font-size:{FONT_LABEL};">'
               f'No validation report yet.<br>Run: python scripts/train_model.py</div>')
        return f'<div class="nt nt-wrap">{_section("🔬", "Model Validation")}{_wrap(msg)}</div>'
    try:
        with open(vr_path) as fh:
            r = _json.load(fh)
    except Exception as exc:
        return (f'<div class="nt nt-wrap">{_section("🔬", "Model Validation")}'
                f'<span style="color:{LOSS}">{exc}</span></div>')

    auc      = r.get("xgb_val_auc",  0.0)
    auc_c    = GAIN if auc >= 0.60 else (NEURAL if auc >= 0.55 else LOSS)
    loss_c, loss_val = _lstm_loss_display(r, "Retired (ADR-077)")
    dr       = r.get("date_range", {})

    def _vr(label: str, val: str, color: str = TEXT1) -> str:
        return (
            f'<tr>'
            f'<td style="padding:9px 14px;border-bottom:1px solid {BORDER};background:{SURFACE};'
            f'color:{TEXT2} !important;font-size:{FONT_LABEL};font-weight:600;">{label}</td>'
            f'<td style="padding:9px 14px;border-bottom:1px solid {BORDER};background:{SURFACE};'
            f'font-family:-apple-system,monospace;color:{color} !important;font-weight:700;">{val}</td>'
            f'</tr>'
        )

    rows = (
        _vr("XGBoost Val AUC", f"{auc:.3f}",                    auc_c)
        + _vr("LSTM Val Loss",loss_val,                        loss_c)
        + _vr("Train Rows",   f"{r.get('training_rows',0):,}")
        + _vr("Symbols",      str(r.get("training_symbols","&mdash;")))
        + _vr("Cutoff",       r.get("train_cutoff", "&mdash;"))
        + _vr("Data From",    dr.get("from", "&mdash;"))
        + _vr("Data To",      dr.get("to",   "&mdash;"))
        + _vr("Generated",    r.get("generated_at","")[:10])
    )
    help_html = (
        f'<div style="background:{BG};border-top:1px solid {BORDER};'
        f'padding:10px 14px;font-size:{FONT_LABEL};color:{TEXT2};line-height:1.6;">'
        f'<strong style="color:{TEXT1};">How to read this:</strong><br>'
        f'<b>XGBoost Val AUC</b> &mdash; How well XGBoost predicts the right direction on data it '
        f'<em>never trained on</em>. 0.50 = random guessing. 0.60+ = meaningfully predictive. '
        f'1.0 = perfect (never achieved in practice).<br>'
        f'<b>LSTM Val Loss</b> &mdash; Prediction error on unseen data (shows "Retired" if the model was '
        f'intentionally removed from training, ADR-077). A well-trained model scores below 0.65.<br>'
        f'<b>Train Cutoff</b> &mdash; All data <em>after</em> this date was held out during training '
        f'to test real-world performance.'
        f'</div>'
    )
    table = _wrap(f'<table class="nt-tbl" style="width:100%">{rows}</table>' + help_html)
    note = (f'<div style="font-size:{FONT_LABEL};color:{TEXT2};padding:2px 0 6px;">'
            f'AUC ≥ 0.60 = good · ≥ 0.55 = acceptable · &lt; 0.52 = near-random</div>')
    return f'<div class="nt nt-wrap">{_section("🔬", "Model Validation")}{note}{table}</div>'
