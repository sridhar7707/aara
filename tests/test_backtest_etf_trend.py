"""scripts/backtest_etf_trend.py: the tested definition (10 month-end closes, equal weight, 10 bps, 12 ETFs)."""
import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep
from scripts import backtest_etf_trend as bt


def _px(up=("XLK",), months=40):
    idx = pd.bdate_range("2015-01-01", periods=months * 21)
    cols = {s: (np.linspace(50, 150, len(idx)) if s in up else np.linspace(150, 50, len(idx)))
            for s in bt.ETFS + ["SPY"]}
    return pd.DataFrame(cols, index=idx)


def test_universe_and_window_are_the_tested_ones():
    assert sorted(bt.ETFS) == ep.ETF_UNIVERSE and len(bt.ETFS) == 12
    assert bt.TREND_MONTHS == 10 and bt.COST == 0.0010 and len(bt.FOLDS) == 5
    assert "NOT 210 trading days" in open(bt.__file__, encoding="utf-8").read()


def test_single_uptrend_etf_is_held_alone_and_cost_is_charged_on_entry_turnover():
    r, spy = bt.strategy_returns(_px())
    m = _px().resample("ME").last()
    mret = m.pct_change()
    # after the 10-month warm-up (+1 month for the shift) only XLK is held at weight 1.0
    t = m.index[12]
    assert r.loc[t] == pytest.approx(mret.loc[t, "XLK"])
    entry = m.index[10]   # first month earning XLK: signal true at index 9, turnover 1.0 -> 10 bps
    assert r.loc[entry] == pytest.approx(mret.loc[entry, "XLK"] - bt.COST)


def test_all_downtrend_is_cash():
    r, _ = bt.strategy_returns(_px(up=()))
    assert (r == 0).all()


def test_equal_weight_among_held():
    r, _ = bt.strategy_returns(_px(up=("XLK", "XLE")))
    m = _px(up=("XLK", "XLE")).resample("ME").last()
    mret = m.pct_change()
    t = m.index[15]
    assert r.loc[t] == pytest.approx(0.5 * mret.loc[t, "XLK"] + 0.5 * mret.loc[t, "XLE"])


def test_missing_raw_directory_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="raw CSVs"):
        bt.load_prices(tmp_path)
