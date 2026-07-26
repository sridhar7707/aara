"""Trade Journal dashboard component — entry/exit log with pattern stats."""
from __future__ import annotations

from loguru import logger

from bot.core.error_logger import safe_render, timed
from dashboard.data import get_db_conn
from dashboard.design_system import (
    BORDER, GAIN, LOSS, NEURAL, SURFACE, TEXT1, TEXT2, TEXT3,
    FONT_HERO, FONT_LABEL, FONT_VALUE, WEIGHT_BOLD,
    TH, TD, TD0, td_style, th_style, _section, _empty_state, _card, _wrap,
)
from dashboard.registry import ComponentSpec, RefreshGroup, register

_logger = logger

_CELL  = f"padding:8px 14px;font-size:{FONT_VALUE};color:{TEXT2};"
_CELL1 = f"padding:8px 14px;font-size:{FONT_VALUE};color:{TEXT1};font-weight:{WEIGHT_BOLD};"
_NUM   = f"padding:8px 14px;font-size:{FONT_VALUE};color:{TEXT1};text-align:right;font-family:Courier New,monospace;"


def _outcome_color(pct: float | None) -> str:
    if pct is None:
        return TEXT3
    return GAIN if pct > 0 else (LOSS if pct < 0 else TEXT3)


def _outcome_str(pct: float | None) -> str:
    if pct is None:
        return "open"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1%}"


def _reason_label(reason: str | None) -> str:
    mapping = {
        "take-profit":    "Take Profit",
        "stop-loss":      "Stop Loss",
        "trailing-stop":  "Trailing Stop",
        "time-exit":      "Time Exit",
        "signal":         "Signal Sell",
        "gap-down":       "Gap Down",
        "drift-trim":     "Drift Trim",
    }
    return mapping.get(reason or "", reason or "—")


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return iso[:10]
    except Exception:
        return iso


def _read_recent() -> list[dict]:
    from database.trade_journal import recent_entries
    try:
        with get_db_conn() as con:
            return recent_entries(con, limit=25)
    except Exception as e:
        _logger.warning(f"trade_journal read recent: {e}")
        return []


def _read_pattern_stats() -> list[dict]:
    from database.trade_journal import query_pattern_stats
    try:
        with get_db_conn() as con:
            return query_pattern_stats(con)
    except Exception as e:
        _logger.warning(f"trade_journal pattern stats: {e}")
        return []


@timed(_logger)
@safe_render("Trade Journal")
def render_trade_journal() -> str:
    rows = _read_recent()
    stats = _read_pattern_stats()

    # ── Pattern summary ────────────────────────────────────────────────────────
    if stats:
        stat_rows = ""
        for i, s in enumerate(stats):
            border = i < len(stats) - 1
            wr_color = GAIN if s["win_rate"] >= 55 else (LOSS if s["win_rate"] < 40 else TEXT2)
            avg_color = GAIN if s["avg_pct"] > 0 else LOSS
            stat_rows += (
                f"<tr>"
                f"<td {td_style(_CELL1, border=border)}>{_reason_label(s['exit_reason'])}</td>"
                f"<td {td_style(_NUM, border=border)}>{s['n']}</td>"
                f"<td {td_style(_NUM + f'color:{wr_color};', border=border)}>{s['win_rate']:.0f}%</td>"
                f"<td {td_style(_NUM + f'color:{avg_color};', border=border)}>{'+' if s['avg_pct']>=0 else ''}{s['avg_pct']:.1f}%</td>"
                f"</tr>"
            )
        pattern_table = (
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th {th_style('text-align:left;')}>Exit Type</th>"
            f"<th {th_style('text-align:right;')}>Trades</th>"
            f"<th {th_style('text-align:right;')}>Win Rate</th>"
            f"<th {th_style('text-align:right;')}>Avg Return</th>"
            f"</tr></thead><tbody>{stat_rows}</tbody></table>"
        )
        pattern_section = f'<div class="nt nt-wrap">{_section("📊", "Pattern Stats", f"{len(stats)} exit types")}{pattern_table}</div>'
    else:
        pattern_section = ""

    # ── Recent journal entries ─────────────────────────────────────────────────
    if not rows:
        journal_section = (
            f'<div class="nt nt-wrap">'
            f'{_section("📓", "Trade Journal", "")}'
            f'{_card(_empty_state("📓", "No journal entries yet", "Entries are recorded automatically on each BUY and closed on each SELL."))}'
            f'</div>'
        )
    else:
        tbody = ""
        for i, r in enumerate(rows):
            border = i < len(rows) - 1
            pct = r.get("outcome_pct")
            oc  = _outcome_color(pct)
            closed = r.get("closed_at")
            status_tag = (
                f"<span style='background:{LOSS};color:#fff;border-radius:3px;"
                f"padding:1px 6px;font-size:10px;'>closed</span>"
                if closed else
                f"<span style='background:{NEURAL};color:#fff;border-radius:3px;"
                f"padding:1px 6px;font-size:10px;'>open</span>"
            )
            lesson = r.get("lesson") or ""
            conf   = r.get("entry_confidence")
            conf_s = f"{conf:.0%}" if conf is not None else "—"
            # white-space:normal + overflow:visible on the Lesson cell overrides
            # the global .nt-wrap td ellipsis-truncation rule (dashboard/layout.py)
            # so the full lesson text wraps instead of getting cut off.
            tbody += (
                f"<tr>"
                f"<td {td_style(_CELL1, border=border)}>{r.get('symbol','—')} {status_tag}</td>"
                f"<td {td_style(_CELL, border=border)}>{_fmt_date(r.get('created_at'))}</td>"
                f"<td {td_style(_CELL, border=border)}>{conf_s}</td>"
                f"<td {td_style(_CELL, border=border)}>{_reason_label(r.get('exit_reason'))}</td>"
                f"<td {td_style(_NUM + f'color:{oc};', border=border)}>{_outcome_str(pct)}</td>"
                f"<td {td_style(_CELL + f'font-style:italic;color:{TEXT3};white-space:normal;overflow:visible;text-overflow:clip;max-width:none;min-width:220px;', border=border, nowrap=False)}>{lesson}</td>"
                f"</tr>"
            )
        table = (
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr>"
            f"<th {th_style('text-align:left;')}>Symbol</th>"
            f"<th {th_style('text-align:left;')}>Entry Date</th>"
            f"<th {th_style('text-align:left;')}>Confidence</th>"
            f"<th {th_style('text-align:left;')}>Exit Type</th>"
            f"<th {th_style('text-align:right;')}>Return</th>"
            f"<th {th_style('text-align:left;')}>Lesson</th>"
            f"</tr></thead><tbody>{tbody}</tbody></table>"
        )
        journal_section = (
            f'<div class="nt nt-wrap">'
            f'{_section("📓", "Trade Journal", f"{len(rows)} recent entries")}'
            f'{table}</div>'
        )

    return _wrap(pattern_section + journal_section)


register(ComponentSpec(
    key="trade_journal_out",
    group=RefreshGroup.SLOW,
    render_fn=render_trade_journal,
    priority=55,
))
