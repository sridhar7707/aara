"""ADR-083 / ADR-085: paper-only ETF overlay rule, planning, refusals and endpoint guard."""
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
