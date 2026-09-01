"""Regression coverage for bot._main_positions._signal_sell fill-state handling.

Critical invariant (post zero-fill fix): a SELL with total filled_qty == 0
must NOT
  - write a completed SELL trades row,
  - delete position_state,
  - report a sale (_signal_sell must return (False, False)).

_signal_sell returns (sold, fully_closed):
  - full fill  -> (True, True):  SELL row for the actual filled qty, position_state deleted.
  - partial    -> (True, False): SELL row for the ACTUAL filled qty, position_state kept
                                 with the unfilled remainder (entry_price / opened_at /
                                 high_water_mark / atr_at_entry preserved). Caller must NOT
                                 record a decision outcome yet.
  - zero fill  -> (False, False): nothing persisted, position_state untouched.
"""
import uuid

import pytest
from unittest.mock import MagicMock

from bot._main_db import init_db
from bot import _main_positions as mp


@pytest.fixture
def db():
    return init_db(":memory:")


@pytest.fixture(autouse=True)
def _silence_side_effects(monkeypatch):
    # Audit-only collaborators that need tables/network not under test here.
    monkeypatch.setattr(mp, "_journal_close", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_rec_action", lambda *a, **k: None)
    monkeypatch.setattr(mp, "tg", MagicMock())


class _FakeClient:
    """Limit/market submit -> dict|None; wait_for_fill -> configured float."""

    def __init__(self, *, limit_submit=True, limit_fill=0.0,
                 market_submit=True, market_fill=0.0):
        self._limit_submit = limit_submit
        self._limit_fill = float(limit_fill)
        self._market_submit = market_submit
        self._market_fill = float(market_fill)
        self.limit_oid = str(uuid.uuid4())
        self.market_oid = str(uuid.uuid4())

    def sell(self, symbol, qty=None, limit_price=None):
        if not self._limit_submit:
            return None
        return {"order_id": self.limit_oid, "symbol": symbol, "side": "sell", "qty": qty}

    def sell_market(self, symbol, qty):
        if not self._market_submit:
            return None
        return {"order_id": self.market_oid, "symbol": symbol, "side": "sell", "qty": qty}

    def wait_for_fill(self, order_id, timeout_secs=15):
        if order_id == self.market_oid:
            return self._market_fill
        return self._limit_fill


def _seed_position(db, symbol="GOOGL", entry=110.0, hwm=120.0, atr=1.0, shares=5.0):
    mp._upsert_position_state(db, symbol, entry, hwm, atr, shares)


def _trades(db, symbol):
    return db.execute(
        "SELECT action, shares, order_id FROM trades WHERE symbol=?", (symbol,)
    ).fetchall()


def _pos_row(db, symbol):
    return db.execute(
        "SELECT entry_price, high_water_mark, atr_at_entry, shares, opened_at "
        "FROM position_state WHERE symbol=?",
        (symbol,),
    ).fetchone()


def test_signal_sell_zero_fill_writes_no_trade_and_keeps_position_state(db):
    _seed_position(db)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(limit_submit=True, limit_fill=0.0)

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, holding_days=40, pool=None,
    )

    assert sold is False
    assert fully_closed is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before


def test_signal_sell_full_fill_persists_trade_with_order_id_and_deletes_position_state(db):
    _seed_position(db)
    client = _FakeClient(limit_submit=True, limit_fill=5.0)

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, holding_days=40, pool=None,
    )

    assert sold is True
    assert fully_closed is True
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL_TIME_EXIT"
    assert shares == 5.0
    assert oid == client.limit_oid
    assert _pos_row(db, "GOOGL") is None


def test_signal_sell_full_fill_records_actual_filled_quantity(db):
    """Broker reports a filled qty slightly under the ordered qty (rounding /
    fractional dust) but within the 0.001 epsilon -- still a full close, and
    the trade row must carry the ACTUAL filled quantity, not the ordered one."""
    _seed_position(db, shares=5.0)
    client = _FakeClient(limit_submit=True, limit_fill=4.9995)  # within epsilon of 5

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="signal", pnl_pct=0.02, entry_price=110.0, holding_days=10, pool=None,
    )

    assert (sold, fully_closed) == (True, True)
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, _oid = rows[0]
    assert action == "SELL"
    assert shares == pytest.approx(4.9995)
    assert _pos_row(db, "GOOGL") is None


def test_signal_sell_partial_fill_records_filled_qty_and_keeps_remainder(db):
    """A partial fill records a SELL for the ACTUAL filled quantity and keeps
    position_state alive with the unfilled remainder; entry_price and
    opened_at are preserved so holding-period / cost-basis math still works.
    The result reports a real sale that did NOT fully close the position."""
    _seed_position(db, entry=110.0, hwm=120.0, atr=1.0, shares=5.0)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(limit_submit=True, limit_fill=2.0)  # 2 of 5

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="signal", pnl_pct=0.01, entry_price=110.0, holding_days=10, pool=None,
    )

    assert sold is True
    assert fully_closed is False
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL"
    assert shares == pytest.approx(2.0)      # actual fill, never the ordered 5
    assert oid == client.limit_oid
    after = _pos_row(db, "GOOGL")
    assert after is not None
    entry_price, _hwm, _atr, rem_shares, opened_at = after
    assert rem_shares == pytest.approx(3.0)
    assert entry_price == pytest.approx(110.0)          # preserved
    assert opened_at == before[4]                        # preserved


def test_signal_sell_partial_stop_escalation_sums_both_legs_and_keeps_remainder(db):
    """Stop path: limit leg fills 2, market escalation fills 1 -> one SELL_STOP
    row for the combined 3 shares, remainder 2 left in position_state."""
    _seed_position(db, shares=5.0)
    client = _FakeClient(
        limit_submit=True, limit_fill=2.0, market_submit=True, market_fill=1.0,
    )

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        is_from_stop=True, reason="stop-loss", pnl_pct=-0.06, entry_price=110.0, pool=None,
    )

    assert (sold, fully_closed) == (True, False)
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL_STOP"
    assert shares == pytest.approx(3.0)
    assert oid == client.market_oid
    after = _pos_row(db, "GOOGL")
    assert after is not None
    assert after[3] == pytest.approx(2.0)


def test_signal_sell_stop_escalation_zero_fill_both_legs_returns_false_no_persistence(db):
    _seed_position(db)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(
        limit_submit=True, limit_fill=0.0, market_submit=True, market_fill=0.0,
    )

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        is_from_stop=True, reason="stop-loss", pnl_pct=-0.06, entry_price=110.0, pool=None,
    )

    assert sold is False
    assert fully_closed is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before


def test_signal_sell_stop_escalation_market_fills_full_persists_stop_row(db):
    _seed_position(db)
    client = _FakeClient(
        limit_submit=True, limit_fill=0.0, market_submit=True, market_fill=5.0,
    )

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        is_from_stop=True, reason="stop-loss", pnl_pct=-0.06, entry_price=110.0, pool=None,
    )

    assert sold is True
    assert fully_closed is True
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL_STOP"
    assert oid == client.market_oid   # broker id of the fill that actually executed
    assert _pos_row(db, "GOOGL") is None


def test_signal_sell_submit_failure_returns_false_no_persistence(db):
    _seed_position(db)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(limit_submit=False)

    sold, fully_closed = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, pool=None,
    )

    assert sold is False
    assert fully_closed is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before


def test_trim_position_partial_fill_records_filled_qty_and_decrements_state(db):
    """_trim_position logs only the ACTUAL filled quantity and decrements
    position_state by that amount -- never by the ordered trim quantity."""
    _seed_position(db, entry=110.0, hwm=120.0, atr=1.0, shares=10.0)
    client = _FakeClient(limit_submit=True, limit_fill=1.5)  # asked 4, filled 1.5

    ok = mp._trim_position(
        db, client, "GOOGL", 4.0, 100.0, "TRENDING_UP", 10_000.0,
        pnl_pct=0.05, entry_price=110.0, pool=None,
    )

    assert ok is True
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, _oid = rows[0]
    assert action == "SELL_TRIM"
    assert shares == pytest.approx(1.5)
    after = _pos_row(db, "GOOGL")
    assert after is not None
    assert after[3] == pytest.approx(8.5)   # 10 - 1.5


def test_trim_position_zero_fill_leaves_everything_unchanged(db):
    _seed_position(db, shares=10.0)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(limit_submit=True, limit_fill=0.0)

    ok = mp._trim_position(
        db, client, "GOOGL", 4.0, 100.0, "TRENDING_UP", 10_000.0,
        pnl_pct=0.05, entry_price=110.0, pool=None,
    )

    assert ok is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before
