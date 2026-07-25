"""Risk-state persistence: RiskSnapshot dataclass + load/save helpers."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from loguru import logger

from bot.risk.risk_manager import RiskManager


@dataclass
class RiskSnapshot:
    daily_start: float | None
    day_trade_dates: list[str] = field(default_factory=list)
    weekly_start: float | None = None
    daily_warning_sent: bool = False
    weekly_halt_alerted: bool = False
    portfolio_high: float | None = None


def _week_key() -> str:
    return date.today().strftime("%G-W%V")


def load_risk_state(con: sqlite3.Connection) -> RiskSnapshot:
    """Load persisted risk state into a typed snapshot."""
    today = date.today().isoformat()
    wk    = _week_key()
    rows  = {r[0]: r[1] for r in con.execute("SELECT key, value FROM risk_state")}

    daily_start: float | None = None
    if rows.get("daily_start_date") == today:
        try:
            daily_start = float(rows["daily_start_value"])
        except (KeyError, ValueError, TypeError):
            pass

    day_trade_dates: list[str] = []
    try:
        day_trade_dates = json.loads(rows.get("day_trade_dates", "[]"))
    except (json.JSONDecodeError, TypeError):
        pass

    weekly_start: float | None = None
    if rows.get("weekly_start_week") == wk:
        try:
            weekly_start = float(rows["weekly_start_value"])
        except (KeyError, ValueError, TypeError):
            pass

    daily_warning_sent  = rows.get("daily_warning_sent_date") == today
    weekly_halt_alerted = rows.get("weekly_halt_alerted_week") == wk

    portfolio_high: float | None = None
    try:
        portfolio_high = float(rows["portfolio_high"])
    except (KeyError, ValueError, TypeError):
        pass

    return RiskSnapshot(
        daily_start=daily_start,
        day_trade_dates=day_trade_dates,
        weekly_start=weekly_start,
        daily_warning_sent=daily_warning_sent,
        weekly_halt_alerted=weekly_halt_alerted,
        portfolio_high=portfolio_high,
    )


def save_risk_state(con: sqlite3.Connection, risk: RiskManager) -> None:
    today  = date.today().isoformat()
    wk     = _week_key()
    trades = json.dumps([d.isoformat() for d in risk.day_trade_log])
    start  = str(risk.daily_start_value)  if risk.daily_start_value  is not None else ""
    weekly = str(risk.weekly_start_value) if risk.weekly_start_value is not None else ""
    entries = [
        ("daily_start_value",        start),
        ("daily_start_date",         today),
        ("day_trade_dates",          trades),
        ("weekly_start_value",       weekly),
        ("weekly_start_week",        wk),
        ("daily_warning_sent_date",  today if risk.daily_warning_sent else ""),
        ("weekly_halt_alerted_week", wk    if risk.weekly_halt_alerted else ""),
        ("portfolio_high",           str(risk.portfolio_high) if risk.portfolio_high is not None else ""),
        ("trading_halted_date",      today if risk.halted else ""),
    ]
    for key, val in entries:
        con.execute(
            "INSERT OR REPLACE INTO risk_state (key, value, updated_at) VALUES (?,?,?)",
            (key, val, datetime.now(timezone.utc).isoformat()),
        )
    con.commit()
    logger.debug(f"Risk state persisted: daily_start={risk.daily_start_value}, halted={risk.halted}")
