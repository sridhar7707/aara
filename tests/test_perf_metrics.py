"""Tests for analytics/perf_metrics.py (daily resampling)."""
import math

import pytest

from analytics.perf_metrics import (
    annualised_sharpe,
    annualised_sortino,
    daily_returns,
    last_value_per_day,
)


def test_last_value_per_day_takes_the_final_reading():
    rows = [("2026-11-02T10:00", 100.0), ("2026-11-02T15:00", 110.0), ("2026-11-03T09:00", 105.0)]
    assert last_value_per_day(rows) == [110.0, 105.0]


def test_cadence_does_not_change_the_daily_figure():
    # One reading a day, versus the same day sampled 20 times: identical daily returns.
    daily = [(f"2026-10-{d:02d}T16:00", 100.0 * (1.01 if d % 2 else 0.995) ** d) for d in range(1, 30)]
    dense = []
    for ts, v in daily:
        for k in range(20):
            dense.append((ts[:11] + f"{k:02d}:00", v * (1 + 0.00001 * k)))  # drift inside the day
    assert daily_returns(daily) == pytest.approx(daily_returns(dense), rel=1e-4)


def test_sharpe_uses_sqrt_252_on_daily_returns():
    rows = [(f"2026-09-{d:02d}T16:00", 100.0 + (d % 3) * 0.5 + d * 0.1) for d in range(1, 31)]
    rets = daily_returns(rows)
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
    assert annualised_sharpe(rows, min_days=5) == pytest.approx(mean / sd * math.sqrt(252))


def test_too_few_days_returns_none():
    rows = [("2026-11-02T10:00", 100.0), ("2026-11-03T10:00", 101.0)]
    assert annualised_sharpe(rows) is None
    assert annualised_sortino(rows) is None


def test_flat_series_returns_none_not_a_division_by_zero():
    rows = [(f"2026-09-{d:02d}T16:00", 100.0) for d in range(1, 31)]
    assert annualised_sharpe(rows, min_days=5) is None
