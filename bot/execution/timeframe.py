"""Shared timeframe-string parsing for both AlpacaClient and PaperExecutor.

Deliberately its own module: alpaca_client.py has top-level imports of
alpaca.trading (the order-submission SDK), so importing this helper FROM
alpaca_client.py would transitively pull alpaca.trading into any module
that imports it -- including PaperExecutor, whose core safety guarantee is
that it never can. This module only touches alpaca.data.timeframe
(market-data, read-only), so it's safe for both to share.
"""
from __future__ import annotations

import re

from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

_TIMEFRAME_UNITS = {
    "min": TimeFrameUnit.Minute, "minute": TimeFrameUnit.Minute,
    "hour": TimeFrameUnit.Hour, "day": TimeFrameUnit.Day,
    "week": TimeFrameUnit.Week, "month": TimeFrameUnit.Month,
}


def parse_timeframe(spec: str) -> TimeFrame:
    """Parse strings like '5Min', '1Hour', '1Day' into a TimeFrame."""
    m = re.match(r"(\d+)([A-Za-z]+)", spec)
    if not m:
        raise ValueError(f"Unrecognized timeframe: {spec!r}")
    amount, unit_str = int(m.group(1)), m.group(2).lower()
    unit = _TIMEFRAME_UNITS.get(unit_str)
    if unit is None:
        raise ValueError(f"Unrecognized timeframe unit: {unit_str!r}")
    return TimeFrame(amount, unit)
