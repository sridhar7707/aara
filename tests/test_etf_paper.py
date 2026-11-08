"""ADR-083: paper-only ETF overlay rule, planning and endpoint guard."""
import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep


def _closes(up=(), down=(), n=300):
    idx = pd.bdate_range("2024-01-01", periods=n)
    cols = {}
    for s in up:
        cols[s] = np.linspace(50, 150, n)
    for s in down:
        cols[s] = np.linspace(150, 50, n)
    return pd.DataFrame(cols, index=idx)


def test_endpoint_guard_accepts_only_exact_paper_url():
    ep.assert_paper_endpoint("https://paper-api.alpaca.markets")
    ep.assert_paper_endpoint("https://paper-api.alpaca.markets/")
    for bad in ["https://api.alpaca.markets", "https://paper-api.alpaca.markets.evil.com",
                "http://paper-api.alpaca.markets", ""]:
        with pytest.raises(RuntimeError):
            ep.assert_paper_endpoint(bad)


def test_trend_targets_hold_only_uptrending_etfs_equal_weighted_among_held():
    c = _closes(up=["XLK", "QQQ"], down=["XLE"])
    w = ep.trend_targets(c)
    assert set(w) == {"XLK", "QQQ"}
    assert all(v == pytest.approx(0.5) for v in w.values())  # equal among held, fully invested


def test_trend_targets_empty_when_nothing_is_up():
    assert ep.trend_targets(_closes(down=["XLK"])) == {}


def test_trend_targets_refuses_short_history():
    with pytest.raises(ValueError):
        ep.trend_targets(_closes(up=["XLK"], n=50))


def test_plan_buys_and_sells_to_target_sells_first():
    equity = 10_000.0
    current = {"XLE": 2_000.0}                 # currently held, now off-trend
    weights = {"XLK": 0.5}                     # target 5,000 of XLK
    plan = ep.plan_orders(equity, current, weights, {"XLK": 100.0, "XLE": 50.0})
    assert [p["side"] for p in plan] == ["sell", "buy"]
    assert plan[0]["symbol"] == "XLE" and plan[0]["qty"] == pytest.approx(40.0)
    assert plan[1]["symbol"] == "XLK" and plan[1]["notional"] == pytest.approx(5_000.0)


def test_plan_skips_differences_below_minimum():
    plan = ep.plan_orders(10_000.0, {"XLK": 5_000.0}, {"XLK": 0.5}, {"XLK": 100.0})
    assert plan == []


def test_plan_requires_a_price_for_every_trade():
    with pytest.raises(ValueError):
        ep.plan_orders(10_000.0, {}, {"XLK": 0.5}, {})
