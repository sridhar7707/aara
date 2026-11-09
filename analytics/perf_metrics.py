"""Daily-return performance metrics (decided 2026-11-09, financial expert).

Snapshots are written every cycle, so the observation cadence varies with how often the bot
runs. A Sharpe ratio annualised with a fixed cadence therefore depends on the schedule, not on
the strategy. These functions resample to one value per calendar day, take daily returns, and
annualise with sqrt(252). Pure functions: no database access.
"""
from __future__ import annotations

import math
from collections import OrderedDict

TRADING_DAYS = 252


def last_value_per_day(rows: list[tuple[str, float]]) -> list[float]:
    """Take the last value of each calendar day (rows are (timestamp, value))."""
    by_day: OrderedDict[str, float] = OrderedDict()
    for ts, value in sorted(rows, key=lambda r: r[0]):
        if ts is None or value is None:
            continue
        by_day[str(ts)[:10]] = float(value)
    return list(by_day.values())


def daily_returns(rows: list[tuple[str, float]]) -> list[float]:
    values = last_value_per_day(rows)
    out = []
    for prev, cur in zip(values, values[1:]):
        if prev > 0:
            out.append(cur / prev - 1.0)
    return out


def annualised_sharpe(rows: list[tuple[str, float]], min_days: int = 20) -> float | None:
    """Mean over standard deviation of daily returns, times sqrt(252). None if too few days."""
    rets = daily_returns(rows)
    if len(rets) < min_days:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return mean / sd * math.sqrt(TRADING_DAYS)


def annualised_sortino(rows: list[tuple[str, float]], min_days: int = 20) -> float | None:
    rets = daily_returns(rows)
    if len(rets) < min_days:
        return None
    mean = sum(rets) / len(rets)
    downside = [r for r in rets if r < 0]
    if len(downside) < 2:
        return None
    dvar = sum(r * r for r in downside) / len(downside)
    dsd = math.sqrt(dvar)
    if dsd == 0:
        return None
    return mean / dsd * math.sqrt(TRADING_DAYS)
