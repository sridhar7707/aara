# ================================================================
# UI CHANGE TRACKING
# After making ANY change to this file run:
#   python tests/ui_changelog.py
# This updates docs/UI_CHANGELOG.md automatically.
# Do not skip this step.
# ================================================================
# ================================================================
# REQUIREMENTS TRACKING
# After making ANY change to this file run:
#   python tests/requirements_tracker.py
# This updates docs/REQUIREMENTS.md automatically.
# ================================================================
"""Gradio dashboard &mdash; TradeGenius AI, hosted on HuggingFace Spaces."""
from __future__ import annotations

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import gradio as gr
from loguru import logger

# ── Design system ─────────────────────────────────────────────────────────────
from dashboard.design_system import (
    BG, SURFACE, SURFACE2, BORDER, TEXT1, TEXT2, TEXT3,
    ACTION_BUY, ACTION_SELL, ACTION_TRIM, ACTION_HOLD, ACTION_WATCH,
    ACTION_BUY_BG, ACTION_SELL_BG, ACTION_TRIM_BG,
    ACTION_HOLD_BG, ACTION_WATCH_BG, ACTION_ADD_BG, ACTION_EXIT_BG,
    PRIMARY, GAIN, LOSS, NEURAL,
    PRIMARY_BG, GAIN_BG, LOSS_BG, NEURAL_BG,
    GAIN_BD, LOSS_BD, NEURAL_BD, ACTION_ADD, ACTION_EXIT,
    FONT_HERO, FONT_SECTION, FONT_VALUE, FONT_LABEL,
    WEIGHT_BOLD, WEIGHT_MEDIUM, WEIGHT_NORMAL,
    CARD_PADDING, CARD_RADIUS, ROW_PADDING, SECTION_GAP, INNER_GAP,
    SYMBOL_STYLE, PLOTLY_LAYOUT,
    _pnl_color, _card, _label, _hero_value, _section_title, _action_badge,
    _symbol, _confidence_bar, _metric_row, _progress_bar, _divider,
    _empty_state, _action_row, _table,
    _sym, _badge, _num, _pnl, _section, _wrap, _stat_card,
    TH, TD, TD0,
)
from dashboard.layout import GRADIO_CSS, STYLES, LOGO, HEADER_HTML, FOOTER_HTML, TAB_FIX_JS
from dashboard.data import (
    get_data, DB_PATH, HF_TOKEN, HF_REPO_ID,
    _now_ct, _to_ct, _market_status,
)
from dashboard.charts import _get_sym_hist, _sym_perf, _sparkline, _FI_LABELS
from dashboard.components.overview import (
    render_portfolio_health_hero,
    render_trade_frequency, render_spy_banner,
)
from dashboard.components.ai_panel import render_ai_recommendation, render_ai_committee, _WHY_MAP
from dashboard.components.risk import render_risk_panel, render_market_intelligence, _risk_level, _SECTOR_MAP
from dashboard.components.portfolio import render_positions, render_trades
from dashboard.components.models import (
    render_validation_report, render_investor_view, render_paper_trading_scorecard,
)
from dashboard.components.signals import render_watchlist, render_timeline
from dashboard.components.history import render_whats_changed, render_portfolio_performance, perf_choices
from dashboard.components.recommendation_history import (
    render_recommendation_history, render_buy_candidates, render_top_picks,
)
from dashboard.components.news import render_news_feed
from dashboard.components.signal_history import render_signal_history
from dashboard.components.decision import render_decision_center
from dashboard.components.rebalance import render_rebalance
from dashboard.components.symbol_detail import render_symbol_detail, _get_symbol_choices
from dashboard.components.settings import render_settings_summary, render_investor_profile, do_save_settings
from dashboard.components.brief import render_morning_brief, render_scheduler_status, render_three_question_summary
from dashboard.components.thesis import render_thesis_tracker
from dashboard.components.weekly_summary import render_weekly_summary
from dashboard.components.simulator import render_portfolio_simulator
from dashboard.components.timeline import render_all_timelines
from dashboard.components.decision_bar import render_decision_bar
from dashboard.components.capital import (
    render_capital_overview,
    render_profit_breakdown, render_managed_capital, save_reinvestment_mode,
    do_pool_deposit, do_pool_withdraw, do_set_reserve, _load_pool,
)
from dashboard.components.attribution import (
    render_attribution_by_symbol, render_attribution_by_sector,
    render_attribution_by_model, render_attribution_by_trade,
    render_confidence_calibration, render_exit_attribution,
)
from dashboard.components.trade_journal import render_trade_journal
from dashboard.components.loss_explanation import render_loss_explanation
from dashboard.components.pending_approvals import (
    render_pending_approvals, on_approve_click, on_reject_click,
)
from dashboard.components.phase2_preview import render_improvement_proposals
from dashboard.timers import register_all_timers
from dashboard.prerender import prerender_all
import dashboard.registry as registry
from database.user_settings import get_all_settings, get_setting
from bot.core.error_logger import safe_render, timed
from bot.core.recommendation_engine import (
    get_portfolio_action, get_position_sizing,
    get_sell_analysis, get_recommendation_explanation, get_portfolio_health,
)

_logger = logger

_theme = gr.themes.Base(
    primary_hue=gr.themes.colors.green,
    neutral_hue=gr.themes.colors.slate,
).set(
    body_background_fill="#0f1115",
    body_text_color="#ffffff",
    block_background_fill="#171a21",
    block_border_color="#2d3445",
    block_radius="12px",
    button_primary_background_fill="#00c853",
    button_primary_text_color="#000000",
    button_secondary_background_fill="#222733",
    button_secondary_text_color="#ffffff",
    border_color_primary="#2d3445",
)

# ── Pre-render all components concurrently at startup ─────────────────────────
# gr.Plot ignores value=callable in Gradio 5.9 and demo.load() events do not
# fire reliably, so we render everything upfront and pass static values.
# market_mood has a 20 s yfinance timeout; its prewarm thread starts at import
# so by the time this block runs it already has a head start. Extracted to
# dashboard/prerender.py (kept app.py under the 500-line limit).
_ci = prerender_all()

with gr.Blocks(title="TradeGenius AI", theme=_theme, css=GRADIO_CSS, js=TAB_FIX_JS) as _demo:
    gr.HTML(HEADER_HTML)
    with gr.Tabs():
        # ── Tab 1: Brief (5-card end-user view) ──────────────────────────────
        with gr.TabItem("📋 Brief"):
            exec_summary_out     = registry.mount("exec_summary_out",     gr.HTML(value=_ci["exec_summary"], show_label=False))
            decision_bar_out     = registry.mount("decision_bar_out",     gr.HTML(value=render_decision_bar, show_label=False))
            scheduler_status_out = registry.mount("scheduler_status_out", gr.HTML(value=render_scheduler_status, show_label=False))
            morning_brief_out    = registry.mount("morning_brief_out",    gr.HTML(value=render_morning_brief, show_label=False))
            pos_brief_out        = registry.mount("pos_brief_out",        gr.HTML(value=render_positions, show_label=False))

        # ── Tab 2: Portfolio (6-block end-user view) ─────────────────────────
        with gr.TabItem("💼 Portfolio"):
            weekly_summary_out  = registry.mount("weekly_summary_out",  gr.HTML(value=render_weekly_summary))
            hero_out            = registry.mount("hero_out",            gr.HTML(value=render_portfolio_health_hero))
            _init_choices = perf_choices()
            _init_sel = next((c for c in _init_choices if "—" not in c), _init_choices[2] if len(_init_choices) > 2 else _init_choices[0])
            perf_tabs  = registry.mount("perf_tabs", gr.Radio(
                choices=_init_choices, value=_init_sel,
                label="", container=False, elem_classes=["perf-tabs"],
            ))
            perf_out   = registry.mount("perf_out", gr.HTML(value=render_portfolio_performance(_init_sel)))
            eq_plot    = registry.mount("eq_plot",  gr.Plot(value=_ci["equity"], label="", show_label=False, elem_id="equity-chart"))
            pos_out    = registry.mount("pos_out",  gr.HTML(value=render_positions))
            trades_out = registry.mount("trades_out", gr.HTML(value=render_trades))

        # ── Tab 3: Analytics (deep-dive — one tap from Brief / Portfolio) ─────
        # Secondary/drill-down sections live in collapsed accordions so the
        # tab isn't ~6000px of unconditional scroll — nothing removed, just
        # progressive disclosure. Keep only the most glanceable, highest-
        # value sections unconditionally visible at the top.
        with gr.TabItem("🔍 Analytics"):
            spy_banner_out      = registry.mount("spy_banner_out",      gr.HTML(value=""))
            with gr.Row():
                with gr.Column(scale=6):
                    alloc_plot = registry.mount("alloc_plot", gr.Plot(value=_ci["alloc"], label="", show_label=False))
                with gr.Column(scale=4):
                    pnl_plot   = registry.mount("pnl_plot",  gr.Plot(value=_ci["pnl"],   label="", show_label=False))
            ai_rec_brief_out   = registry.mount("ai_rec_brief_out",   gr.HTML(value=render_ai_recommendation))
            watchlist_out       = registry.mount("watchlist_out",       gr.HTML(value=render_watchlist))
            _initial_choices = _get_symbol_choices()
            _initial_sym     = _initial_choices[0] if _initial_choices else None
            symbol_selector  = registry.mount("symbol_selector", gr.Dropdown(
                choices=_initial_choices, label="🔍 Symbol Detail",
                value=_initial_sym, container=True, elem_classes=["sym-selector"],
            ))
            symbol_detail_out = registry.mount("symbol_detail_out", gr.HTML(value=render_symbol_detail(_initial_sym) if _initial_sym else ""))

            with gr.Accordion("🗳️ AI Committee", open=False):
                committee_out       = registry.mount("committee_out",       gr.HTML(value=""))
            with gr.Accordion("✅ Decision Center", open=False):
                decision_center_out = registry.mount("decision_center_out", gr.HTML(value=""))
            with gr.Accordion("⏳ Pending Approvals", open=False):
                pending_approvals_out = registry.mount("pending_approvals_out", gr.HTML(value=render_pending_approvals))
                with gr.Row():
                    _approval_id_in = gr.Number(label="Decision ID", precision=0, container=True)
                    _approve_btn = gr.Button("Approve", variant="primary")
                    _reject_btn  = gr.Button("Reject", variant="secondary")
                _reject_reason_in    = gr.Textbox(label="Rejection reason (optional)", container=True)
                _approval_status_out = gr.HTML(value="")
            with gr.Accordion("⚖️ Rebalance", open=False):
                rebalance_out       = registry.mount("rebalance_out",       gr.HTML(value=""))
            with gr.Accordion("📝 Thesis Tracker", open=False):
                thesis_out          = registry.mount("thesis_out",          gr.HTML(value=""))
            with gr.Accordion("🔬 Simulate a Trade", open=False):
                _sim_syms  = sorted(get_data().get("prices", {}).keys()) or []
                sim_sym_dd = registry.mount("sim_sym_dd", gr.Dropdown(choices=_sim_syms, label="Symbol", container=True))
                sim_amt_sl = gr.Slider(minimum=100, maximum=10000, value=500, step=100,
                                       label="Amount ($)", container=True)
                simulator_out = gr.HTML(value="")
            with gr.Accordion("📅 Since Yesterday", open=False):
                whats_changed_out  = registry.mount("whats_changed_out",  gr.HTML(value=render_whats_changed))
            with gr.Accordion("🌡️ Market Mood", open=False):
                market_mood_out    = registry.mount("market_mood_out",    gr.HTML(value=_ci["market_mood"]))
            with gr.Accordion("🛡️ Risk Controls", open=False):
                risk_panel_out     = registry.mount("risk_panel_out",     gr.HTML(value=render_risk_panel))
            with gr.Accordion("📡 Market Intelligence", open=False):
                mkt_intel_out      = registry.mount("mkt_intel_out",      gr.HTML(value=render_market_intelligence))
            with gr.Accordion("📰 Market News", open=False):
                news_out           = registry.mount("news_out",           gr.HTML(value=_ci["news"]))
            with gr.Accordion("🕐 Decision Timeline", open=False):
                timeline_brief_out = registry.mount("timeline_brief_out", gr.HTML(value=render_all_timelines))
            with gr.Accordion("🌡️ Regime Performance (Phase 2 preview)", open=False):
                regime_performance_out = registry.mount(
                    "regime_performance_out", gr.HTML(value=_ci["regime_performance"])
                )
            with gr.Accordion("📋 Improvement Proposals (Phase 2 preview)", open=False):
                improvement_proposals_out = registry.mount(
                    "improvement_proposals_out", gr.HTML(value=render_improvement_proposals)
                )

        # ── Tab 4: Capital ────────────────────────────────────────────────────
        with gr.TabItem("💰 Capital"):
            capital_overview_out  = registry.mount("capital_overview_out",  gr.HTML(value=render_capital_overview))
            with gr.Row():
                with gr.Column(scale=1):
                    managed_capital_out = registry.mount("managed_capital_out", gr.HTML(value=render_managed_capital))
                with gr.Column(scale=1):
                    capital_health_out  = registry.mount("capital_health_out",  gr.HTML(value=_ci["cap_health"]))
            capital_chart_out     = registry.mount("capital_chart_out",     gr.Plot(value=_ci["capital"], label="Capital Growth", show_label=False))
            profit_breakdown_out  = registry.mount("profit_breakdown_out",  gr.HTML(value=render_profit_breakdown))
            capital_ledger_out    = registry.mount("capital_ledger_out",    gr.HTML(value=_ci["cap_ledger"]))
            # ── Profit Handling ────────────────────────────────────────────
            _cur_reinvest = get_setting("reinvest_profits_only", "false")
            reinvest_radio = gr.Radio(
                choices=[
                    "Auto Reinvest ON — profits grow managed capital",
                    "Auto Reinvest OFF — profits shown as withdrawable",
                ],
                value=(
                    "Auto Reinvest OFF — profits shown as withdrawable"
                    if _cur_reinvest == "true"
                    else "Auto Reinvest ON — profits grow managed capital"
                ),
                label="Profit Handling",
            )
            reinvest_status = gr.HTML(value="")
            # ── Capital Actions ────────────────────────────────────────────
            with gr.Row():
                with gr.Column(scale=1):
                    _deposit_amt = gr.Number(label="Deposit Amount ($)", minimum=1, precision=2)
                    _deposit_btn = gr.Button("Deposit", variant="primary")
                    _deposit_status = gr.HTML(value="")
                with gr.Column(scale=1):
                    _withdraw_amt = gr.Number(label="Withdraw Amount ($)", minimum=1, precision=2)
                    _withdraw_btn = gr.Button("Withdraw", variant="secondary")
                    _withdraw_status = gr.HTML(value="")
                with gr.Column(scale=1):
                    try:
                        _pool_init = _load_pool()
                        _reserve_default = _pool_init.reserve if _pool_init else 100.0
                    except Exception:
                        _reserve_default = 100.0
                    _reserve_amt = gr.Number(label="Set Reserve ($)", minimum=0, precision=2,
                                             value=_reserve_default)
                    _reserve_btn = gr.Button("Set Reserve", variant="secondary")
                    _reserve_status = gr.HTML(value="")

        # ── Tab 5: Trades ─────────────────────────────────────────────────────
        with gr.TabItem("📈 Trades"):
            top_picks_out       = registry.mount("top_picks_out",       gr.HTML(value=render_top_picks))
            trade_freq_out      = registry.mount("trade_freq_out",      gr.HTML(value=render_trade_frequency))
            buy_candidates_out  = registry.mount("buy_candidates_out",  gr.HTML(value=render_buy_candidates))
            signal_history_out  = registry.mount("signal_history_out",  gr.HTML(value=render_signal_history))
            rec_history_out     = registry.mount("rec_history_out",     gr.HTML(value=render_recommendation_history))
            timeline_trades_out = registry.mount("timeline_trades_out", gr.HTML(value=render_timeline))

        # ── Tab 6: Performance ────────────────────────────────────────────────
        with gr.TabItem("📊 Performance"):
            decision_quality_out = registry.mount(
                "decision_quality_out", gr.HTML(value=_ci["decision_quality"])
            )
            counterfactual_out = registry.mount(
                "counterfactual_out", gr.HTML(value=_ci["counterfactual"])
            )
            trust_scorecard_out = registry.mount(
                "trust_scorecard_out", gr.HTML(value=_ci["trust_scorecard"])
            )
            constitution_compliance_out = registry.mount(
                "constitution_compliance_out", gr.HTML(value=_ci["constitution_compliance"])
            )
            calibration_buckets_out = registry.mount(
                "calibration_buckets_out", gr.HTML(value=_ci["calibration_buckets"])
            )
            scorecard_out = registry.mount(
                "scorecard_out", gr.HTML(value=_ci["paper_trading_scorecard"])
            )
            metrics_out   = registry.mount("metrics_out",   gr.HTML(value=_ci["metrics"]))
            # Full width, stacked — both tables grew a "vs SPY" column and no longer
            # fit two-up without truncating dollar amounts with an ellipsis.
            attribution_symbol_out = registry.mount("attribution_symbol_out", gr.HTML(value=render_attribution_by_symbol))
            attribution_sector_out = registry.mount("attribution_sector_out", gr.HTML(value=render_attribution_by_sector))
            with gr.Row():
                attribution_model_out = registry.mount("attribution_model_out", gr.HTML(value=render_attribution_by_model))
                attribution_trade_out = registry.mount("attribution_trade_out", gr.HTML(value=render_attribution_by_trade))
            exit_attribution_out = registry.mount("exit_attribution_out", gr.HTML(value=render_exit_attribution))
            confidence_calibration_out = registry.mount(
                "confidence_calibration_out", gr.HTML(value=render_confidence_calibration)
            )
            with gr.Row():
                returns_hist_plot = registry.mount("returns_hist_plot", gr.Plot(value=_ci["ret_hist"], label="", show_label=False))
                winloss_plot      = registry.mount("winloss_plot",      gr.Plot(value=_ci["winloss"],  label="", show_label=False))
            model_view = gr.Radio(
                choices=["📊 Investor View", "🔬 Developer View"],
                value="📊 Investor View", label="", container=False,
            )
            investor_out = registry.mount("investor_out", gr.HTML(value=render_investor_view, visible=True))
            with gr.Column(visible=False) as dev_col:
                with gr.Row():
                    with gr.Column(scale=65):
                        fi_plot = registry.mount("fi_plot", gr.Plot(value=_ci["fi"], label="", show_label=False))
                    with gr.Column(scale=35):
                        val_out = registry.mount("val_out", gr.HTML(value=""))

        # ── Tab 7: Trade Journal ──────────────────────────────────────────────
        with gr.TabItem("📓 Journal"):
            trade_journal_out = registry.mount(
                "trade_journal_out", gr.HTML(value=render_trade_journal)
            )
            loss_explanation_out = registry.mount(
                "loss_explanation_out", gr.HTML(value=render_loss_explanation)
            )

        # ── Tab 8: Settings ───────────────────────────────────────────────────
        with gr.TabItem("⚙️ Settings"):
            _s0 = get_all_settings()
            def _pct(key: str, default: str) -> float:
                try:
                    return round(float(_s0.get(key, default)) * 100, 1)
                except (ValueError, TypeError):
                    return float(default) * 100
            with gr.Row():
                with gr.Column(scale=1):
                    _risk_radio = gr.Radio(
                        choices=["Conservative", "Moderate", "Aggressive"],
                        value=_s0.get("risk_tolerance", "Moderate"), label="Risk Tolerance",
                    )
                    _bench_radio = gr.Radio(
                        choices=["SPY", "QQQ", "DIA"],
                        value=_s0.get("benchmark", "SPY"), label="Benchmark",
                    )
                    _max_pos_sl = gr.Slider(minimum=5, maximum=50, step=1,
                                            value=_pct("max_position_pct", "0.20"),
                                            label="Max Position Size %")
                    _max_dd_sl  = gr.Slider(minimum=5, maximum=30, step=1,
                                            value=_pct("max_drawdown_pct", "0.12"),
                                            label="Max Drawdown Threshold %")
                    _stop_sl    = gr.Slider(minimum=1, maximum=15, step=0.5,
                                            value=_pct("stop_loss_pct", "0.04"),
                                            label="Stop-Loss Default %")
                    _notif_check = gr.Checkbox(
                        value=_s0.get("notifications_enabled", "false") == "true",
                        label="Enable Notifications",
                    )
                    _save_btn    = gr.Button("💾 Save Settings", variant="primary")
                    _save_status = gr.HTML(value="")
                with gr.Column(scale=1):
                    settings_summary_out = registry.mount("settings_summary_out", gr.HTML(value=render_settings_summary))
            investor_profile_out = registry.mount("investor_profile_out", gr.HTML(value=render_investor_profile))

    gr.HTML(value=FOOTER_HTML)

    # ── Event handlers ────────────────────────────────────────────────────────
    def _on_model_view_change(v, *_):
        return (gr.update(visible=(v == "📊 Investor View")),
                gr.update(visible=(v == "🔬 Developer View")))

    model_view.change(fn=_on_model_view_change, inputs=[model_view], outputs=[investor_out, dev_col])

    # perf_out (gr.HTML) updates server-side on radio change.
    # eq_plot (gr.Plot) updates client-side via Plotly.relayout() in TAB_FIX_JS —
    # Gradio 5.9 "Too many arguments" prevents gr.Plot in .change() outputs when
    # inputs are also declared, so the chart period filter runs in the browser.
    perf_tabs.change(fn=render_portfolio_performance, inputs=[perf_tabs], outputs=[perf_out])
    symbol_selector.change(fn=render_symbol_detail, inputs=[symbol_selector], outputs=[symbol_detail_out])

    def _run_sim(sym, amt):
        return render_portfolio_simulator(sym, float(amt) if amt else 500.0)
    sim_sym_dd.change(fn=_run_sim, inputs=[sim_sym_dd, sim_amt_sl], outputs=simulator_out)
    sim_amt_sl.change(fn=_run_sim, inputs=[sim_sym_dd, sim_amt_sl], outputs=simulator_out)

    reinvest_radio.change(fn=save_reinvestment_mode, inputs=[reinvest_radio],
                          outputs=[reinvest_status])

    def _cap_action(fn, v, default=""):
        return fn(str(v) if v is not None else default), render_managed_capital()

    _deposit_btn.click(fn=lambda v: _cap_action(do_pool_deposit, v), inputs=[_deposit_amt], outputs=[_deposit_status, managed_capital_out])
    _withdraw_btn.click(fn=lambda v: _cap_action(do_pool_withdraw, v), inputs=[_withdraw_amt], outputs=[_withdraw_status, managed_capital_out])
    _reserve_btn.click(fn=lambda v: _cap_action(do_set_reserve, v, "0"), inputs=[_reserve_amt], outputs=[_reserve_status, managed_capital_out])

    _approve_btn.click(fn=on_approve_click, inputs=[_approval_id_in],
                      outputs=[_approval_status_out, pending_approvals_out])
    _reject_btn.click(fn=on_reject_click, inputs=[_approval_id_in, _reject_reason_in],
                      outputs=[_approval_status_out, pending_approvals_out])

    _save_btn.click(
        fn=do_save_settings,
        inputs=[_risk_radio, _bench_radio, _max_pos_sl, _max_dd_sl, _stop_sl, _notif_check],
        outputs=[settings_summary_out, _save_status],
    )

    # All components are pre-rendered at startup via _ci — no demo.load() needed.

    # ── Timer registration ────────────────────────────────────────────────────
    timer_ui   = gr.Timer(value=60)    # 1 min — DB reads only, no yfinance; fast on HF free tier
    timer_data = gr.Timer(value=300)   # 5 min — yfinance (15 s timeout), charts, AI, news
    registry.validate()                # catch any spec registered but never mounted
    register_all_timers(timer_ui, timer_data)


from dashboard.http_endpoints import build_app
app = build_app(_demo)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
