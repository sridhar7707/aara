"""ADR-085: the stock bot neither adopts nor trades ETF-overlay holdings on the shared paper account."""
import sqlite3
from types import SimpleNamespace

from bot._main_positions import _reconcile_positions
from config import ETF_OVERLAY_SYMBOLS


def _con():
    con = sqlite3.connect(":memory:")
    con.execute("""CREATE TABLE position_state (
        symbol TEXT PRIMARY KEY, entry_price REAL, high_water_mark REAL,
        atr_at_entry REAL, opened_at TEXT, shares REAL DEFAULT 0.0)""")
    con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol TEXT, action TEXT, shares REAL, "
                "price REAL, notional REAL, timestamp TEXT, regime TEXT, portfolio_value REAL, pnl_pct REAL)")
    return con


def test_etf_overlay_holding_is_not_adopted_into_stock_position_state():
    con = _con()
    pos = {"XLK": SimpleNamespace(symbol="XLK", qty=3.0, avg_entry_price=200.0, market_value=600.0),
           "AAPL": SimpleNamespace(symbol="AAPL", qty=2.0, avg_entry_price=150.0, market_value=300.0)}
    _reconcile_positions(con, pos, portfolio_value=1_000.0)
    adopted = {r[0] for r in con.execute("SELECT symbol FROM position_state")}
    assert "AAPL" in adopted                 # a genuine stock position is still adopted
    assert "XLK" not in adopted              # the ETF overlay's holding is not


def test_overlay_symbols_are_defined_once():
    assert {"XLK", "QQQ", "GLD"} <= set(ETF_OVERLAY_SYMBOLS)
