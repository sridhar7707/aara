"""Tests for bot._main_decisions."""
import pytest
from bot._main_db import init_db, log_trade
from bot._main_decisions import create_buy_decision, backfill_decisions_from_trades


@pytest.fixture
def db():
    return init_db(":memory:")


def test_create_buy_decision_creates_row(db):
    did = create_buy_decision(db, "AAPL", 150.0, 10000.0, None, 0.70, 0.65, 0.30, 0.55, "TRENDING_UP")
    row = db.execute(
        "SELECT symbol, decision_type, decision_status FROM decision_log WHERE decision_id=?", (did,),
    ).fetchone()
    assert row == ("AAPL", "BUY", "CREATED")


# --- backfill_decisions_from_trades ---

def test_backfill_simple_buy_sell_pair(db):
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "AAPL", "SELL", 5.0, 110.0, 550.0, "TRENDING_UP", 10000.0, 0.10)
    created = backfill_decisions_from_trades(db)
    assert created == 1
    row = db.execute(
        "SELECT decision_status, execution_status, outcome_status, trade_id FROM decision_log WHERE symbol='AAPL'",
    ).fetchone()
    assert row[0] == "APPROVED"
    assert row[1] == "EXECUTED"
    assert row[2] == "WIN"
    assert row[3] is not None


def test_backfill_still_open_position_has_unknown_outcome(db):
    log_trade(db, "MSFT", "BUY", 2.0, 300.0, 600.0, "TRENDING_UP", 10000.0, 0.0)
    created = backfill_decisions_from_trades(db)
    assert created == 1
    row = db.execute(
        "SELECT outcome_status, outcome_known_at FROM decision_log WHERE symbol='MSFT'",
    ).fetchone()
    assert row[0] == "UNKNOWN"
    assert row[1] is None


def test_backfill_sell_reconcile_is_not_treated_as_a_real_close(db):
    """The exact 2026-07-07 pattern: BUY -> bogus SELL_RECONCILE -> real SELL.
    The reconcile must not be what closes the decision; the real sell must."""
    log_trade(db, "GOOGL", "BUY", 1.0, 300.0, 300.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "GOOGL", "SELL_RECONCILE", 1.0, 100.0, 100.0, "reconcile", 10000.0, -0.6667)
    log_trade(db, "GOOGL", "SELL_TIME_EXIT", 1.0, 330.0, 330.0, "TRENDING_UP", 10000.0, 0.10)
    created = backfill_decisions_from_trades(db)
    assert created == 1
    row = db.execute(
        "SELECT outcome_status, trade_id FROM decision_log WHERE symbol='GOOGL'",
    ).fetchone()
    assert row[0] == "WIN"  # from the real +10% sell, not the fake -66.67% reconcile
    buy_id = db.execute(
        "SELECT id FROM trades WHERE symbol='GOOGL' AND action='BUY'"
    ).fetchone()[0]
    assert row[1] == buy_id  # trade_id links to the executing BUY, not the SELL


def test_backfill_sell_reconcile_with_no_later_real_sell_stays_open(db):
    """A ghost position: bought, falsely reconciled, never actually re-sold in
    the data. Must stay UNKNOWN, not be marked closed using the fake reconcile."""
    log_trade(db, "SNOW", "BUY", 1.0, 250.0, 250.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "SNOW", "SELL_RECONCILE", 1.0, 260.0, 260.0, "reconcile", 10000.0, 0.04)
    created = backfill_decisions_from_trades(db)
    assert created == 1
    row = db.execute(
        "SELECT outcome_status, outcome_known_at FROM decision_log WHERE symbol='SNOW'",
    ).fetchone()
    assert row[0] == "UNKNOWN"
    assert row[1] is None


def test_backfill_orphan_sell_with_no_matching_buy_is_skipped(db):
    """A SELL with no BUY on record (predates trades.db history) must not crash
    and must not create a decision_log row."""
    log_trade(db, "MS", "SELL_STOP", 3.0, 200.0, 600.0, "TRENDING_UP", 10000.0, -0.05)
    created = backfill_decisions_from_trades(db)
    assert created == 0
    row = db.execute("SELECT COUNT(*) FROM decision_log WHERE symbol='MS'").fetchone()
    assert row[0] == 0


def test_backfill_two_cycles_same_symbol(db):
    """Symbol bought, sold, and bought again — two separate decisions."""
    log_trade(db, "NKE", "BUY", 10.0, 42.0, 420.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "NKE", "SELL", 10.0, 43.0, 430.0, "TRENDING_UP", 10000.0, 0.024)
    log_trade(db, "NKE", "BUY", 10.0, 44.0, 440.0, "TRENDING_UP", 10000.0, 0.0)
    created = backfill_decisions_from_trades(db)
    assert created == 2
    rows = db.execute(
        "SELECT outcome_status FROM decision_log WHERE symbol='NKE' ORDER BY decision_id",
    ).fetchall()
    assert rows[0][0] == "WIN"
    assert rows[1][0] == "UNKNOWN"


def test_backfill_is_idempotent(db):
    log_trade(db, "AAPL", "BUY", 5.0, 100.0, 500.0, "TRENDING_UP", 10000.0, 0.0)
    log_trade(db, "AAPL", "SELL", 5.0, 110.0, 550.0, "TRENDING_UP", 10000.0, 0.10)
    first = backfill_decisions_from_trades(db)
    second = backfill_decisions_from_trades(db)
    assert first == 1
    assert second == 0
    n = db.execute("SELECT COUNT(*) FROM decision_log WHERE symbol='AAPL'").fetchone()[0]
    assert n == 1


def test_backfill_skips_trades_already_linked_by_live_wiring(db):
    """A decision created live via create_buy_decision + mark_executed (Commit
    4 path) must not get a second, duplicate decision_log row from backfill."""
    from bot._main_decisions import create_buy_decision
    from database.services.decision_service import mark_executed
    trade_id = log_trade(db, "BAC", "BUY", 8.0, 60.0, 480.0, "TRENDING_UP", 10000.0, 0.0)
    did = create_buy_decision(db, "BAC", 60.0, 10000.0, None, 0.7, 0.6, 0.3, 0.55, "TRENDING_UP")
    mark_executed(db, did, trade_id=trade_id)
    created = backfill_decisions_from_trades(db)
    assert created == 0
    n = db.execute("SELECT COUNT(*) FROM decision_log WHERE symbol='BAC'").fetchone()[0]
    assert n == 1
