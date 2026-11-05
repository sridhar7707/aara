"""Model validation, investor view, and institutional metrics.

Split across models_scorecard.py, models_validation.py,
models_institutional.py, and models_investor.py (ADR-079) — this file is a
re-export facade that preserves the public import surface
(dashboard.components.models) and the one-time component registration below,
which must run at import of this module.
"""
from __future__ import annotations

from dashboard.components.models_scorecard import render_paper_trading_scorecard
from dashboard.components.models_validation import render_validation_report, _lstm_loss_display
from dashboard.components.models_institutional import render_institutional_metrics
from dashboard.components.models_investor import render_investor_view, _model_quality_fallback

from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("investor_out",  RefreshGroup.FAST, render_investor_view,           priority=90))
register(ComponentSpec("scorecard_out", RefreshGroup.SLOW, render_paper_trading_scorecard, priority=60))
register(ComponentSpec("metrics_out",   RefreshGroup.SLOW, render_institutional_metrics,   priority=61))
register(ComponentSpec("val_out",       RefreshGroup.SLOW, render_validation_report,       priority=62))
