"""ADR-081 Tier 1: model-validity fixes.

1.1 forward target is built per symbol, so the shift never crosses tickers.
1.2/1.3 time split has three disjoint segments with a purge at each boundary.
1.4 regime labels are never recomputed on a combined multi-symbol frame.
"""
import numpy as np
import pandas as pd
import pytest

from bot.strategy.regime_classifier import RegimeClassifier
from bot.strategy.xgb_predictor import (
    FORWARD_PERIODS,
    MIN_MOVE_PCT,
    XGBPredictor,
    forward_target,
    time_split,
)


def _two_symbols(n=120):
    """Two tickers at very different price levels, same dates."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    a = pd.DataFrame({"close": np.linspace(10, 20, n)}, index=idx)
    b = pd.DataFrame({"close": np.linspace(1000, 900, n)}, index=idx)
    return a, b


def test_forward_target_is_computed_within_one_symbol():
    a, b = _two_symbols()
    ta, tb = forward_target(a["close"]), forward_target(b["close"])
    # Row t of symbol A must depend only on A's own future closes.
    expected_a = ((a["close"].shift(-FORWARD_PERIODS) - a["close"]) / a["close"] > MIN_MOVE_PCT).astype(int)
    pd.testing.assert_series_equal(ta, expected_a, check_names=False)
    assert ta.iloc[0] == 1  # rising symbol: forward return above the threshold
    assert tb.iloc[0] == 0  # falling symbol


def test_cross_symbol_shift_would_differ_from_per_symbol_target():
    """Documents the bug: shifting a combined frame gives different labels."""
    a, b = _two_symbols()
    combined = pd.concat([a, b]).sort_index(kind="stable")
    crossed = forward_target(combined["close"])
    per_symbol = pd.concat([forward_target(a["close"]), forward_target(b["close"])]).sort_index(kind="stable")
    assert not crossed.equals(per_symbol.reindex(crossed.index))


def test_time_split_segments_are_disjoint_and_ordered():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    df = pd.DataFrame({"x": range(400)}, index=idx)
    train, val, hold = time_split(df)
    assert len(train) and len(val) and len(hold)
    assert train.index.max() < val.index.min()
    assert val.index.max() < hold.index.min()
    assert not set(train.index) & set(val.index)
    assert not set(val.index) & set(hold.index)


def test_time_split_purges_labels_that_cross_a_boundary():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    df = pd.DataFrame({"x": range(400)}, index=idx)
    train, val, hold = time_split(df)
    dates = sorted(df.index.unique())
    gap_train_val = dates.index(val.index.min()) - dates.index(train.index.max())
    gap_val_hold = dates.index(hold.index.min()) - dates.index(val.index.max())
    assert gap_train_val >= FORWARD_PERIODS
    assert gap_val_hold >= FORWARD_PERIODS


def test_time_split_holdout_is_the_latest_fifteen_percent():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    df = pd.DataFrame({"x": range(400)}, index=idx)
    _, _, hold = time_split(df)
    assert hold.index.max() == idx.max()
    assert abs(len(hold) - 0.15 * 400) <= FORWARD_PERIODS + 1


def test_xgb_train_refuses_a_frame_without_per_symbol_target():
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    df = pd.DataFrame({"close": np.linspace(1, 2, 50)}, index=idx)
    with pytest.raises(ValueError, match="per-symbol 'target'"):
        XGBPredictor().train(df, save=False)


def test_regime_train_refuses_a_frame_without_per_symbol_labels():
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    df = pd.DataFrame({"close": np.linspace(1, 2, 50)}, index=idx)
    with pytest.raises(ValueError, match="per-symbol 'regime' labels"):
        RegimeClassifier.__new__(RegimeClassifier).train(df)
