"""Regression coverage for bot._main_positions._signal_sell fill-state handling.

Critical invariant (post zero-fill fix): a SELL with total filled_qty == 0
must NOT
  - write a completed SELL trades row,
  - delete position_state,
  - report success (_signal_sell must return False).

A fill > 0 must still persist the SELL with the broker order_id and close
position_state. Partial fills follow the pre-existing contract (recorded as a
close for the ordered quantity; the remainder is left for
_reconcile_positions -- see wait_for_fill's own docstring), which this fix
does not change.
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
        "SELECT entry_price, high_water_mark, atr_at_entry, shares "
        "FROM position_state WHERE symbol=?",
        (symbol,),
    ).fetchone()


def test_signal_sell_zero_fill_writes_no_trade_and_keeps_position_state(db):
    _seed_position(db)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(limit_submit=True, limit_fill=0.0)

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, holding_days=40, pool=None,
    )

    assert result is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before


def test_signal_sell_full_fill_persists_trade_with_order_id_and_deletes_position_state(db):
    _seed_position(db)
    client = _FakeClient(limit_submit=True, limit_fill=5.0)

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, holding_days=40, pool=None,
    )

    assert result is True
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL_TIME_EXIT"
    assert shares == 5.0
    assert oid == client.limit_oid
    assert _pos_row(db, "GOOGL") is None


def test_signal_sell_partial_fill_follows_existing_reconcile_contract(db):
    """Pre-existing semantics: any fill > 0 records a close for the ordered
    quantity and deletes position_state; the unfilled remainder is left for
    _reconcile_positions. This fix does not change that -- only the
    zero-fill case."""
    _seed_position(db)
    client = _FakeClient(limit_submit=True, limit_fill=2.0)  # 2 of 5

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="signal", pnl_pct=0.01, entry_price=110.0, holding_days=10, pool=None,
    )

    assert result is True
    rows = _trades(db, "GOOGL")
    assert len(rows) == 1
    action, shares, oid = rows[0]
    assert action == "SELL"
    assert shares == 5.0            # ordered qty, per the existing contract
    assert oid == client.limit_oid
    assert _pos_row(db, "GOOGL") is None


def test_signal_sell_stop_escalation_zero_fill_both_legs_returns_false_no_persistence(db):
    _seed_position(db)
    before = _pos_row(db, "GOOGL")
    client = _FakeClient(
        limit_submit=True, limit_fill=0.0, market_submit=True, market_fill=0.0,
    )

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        is_from_stop=True, reason="stop-loss", pnl_pct=-0.06, entry_price=110.0, pool=None,
    )

    assert result is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before


def test_signal_sell_stop_escalation_market_fills_full_persists_stop_row(db):
    _seed_position(db)
    client = _FakeClient(
        limit_submit=True, limit_fill=0.0, market_submit=True, market_fill=5.0,
    )

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        is_from_stop=True, reason="stop-loss", pnl_pct=-0.06, entry_price=110.0, pool=None,
    )

    assert result is True
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

    result = mp._signal_sell(
        db, client, "GOOGL", 5.0, 100.0, "TRENDING_UP", 10_000.0,
        reason="time-exit", pnl_pct=-0.03, entry_price=110.0, pool=None,
    )

    assert result is False
    assert _trades(db, "GOOGL") == []
    assert _pos_row(db, "GOOGL") == before
