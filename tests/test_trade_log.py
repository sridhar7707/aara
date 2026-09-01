"""Regression coverage for bot.db.trade_log.log_trade().

Focus: log_trade must accept a uuid.UUID order_id (alpaca-py 0.43.5 returns
Order.id as uuid.UUID) and persist it as a plain string into the TEXT
trades.order_id column, and must keep accepting order_id=None.
"""
import uuid

import pytest

from bot._main_db import init_db, log_trade


@pytest.fixture
def db():
    return init_db(":memory:")


def _row(db):
    return db.execute(
        "SELECT symbol, action, order_id, typeof(order_id) FROM trades ORDER BY id DESC LIMIT 1"
    ).fetchone()


def test_log_trade_accepts_uuid_order_id_and_stores_str(db):
    oid = uuid.uuid4()
    rowid = log_trade(
        db, "AAPL", "SELL_STOP", 5.0, 110.0, 550.0, "TRENDING_UP", 10_000.0, -0.05,
        entry_price=100.0, order_id=oid,
    )
    assert rowid is not None

    symbol, action, stored_oid, oid_type = _row(db)
    assert (symbol, action) == ("AAPL", "SELL_STOP")
    assert stored_oid == str(oid)
    assert isinstance(stored_oid, str)
    assert oid_type == "text"


def test_log_trade_accepts_none_order_id(db):
    rowid = log_trade(
        db, "MSFT", "BUY", 2.0, 200.0, 400.0, "TRENDING_UP", 10_000.0, 0.0,
        order_id=None,
    )
    assert rowid is not None

    _, _, stored_oid, oid_type = _row(db)
    assert stored_oid is None
    assert oid_type == "null"


def test_log_trade_accepts_plain_str_order_id_unchanged(db):
    log_trade(
        db, "NKE", "BUY", 1.0, 50.0, 50.0, "TRENDING_UP", 10_000.0, 0.0,
        order_id="already-a-string-id",
    )
    _, _, stored_oid, _ = _row(db)
    assert stored_oid == "already-a-string-id"
