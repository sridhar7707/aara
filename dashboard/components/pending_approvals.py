"""Pending Approvals — Decision Intelligence Phase 4, Step 9.

The SUPERVISED per-trade approval workflow this queue served was fully
retired per phase0_decisions.md #17/#18 — Phase 1A has no per-trade human
approval workflow at all, and nothing writes to decision_log anymore.
Kept as a permanent no-op (decision #18: no action needed) rather than
removed, since a future live-capital DEFENSIVE-state approval queue is a
deliberate, deferred design (CURRENT_ARCHITECTURE.md's "Deferred, Not
Forgotten") that would be a *new* append-only table, not a revival of this
one. This component will never show a pending row again.
"""
from __future__ import annotations

from loguru import logger

from bot.core.error_logger import safe_render, timed
from dashboard.data import get_db_conn
from dashboard.design_system import (
    GAIN, LOSS, TEXT1, TEXT2, TEXT3,
    FONT_VALUE, WEIGHT_BOLD,
    td_style, th_style, _section, _empty_state, _card, _wrap,
)
from dashboard.registry import ComponentSpec, RefreshGroup, register

_logger = logger


def _read_pending() -> list[dict]:
    from database.services.decision_service import list_pending_approvals
    try:
        with get_db_conn() as con:
            return list_pending_approvals(con)
    except Exception as exc:
        _logger.warning(f"pending_approvals read: {exc}")
        return []


@timed(_logger)
@safe_render("Pending Approvals")
def render_pending_approvals() -> str:
    rows = _read_pending()
    if not rows:
        return (
            f'<div class="nt nt-wrap">'
            f'{_section("⏳", "Pending Approvals", "")}'
            f'{_card(_empty_state("⏳", "No decisions awaiting approval", "Per-trade approval is retired for Phase 1A — this queue will not populate."))}'
            f'</div>'
        )

    n = len(rows)
    rows_html = ""
    for i, r in enumerate(rows):
        border = i < n - 1
        conf = r.get("ai_confidence")
        conf_s = f"{conf}%" if conf is not None else "—"
        notional = r.get("suggested_notional")
        notional_s = f"${notional:,.2f}" if notional else "—"
        reason = r.get("decision_reason") or "—"
        date_s = str(r.get("created_at") or "")[:16].replace("T", " ")
        rows_html += (
            f"<tr>"
            f"<td {td_style('font-weight:'+WEIGHT_BOLD+';', border=border)}>{r['decision_id']}</td>"
            f"<td {td_style('font-weight:'+WEIGHT_BOLD+';color:'+TEXT1+' !important;', border=border)}>{r['symbol']}</td>"
            f"<td {td_style('', border=border)}>{conf_s}</td>"
            f"<td {td_style('text-align:right;font-family:Courier New,monospace;', border=border)}>{notional_s}</td>"
            f"<td {td_style('white-space:normal;overflow:visible;text-overflow:clip;max-width:none;min-width:220px;color:'+TEXT2+' !important;', border=border, nowrap=False)}>{reason}</td>"
            f"<td {td_style('color:'+TEXT3+' !important;', border=border)}>{date_s}</td>"
            f"</tr>"
        )

    table = (
        f"<table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr>"
        f"<th {th_style()}>ID</th>"
        f"<th {th_style()}>Symbol</th>"
        f"<th {th_style()}>Confidence</th>"
        f"<th {th_style('text-align:right;')}>Suggested Size</th>"
        f"<th {th_style()}>Reason</th>"
        f"<th {th_style()}>Created</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>"
    )
    return (
        f'<div class="nt nt-wrap">'
        f'{_section("⏳", "Pending Approvals", f"{n} awaiting a decision")}'
        f'{_wrap(table)}'
        f'</div>'
    )


def do_approve_decision(decision_id_str: str) -> str:
    """Human clicked Approve — flips decision_status only. The bot's own
    loop places the real order on its next cycle; this never touches Alpaca."""
    try:
        # int(x) rejects "19.0" outright -- gr.Number always hands on_approve_click/
        # on_reject_click a float, so str(that float) round-trips through here as
        # "19.0", not "19". Parsing via float() first handles both shapes.
        decision_id = int(float(decision_id_str))
    except Exception:
        return f'<span style="color:{LOSS};font-size:12px;">⚠ Invalid decision ID</span>'
    try:
        from database.services.decision_service import approve_decision
        with get_db_conn() as con:
            row = con.execute(
                "SELECT decision_status FROM decision_log WHERE decision_id=?", (decision_id,)
            ).fetchone()
            if not row:
                return f'<span style="color:{LOSS};font-size:12px;">⚠ Decision {decision_id} not found</span>'
            if row[0] != "WAITING_APPROVAL":
                return (f'<span style="color:{LOSS};font-size:12px;">⚠ Decision {decision_id} is '
                        f'{row[0]}, not awaiting approval</span>')
            approve_decision(con, decision_id, approved_by="user")
        return f'<span style="color:{GAIN};font-size:12px;">&#10003; Approved decision {decision_id}</span>'
    except Exception as exc:
        _logger.warning(f"do_approve_decision: {exc}")
        return f'<span style="color:{LOSS};font-size:12px;">⚠ {exc}</span>'


def do_reject_decision(decision_id_str: str, reason: str) -> str:
    """Human clicked Reject — terminal, the decision never executes."""
    try:
        # int(x) rejects "19.0" outright -- gr.Number always hands on_approve_click/
        # on_reject_click a float, so str(that float) round-trips through here as
        # "19.0", not "19". Parsing via float() first handles both shapes.
        decision_id = int(float(decision_id_str))
    except Exception:
        return f'<span style="color:{LOSS};font-size:12px;">⚠ Invalid decision ID</span>'
    try:
        from database.services.decision_service import reject_decision
        with get_db_conn() as con:
            row = con.execute(
                "SELECT decision_status FROM decision_log WHERE decision_id=?", (decision_id,)
            ).fetchone()
            if not row:
                return f'<span style="color:{LOSS};font-size:12px;">⚠ Decision {decision_id} not found</span>'
            if row[0] != "WAITING_APPROVAL":
                return (f'<span style="color:{LOSS};font-size:12px;">⚠ Decision {decision_id} is '
                        f'{row[0]}, not awaiting approval</span>')
            reject_decision(con, decision_id, rejected_by="user", reason=reason or "Rejected via dashboard")
        return f'<span style="color:{GAIN};font-size:12px;">&#10003; Rejected decision {decision_id}</span>'
    except Exception as exc:
        _logger.warning(f"do_reject_decision: {exc}")
        return f'<span style="color:{LOSS};font-size:12px;">⚠ {exc}</span>'


def on_approve_click(decision_id: float | None) -> tuple[str, str]:
    """Button-click wrapper: (status_html, refreshed_table_html)."""
    return do_approve_decision(str(decision_id) if decision_id is not None else ""), render_pending_approvals()


def on_reject_click(decision_id: float | None, reason: str) -> tuple[str, str]:
    """Button-click wrapper: (status_html, refreshed_table_html)."""
    return do_reject_decision(str(decision_id) if decision_id is not None else "", reason), render_pending_approvals()


register(ComponentSpec("pending_approvals_out", RefreshGroup.FAST, render_pending_approvals, priority=42))
