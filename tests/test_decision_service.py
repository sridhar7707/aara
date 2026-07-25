"""Tests for database.services.decision_service."""
import pytest
from bot._main_db import init_db
from database.services.decision_service import (
    create_decision, reject_decision, approve_decision, mark_waiting_approval,
    mark_executed, complete_decision, evaluate_decision,
)


@pytest.fixture
def db():
    """In-memory DB with the real decision_log/trades schema (via init_db)."""
    return init_db(":memory:")


def _new_decision(db, **kwargs):
    defaults = dict(symbol="AAPL", price_at_decision=150.0, portfolio_value_at_time=10000.0)
    defaults.update(kwargs)
    return create_decision(db, **defaults)


def test_create_decision_defaults(db):
    did = _new_decision(db, decision_reason="AI momentum + earnings", ai_confidence=78)
    row = db.execute(
        "SELECT symbol, decision_type, decision_status, execution_status, outcome_status, "
        "reasoning, decision_reason, ai_confidence, trade_id "
        "FROM decision_log WHERE decision_id=?", (did,),
    ).fetchone()
    assert row[0] == "AAPL"
    assert row[1] == "BUY"
    assert row[2] == "CREATED"
    assert row[3] == "NOT_EXECUTED"
    assert row[4] == "UNKNOWN"          # never computed at creation time
    assert row[5] == "AI momentum + earnings"   # legacy `reasoning` column kept in sync
    assert row[6] == "AI momentum + earnings"   # new `decision_reason` column
    assert row[7] == 78
    assert row[8] is None                # no trade yet


def test_reject_decision_system_blocked(db):
    did = _new_decision(db)
    reject_decision(db, did, rejected_by="system", reason="wash-sale guard active")
    row = db.execute(
        "SELECT decision_status, execution_status, gate_reason FROM decision_log WHERE decision_id=?",
        (did,),
    ).fetchone()
    assert row[0] == "SYSTEM_BLOCKED"
    assert row[1] == "NOT_EXECUTED"
    assert row[2] == "wash-sale guard active"


def test_reject_decision_user_rejected(db):
    did = _new_decision(db)
    reject_decision(db, did, rejected_by="user", reason="Too expensive")
    status = db.execute("SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "USER_REJECTED"


def test_mark_waiting_approval(db):
    did = _new_decision(db)
    mark_waiting_approval(db, did)
    status = db.execute("SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "WAITING_APPROVAL"


def test_approve_decision_does_not_execute(db):
    did = _new_decision(db)
    approve_decision(db, did, approved_by="system")
    row = db.execute(
        "SELECT decision_status, execution_status FROM decision_log WHERE decision_id=?", (did,),
    ).fetchone()
    assert row[0] == "APPROVED"
    assert row[1] == "NOT_EXECUTED"      # approval alone never executes


def test_mark_executed_links_trade(db):
    did = _new_decision(db)
    approve_decision(db, did, approved_by="system")
    mark_executed(db, did, trade_id=99, quantity_changed=3.5)
    row = db.execute(
        "SELECT execution_status, trade_id, quantity_changed, executed_at FROM decision_log WHERE decision_id=?",
        (did,),
    ).fetchone()
    assert row[0] == "EXECUTED"
    assert row[1] == 99
    assert row[2] == pytest.approx(3.5)
    assert row[3] is not None


def test_complete_decision_win(db):
    did = _new_decision(db)
    mark_executed(db, did, trade_id=1)
    complete_decision(db, did, realized_pnl_pct=0.08)
    row = db.execute(
        "SELECT outcome_status, outcome_known_at FROM decision_log WHERE decision_id=?", (did,),
    ).fetchone()
    assert row[0] == "WIN"
    assert row[1] is not None


def test_complete_decision_loss(db):
    did = _new_decision(db)
    mark_executed(db, did, trade_id=1)
    complete_decision(db, did, realized_pnl_pct=-0.05)
    status = db.execute("SELECT outcome_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "LOSS"


def test_complete_decision_neutral(db):
    did = _new_decision(db)
    mark_executed(db, did, trade_id=1)
    complete_decision(db, did, realized_pnl_pct=0.0)
    status = db.execute("SELECT outcome_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "NEUTRAL"


def test_evaluate_decision_without_trade_returns_error(db):
    did = _new_decision(db)
    result = evaluate_decision(db, did)
    assert "error" in result


def test_evaluate_decision_without_completion_returns_error(db):
    did = _new_decision(db)
    mark_executed(db, did, trade_id=1)
    # trade exists via mark_executed's trade_id, but outcome_known_at unset (complete_decision not called)
    result = evaluate_decision(db, did)
    assert "error" in result


def test_evaluate_decision_writes_nothing_to_db(db):
    """evaluate_decision is read-only — no decision_log columns exist for
    spy_return/alpha, so there is nothing for it to write back."""
    did = _new_decision(db)
    mark_executed(db, did, trade_id=1)
    complete_decision(db, did, realized_pnl_pct=0.05)
    before = dict(zip(
        [c[0] for c in db.execute("SELECT * FROM decision_log WHERE decision_id=?", (did,)).description],
        db.execute("SELECT * FROM decision_log WHERE decision_id=?", (did,)).fetchone(),
    ))
    evaluate_decision(db, did)  # network call to yfinance may fail in CI — that's fine, still read-only
    after = dict(zip(
        [c[0] for c in db.execute("SELECT * FROM decision_log WHERE decision_id=?", (did,)).description],
        db.execute("SELECT * FROM decision_log WHERE decision_id=?", (did,)).fetchone(),
    ))
    assert before == after
