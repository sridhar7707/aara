"""ADR-083 / ADR-085: paper-only ETF overlay rule, planning, refusals and endpoint guard."""
import numpy as np
import pandas as pd
import pytest

from bot.execution import etf_paper as ep
from scripts import backtest_etf_trend as bt


def _closes(up=(), down=(), n=300):
    idx = pd.bdate_range("2024-01-01", periods=n)
    cols = {}
    for s in up:
        cols[s] = np.linspace(50, 150, n)
    for s in down:
        cols[s] = np.linspace(150, 50, n)
    return pd.DataFrame(cols, index=idx)


def _full_universe_closes(up=("XLK",), n=300):
    """Every overlay symbol present: `up` trend up, the rest trend down."""
    return _closes(up=list(up), down=[s for s in ep.ETF_UNIVERSE if s not in up], n=n)


def test_endpoint_guard_accepts_only_exact_paper_url():
    ep.assert_paper_endpoint("https://paper-api.alpaca.markets")
    ep.assert_paper_endpoint("https://paper-api.alpaca.markets/")
    for bad in ["https://api.alpaca.markets", "https://paper-api.alpaca.markets.evil.com",
                "http://paper-api.alpaca.markets", ""]:
        with pytest.raises(RuntimeError):
            ep.assert_paper_endpoint(bad)


def test_trend_targets_hold_only_uptrending_etfs_equal_weighted_among_held():
    w = ep.trend_targets(_full_universe_closes(up=("XLK", "QQQ")))
    assert set(w) == {"XLK", "QQQ"}
    assert all(v == pytest.approx(0.5) for v in w.values())


def test_trend_targets_empty_when_nothing_is_up():
    assert ep.trend_targets(_full_universe_closes(up=())) == {}


def test_trend_targets_refuses_short_history():
    with pytest.raises(ValueError):
        ep.trend_targets(_full_universe_closes(n=50))


def test_trend_targets_refuses_a_missing_etf_instead_of_planning_a_partial_universe():
    c = _full_universe_closes().drop(columns=["XLK"])
    with pytest.raises(ValueError, match="no price history"):
        ep.trend_targets(c)


def test_trend_targets_refuses_a_nan_last_close():
    """A NaN last close must not be read as 'off-trend' and sold."""
    c = _full_universe_closes(up=("QQQ",))
    c.iloc[-1, c.columns.get_loc("QQQ")] = np.nan
    with pytest.raises(ValueError, match="invalid last close"):
        ep.trend_targets(c)


# --- the tested 10-month month-end rule (scripts/backtest_etf_trend.py) ---

def _month_end_series(month_ends, filler, idx):
    """Daily series on idx: every day `filler` except each calendar month's last day, set from month_ends."""
    s = pd.Series(float(filler), index=idx)
    last_days = s.groupby(idx.to_period("M")).tail(1).index
    assert len(last_days) == len(month_ends)
    s.loc[last_days] = list(month_ends)
    return s


def _flat_universe(idx, value=100.0):
    return pd.DataFrame({s: np.full(len(idx), value) for s in ep.ETF_UNIVERSE}, index=idx)


def test_trend_months_is_ten():
    assert ep.TREND_MONTHS == 10 == bt.TREND_MONTHS
    assert not hasattr(ep, "TREND_WINDOW")


def test_month_end_mean_is_used_not_the_daily_mean():
    idx = pd.bdate_range("2024-01-01", "2024-10-31")           # 10 calendar months, >210 trading days
    assert len(idx) >= 210
    c = _flat_universe(idx)
    rising = [100.0 + i for i in range(10)]                    # month-ends rise: last 109 > mean 104.5
    c["XLK"] = _month_end_series(rising, filler=1000.0, idx=idx)           # daily mean far above the last close
    c["QQQ"] = _month_end_series(rising[::-1], filler=1.0, idx=idx)        # month-ends fall; daily mean far below
    # the old daily rule would decide the opposite way for both
    assert c["XLK"].iloc[-1] < c["XLK"].iloc[-210:].mean()
    assert c["QQQ"].iloc[-1] > c["QQQ"].iloc[-210:].mean()
    assert ep.trend_targets(c) == {"XLK": 1.0}


def test_strictly_above_is_required_equal_is_not_held():
    idx = pd.bdate_range("2024-01-01", "2024-12-31")
    c = _flat_universe(idx, 100.0)                             # last close == 10-month mean exactly
    assert ep.trend_targets(c) == {}
    c["GLD"] = _month_end_series([100.0] * 11 + [100.5], filler=100.0, idx=idx)   # 100.5 > mean 100.05
    assert ep.trend_targets(c) == {"GLD": 1.0}


def test_fewer_than_ten_month_ends_raises_even_with_many_daily_closes():
    idx = pd.date_range("2024-01-01", "2024-09-30", freq="D")  # 9 months, 274 daily rows (> 210)
    assert len(idx) > 210
    with pytest.raises(ValueError, match="10 month-end closes, have 9"):
        ep.trend_targets(_flat_universe(idx))


def test_an_etf_with_fewer_than_ten_month_ends_is_not_held():
    idx = pd.bdate_range("2024-01-01", "2024-12-31")
    c = _full_universe_closes(up=("QQQ",), n=len(idx)).set_index(idx)
    new = pd.Series(np.linspace(50, 150, len(idx)), index=idx)
    new[idx < "2024-05-01"] = np.nan                            # only 8 month-ends of history
    c["XLK"] = new
    assert ep.trend_targets(c) == {"QQQ": 1.0}


def test_matches_the_backtest_rule_on_a_fixed_synthetic_series():
    # scripts/backtest_etf_trend.py computes the signal inline inside strategy_returns (no importable rule
    # function), so its two signal lines are replicated here:
    #   m = px.resample("ME").last();  sig = (m > m.rolling(bt.TREND_MONTHS).mean())
    rng = np.random.default_rng(20261108)
    idx = pd.bdate_range("2022-01-03", "2024-12-31")
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (len(idx), len(bt.ETFS))), axis=0)),
                      index=idx, columns=bt.ETFS)
    m = px.resample("ME").last()
    sig = m > m.rolling(bt.TREND_MONTHS).mean()
    held_sets = set()
    for month_end in m.index[bt.TREND_MONTHS - 1:]:
        daily_cut = px[px.index.to_period("M") <= month_end.to_period("M")]
        want = sorted(sig.loc[month_end][sig.loc[month_end]].index)
        got = ep.trend_targets(daily_cut)
        assert sorted(got) == want, month_end
        if want:
            assert all(v == pytest.approx(1.0 / len(want)) for v in got.values())
        held_sets.add(tuple(want))
    assert len(held_sets) > 3          # the series is not degenerate: the held set actually changes


def test_plan_buys_and_sells_to_target_sells_first():
    plan = ep.plan_orders(10_000.0, {"XLE": 2_000.0}, {"XLE": 40.0}, {"XLK": 0.5},
                          {"XLK": 100.0, "XLE": 50.0}, cash_available=10_000.0)
    assert [p["side"] for p in plan] == ["sell", "buy"]
    assert plan[0]["symbol"] == "XLE" and plan[0]["qty"] == pytest.approx(40.0)
    assert plan[1]["symbol"] == "XLK" and plan[1]["notional"] == pytest.approx(5_000.0)


def test_full_exit_sells_the_actual_held_quantity_even_below_min_trade():
    plan = ep.plan_orders(10_000.0, {"XLE": 20.0}, {"XLE": 0.4}, {}, {"XLE": 50.0}, cash_available=0.0)
    assert plan == [{"symbol": "XLE", "side": "sell", "notional": 20.0, "qty": 0.4}]


def test_plan_skips_differences_below_minimum():
    plan = ep.plan_orders(10_000.0, {"XLK": 5_000.0}, {"XLK": 50.0}, {"XLK": 0.5}, {"XLK": 100.0},
                          cash_available=0.0)
    assert plan == []


def test_plan_refuses_buys_beyond_available_cash():
    with pytest.raises(ValueError, match="exceed cash"):
        ep.plan_orders(10_000.0, {}, {}, {"XLK": 1.0}, {"XLK": 100.0}, cash_available=5_000.0)


def test_plan_refuses_non_overlay_symbols():
    with pytest.raises(ValueError, match="non-overlay"):
        ep.plan_orders(10_000.0, {"AAPL": 3_000.0}, {"AAPL": 30.0}, {}, {"AAPL": 100.0}, cash_available=0.0)


def test_plan_requires_a_valid_price_for_every_trade():
    with pytest.raises(ValueError, match="no valid price"):
        ep.plan_orders(10_000.0, {}, {}, {"XLK": 0.5}, {}, cash_available=10_000.0)
    with pytest.raises(ValueError, match="no valid price"):
        ep.plan_orders(10_000.0, {}, {}, {"XLK": 0.5}, {"XLK": float("nan")}, cash_available=10_000.0)


# --- C2/C4/C5/C6 pure parts ---

def test_client_order_id_is_deterministic_per_month_symbol_side():
    assert ep.client_order_id("2026-11", "XLK", "buy") == "etf-2026-11-XLK-buy"
    assert ep.client_order_id("2026-11", "XLK", "sell") != ep.client_order_id("2026-11", "XLK", "buy")


def test_check_sleeve_passes_within_limits():
    ep.check_sleeve(sleeve=1_000.0, equity=10_000.0, cash_after_buys=5_000.0, reserve_pct=0.10)
    ep.check_sleeve(sleeve=1_000.0, equity=10_000.0, cash_after_buys=1_000.0, reserve_pct=0.10)  # exactly at limits


def test_check_sleeve_refuses_sleeve_above_ten_percent_of_equity():
    with pytest.raises(ValueError, match="exceeds"):
        ep.check_sleeve(sleeve=1_000.01, equity=10_000.0, cash_after_buys=5_000.0, reserve_pct=0.10)


def test_check_sleeve_refuses_cash_below_reserve():
    with pytest.raises(ValueError, match="reserve"):
        ep.check_sleeve(sleeve=500.0, equity=10_000.0, cash_after_buys=999.0, reserve_pct=0.10)


def test_check_sleeve_refuses_invalid_equity():
    for bad in (0.0, -5.0, float("nan")):
        with pytest.raises(ValueError, match="equity"):
            ep.check_sleeve(sleeve=1.0, equity=bad, cash_after_buys=1_000.0, reserve_pct=0.10)


def test_overlay_value_ok_allows_up_to_five_percent_over_sleeve():
    assert ep.overlay_value_ok({}, 1_000.0)
    assert ep.overlay_value_ok({"XLK": 600.0, "QQQ": 450.0}, 1_000.0)       # 1050 == limit
    assert not ep.overlay_value_ok({"XLK": 600.0, "QQQ": 451.0}, 1_000.0)


def test_overlay_value_ok_false_on_bad_numbers():
    assert not ep.overlay_value_ok({"XLK": float("nan")}, 1_000.0)
    assert not ep.overlay_value_ok({"XLK": 1.0}, 0.0)


def test_overlay_symbols_in_filters_to_the_universe_and_sorts():
    assert ep.overlay_symbols_in(["AAPL", "XLK", "GLD", "TSLA"]) == ["GLD", "XLK"]
    assert ep.overlay_symbols_in([]) == []
