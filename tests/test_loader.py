"""Tests for bot.eval.loader."""
import pytest

from bot._main_db import init_db, log_trade
from bot.eval.loader import load_completed_trades


@pytest.fixture
def db():
    return init_db(":memory:")


def test_load_completed_trades_simple_pair(db):
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "AAPL", "SELL_STOP", 5.0, 110.0, 550.0, "TRENDING_UP", 10000.0, 0.10)
    df = load_completed_trades(con=db)
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "AAPL"
    assert df.iloc[0]["pnl_pct"] == pytest.approx(0.10)


def test_load_completed_trades_excludes_sell_reconcile_entirely(db):
    """SELL_RECONCILE must not even occupy a rank slot — including it (even
    if its P&L were later filtered) would shift every later sell for the
    symbol onto the wrong buy."""
    log_trade(db, "GOOGL", "BUY", 1.0, 300.0, 300.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "GOOGL", "SELL_RECONCILE", 1.0, 100.0, 100.0, "reconcile", 10000.0, -0.6667)
    df = load_completed_trades(con=db)
    assert df.empty  # never really closed — must not appear as a completed trade


def test_load_completed_trades_reconcile_does_not_shift_later_pairing(db):
    """The exact BKNG-shaped scenario: two buy/sell cycles for the same
    symbol, with a bogus SELL_RECONCILE sitting between them. Removing the
    reconcile must not cause the second buy to pair with the wrong sell."""
    log_trade(db, "BKNG", "BUY", 2.0, 180.0, 360.0, "TRENDING_UP", 10000.0, 0.0)          # buy 1
    log_trade(db, "BKNG", "SELL_TIME_EXIT", 2.0, 182.0, 364.0, "TRENDING_UP", 10000.0, 0.011)  # closes buy 1
    log_trade(db, "BKNG", "BUY", 2.0, 183.0, 366.0, "TRENDING_UP", 10000.0, 0.0)          # buy 2
    log_trade(db, "BKNG", "SELL_RECONCILE", 2.0, 184.0, 368.0, "reconcile", 10000.0, 0.005)  # bogus
    log_trade(db, "BKNG", "SELL_TIME_EXIT", 2.0, 176.0, 352.0, "TRENDING_UP", 10000.0, -0.037)  # closes buy 2

    df = load_completed_trades(con=db)
    assert len(df) == 2
    rows = df.sort_values("buy_ts").to_dict("records")
    assert rows[0]["entry_price"] == pytest.approx(180.0)
    assert rows[0]["pnl_pct"]     == pytest.approx(0.011)
    assert rows[1]["entry_price"] == pytest.approx(183.0)
    assert rows[1]["pnl_pct"]     == pytest.approx(-0.037)
    # every pair must be chronologically valid
    assert (df["sell_ts"] >= df["buy_ts"]).all()


def test_load_completed_trades_orphan_sell_with_no_buy_produces_no_row(db):
    log_trade(db, "MS", "SELL_STOP", 3.0, 200.0, 600.0, "TRENDING_UP", 10000.0, -0.05)
    df = load_completed_trades(con=db)
    assert df.empty


def test_load_completed_trades_still_open_position_produces_no_row(db):
    log_trade(db, "AMZN", "BUY", 2.0, 250.0, 500.0, "TRENDING_UP", 10000.0, 0.0)
    df = load_completed_trades(con=db)
    assert df.empty


def test_load_completed_trades_empty_db_returns_empty_dataframe(db):
    df = load_completed_trades(con=db)
    assert df.empty
