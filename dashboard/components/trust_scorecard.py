"""Phase 1B dashboard wiring for analytics/scorecard.py, compliance.py, and
calibration.py -- explicitly unfrozen ahead of Phase 1A's day-30 acceptance
gate (user decision, 2026-07-30; see CURRENT_ARCHITECTURE.md's Phase 1B
section for why frozen-phase code is running live).

Each render function reads the real Trust Ledger via the same
refresh_db_from_hf() + ledger.db.get_conn() pattern as
dashboard/components/decision_quality.py. The illustrative fallback in
render_calibration_buckets() lives here, not in analytics/calibration.py --
that module's queries stay real always; when real rows exist they render
automatically, no code change needed.
"""
from __future__ import annotations

from loguru import logger

from analytics.scorecard import generate_scorecard
from analytics.compliance import constitution_compliance_report
from analytics.calibration import (
    ConfidenceBucket, ModelAgreementBucket, DataQualityBucket,
    confidence_calibration, return_by_model_agreement, data_quality_impact,
)
from dashboard.design_system import (
    GAIN, LOSS, NEURAL, TEXT1, TEXT2,
    FONT_LABEL, WEIGHT_BOLD,
    _section, _card, _wrap, _stat_card, _illustrative_banner,
    th_style, td_style,
)
from dashboard.components._ledger_analytics import connect_ledger_or_none, rate_color, ret_color
from bot.core.error_logger import safe_render, timed

_logger = logger
_connect = connect_ledger_or_none


def _gate_badge(label: str, passed: bool, awaiting: bool = False) -> str:
    if awaiting:
        color, text = NEURAL, "AWAITING FIRST TRADE"
    else:
        color, text = (GAIN, "PASS") if passed else (LOSS, "FAIL")
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:10px 14px;border-bottom:1px solid #2d3445;">'
        f'<span style="font-size:{FONT_LABEL};color:{TEXT2};">{label}</span>'
        f'<span style="font-size:{FONT_LABEL};font-weight:{WEIGHT_BOLD};color:{color};">'
        f'{text}</span></div>'
    )


@timed(_logger)
@safe_render("Trust Scorecard")
def render_trust_scorecard() -> str:
    conn = _connect()
    if conn is None:
        return (f'<div class="nt nt-wrap">'
                f'{_section("🛡️", "Trust Scorecard", "")}'
                f'{_card("Trust Ledger unavailable.")}</div>')
    try:
        sc = generate_scorecard(conn)
    finally:
        conn.close()

    no_trades_yet = sc.evidence.decisions_collected == 0
    cards = (
        f'<div class="nt-cards">'
        + _stat_card("Decisions Collected", str(sc.evidence.decisions_collected), TEXT2, TEXT1, "EXECUTED decisions", 0.0)
        + _stat_card("Outcomes Recorded", str(sc.evidence.outcomes_recorded), TEXT2, TEXT1, "closed positions", 0.06)
        + _stat_card("Hash Chain Breaks", str(sc.evidence.hash_chain_broken_count), TEXT2,
                     GAIN if sc.evidence.hash_chain_broken_count == 0 else LOSS, "should always be 0", 0.12)
        + f'</div>'
    )
    # Gate 1/4 have no real "FAIL" state distinct from "no evidence yet" --
    # constitution_compliance_pass is False whenever total_checks==0 (0/0 pass
    # rate), and risk_controls_active is literally an EXISTS() check, so
    # False can only mean zero risk_evaluation_events, never a genuine
    # failure. Gate 3 (ledger integrity) is the one gate that's meaningfully
    # PASS on an empty ledger, so it's excluded from this treatment.
    gates_html = (
        _gate_badge("Constitution Compliance (Gate 1)", sc.gates.constitution_compliance_pass,
                    awaiting=sc.compliance.total_checks == 0)
        + _gate_badge("Reproducibility (Gate 2)", sc.gates.reproducibility_pass, awaiting=no_trades_yet)
        + _gate_badge("Ledger Integrity (Gate 3)", sc.gates.ledger_integrity_pass)
        + _gate_badge("Risk Controls Active (Gate 4)", sc.gates.risk_controls_active,
                      awaiting=not sc.gates.risk_controls_active)
    )
    overall = sc.all_governance_gates_pass and not no_trades_yet
    overall_html = (
        f'<div style="padding:10px 14px;font-size:{FONT_LABEL};color:{TEXT2};">'
        + (f'<span style="color:{NEURAL};font-weight:{WEIGHT_BOLD};">Evidence still accumulating</span> '
           f'-- {sc.evidence.decisions_collected} decisions so far, no trade executed yet.'
           if no_trades_yet else
           (f'<span style="color:{GAIN};font-weight:{WEIGHT_BOLD};">All governance gates pass.</span>'
            if overall else
            f'<span style="color:{LOSS};font-weight:{WEIGHT_BOLD};">One or more governance gates failing.</span>'))
        + f'</div>'
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🛡️", "Trust Scorecard", "Phase 1B evidence + governance gates")}'
        f'{cards}{_wrap(gates_html)}{overall_html}'
        f'</div>'
    )


@timed(_logger)
@safe_render("Constitution Compliance")
def render_constitution_compliance() -> str:
    conn = _connect()
    if conn is None:
        return (f'<div class="nt nt-wrap">'
                f'{_section("🏛️", "Constitution Compliance", "")}'
                f'{_card("Trust Ledger unavailable.")}</div>')
    try:
        report = constitution_compliance_report(conn)
    finally:
        conn.close()

    if report.total_checks == 0:
        return (f'<div class="nt nt-wrap">'
                f'{_section("🏛️", "Constitution Compliance", "")}'
                f'{_card("No constitution checks recorded yet.")}</div>')

    rows_html = ""
    for r in report.by_rule:
        rate_color = GAIN if r.pass_rate >= 0.95 else (LOSS if r.pass_rate < 0.80 else NEURAL)
        rows_html += (
            f'<tr>'
            f'<td {td_style()}>{r.rule_id}</td>'
            f'<td {td_style(nowrap=False)}>{r.rule_name}</td>'
            f'<td {td_style("text-align:right;")}>{r.total_checks}</td>'
            f'<td {td_style(f"text-align:right;color:{GAIN};")}>{r.pass_count}</td>'
            f'<td {td_style(f"text-align:right;color:{LOSS};")}>{r.fail_count}</td>'
            f'<td {td_style(f"text-align:right;color:{NEURAL};")}>{r.escalated_count}</td>'
            f'<td {td_style(f"text-align:right;font-weight:{WEIGHT_BOLD};color:{rate_color};")}>{r.pass_rate:.0%}</td>'
            f'</tr>'
        )
    headers = ["Rule", "Name", "Checks", "Pass", "Fail", "Escalated", "Pass Rate"]
    th_cells = "".join(f'<th {th_style()}>{h}</th>' for h in headers)
    table = (
        f'<table style="width:100%;border-collapse:collapse;font-family:Inter,system-ui,sans-serif;">'
        f'<thead><tr>{th_cells}</tr></thead><tbody>{rows_html}</tbody></table>'
    )
    note = f"{report.total_decisions} decisions, {report.overall_pass_rate:.0%} overall pass rate"
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("🏛️", "Constitution Compliance", note)}'
        f'{_wrap(table)}'
        f'</div>'
    )


_rate_color = rate_color
_ret_color = ret_color


def _table_html(headers: list[str], rows_html: str) -> str:
    th_cells = "".join(f'<th {th_style()}>{h}</th>' for h in headers)
    return (
        f'<table style="width:100%;border-collapse:collapse;font-family:Inter,system-ui,sans-serif;">'
        f'<thead><tr>{th_cells}</tr></thead><tbody>{rows_html}</tbody></table>'
    )


def _confidence_row(b) -> str:
    return (f'<tr><td {td_style()}>{b.label}</td>'
            f'<td {td_style("text-align:right;")}>{b.decisions}</td>'
            f'<td {td_style(f"text-align:right;color:{_rate_color(b.win_rate)};")}>{b.win_rate:.0%}</td>'
            f'<td {td_style(f"text-align:right;color:{_ret_color(b.avg_return)};")}>{b.avg_return:+.1%}</td></tr>')


def _agreement_row(b) -> str:
    return (f'<tr><td {td_style(nowrap=False)}>{b.label}</td>'
            f'<td {td_style("text-align:right;")}>{b.decisions}</td>'
            f'<td {td_style(f"text-align:right;color:{_ret_color(b.avg_return)};")}>{b.avg_return:+.1%}</td></tr>')


def _quality_row(b) -> str:
    return (f'<tr><td {td_style()}>{b.status}</td>'
            f'<td {td_style("text-align:right;")}>{b.decisions}</td>'
            f'<td {td_style(f"text-align:right;color:{_rate_color(b.win_rate)};")}>{b.win_rate:.0%}</td>'
            f'<td {td_style(f"text-align:right;color:{_ret_color(b.avg_return)};")}>{b.avg_return:+.1%}</td></tr>')


# Illustrative examples reuse the real dataclasses so row rendering is
# identical between the real and mock paths -- only the data source differs.
_ILLUSTRATIVE_CONFIDENCE = [
    ConfidenceBucket("0.5-0.7", 8, 0.50, -0.004),
    ConfidenceBucket("0.7-0.9", 14, 0.64, 0.018),
    ConfidenceBucket(">0.9", 5, 0.80, 0.031),
]
_ILLUSTRATIVE_AGREEMENT = [
    ModelAgreementBucket("XGBoost + LSTM + FinBERT agree", 9, 0.024),
    ModelAgreementBucket("2 of 3 agree", 15, 0.006),
    ModelAgreementBucket("Disagreement (tie/mixed)", 3, -0.011),
]
_ILLUSTRATIVE_DATA_QUALITY = [
    DataQualityBucket("COMPLETE", 22, 0.68, 0.021),
    DataQualityBucket("DEGRADED", 5, 0.40, -0.009),
]


def _calibration_section(title: str, headers: list[str], real_rows: list, illustrative_rows: list, row_fn) -> str:
    is_real = bool(real_rows)
    rows_html = "".join(row_fn(r) for r in (real_rows if is_real else illustrative_rows))
    banner = "" if is_real else _illustrative_banner(
        "no closed decisions yet -- this is what the real table will look like."
    )
    title_html = (f'<div style="font-size:{FONT_LABEL};color:{TEXT2};font-weight:{WEIGHT_BOLD};'
                  f'text-transform:uppercase;letter-spacing:.5px;margin:14px 0 6px;">{title}</div>')
    return title_html + banner + _wrap(_table_html(headers, rows_html))


@timed(_logger)
@safe_render("Trust Ledger Calibration")
def render_calibration_buckets() -> str:
    conn = _connect()
    if conn is None:
        return (f'<div class="nt nt-wrap">'
                f'{_section("📐", "Trust Ledger Calibration", "Phase 1B preview")}'
                f'{_card("Trust Ledger unavailable.")}</div>')
    try:
        confidence = confidence_calibration(conn)
        agreement = return_by_model_agreement(conn)
        data_quality = data_quality_impact(conn)
    finally:
        conn.close()

    body = (
        _calibration_section("Win rate by confidence bucket",
                              ["Confidence", "Decisions", "Win Rate", "Avg Return"],
                              confidence, _ILLUSTRATIVE_CONFIDENCE, _confidence_row)
        + _calibration_section("Return by model agreement",
                                ["Models Agreeing", "Decisions", "Avg Return"],
                                agreement, _ILLUSTRATIVE_AGREEMENT, _agreement_row)
        + _calibration_section("Return by data completeness",
                                ["Data Quality", "Decisions", "Win Rate", "Avg Return"],
                                data_quality, _ILLUSTRATIVE_DATA_QUALITY, _quality_row)
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("📐", "Trust Ledger Calibration", "Does confidence actually predict outcomes? -- Phase 1B")}'
        f'{body}'
        f'</div>'
    )


from dashboard.registry import ComponentSpec, RefreshGroup, register
register(ComponentSpec("trust_scorecard_out", RefreshGroup.SLOW, render_trust_scorecard, priority=41))
register(ComponentSpec("constitution_compliance_out", RefreshGroup.SLOW, render_constitution_compliance, priority=42))
register(ComponentSpec("calibration_buckets_out", RefreshGroup.SLOW, render_calibration_buckets, priority=43))
