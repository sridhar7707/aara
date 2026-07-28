"""Tests for database.services.decision_service."""
import datetime
import pytest
from bot._main_db import init_db
from database.services.decision_service import (
    create_decision, reject_decision, approve_decision, mark_waiting_approval,
    mark_executed, complete_decision, evaluate_decision, find_open_decision_id,
    has_pending_decision, list_pending_approvals, list_approved_unexecuted,
    expire_stale_decisions, list_rejected_decisions, evaluate_rejected_decision,
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


def test_find_open_decision_id_returns_none_when_no_decision(db):
    assert find_open_decision_id(db, "AAPL") is None


def test_find_open_decision_id_finds_executed_uncompleted(db):
    did = _new_decision(db, symbol="AAPL")
    mark_executed(db, did, trade_id=1)
    assert find_open_decision_id(db, "AAPL") == did


def test_find_open_decision_id_ignores_completed(db):
    did = _new_decision(db, symbol="AAPL")
    mark_executed(db, did, trade_id=1)
    complete_decision(db, did, realized_pnl_pct=0.05)
    assert find_open_decision_id(db, "AAPL") is None


def test_find_open_decision_id_ignores_rejected(db):
    did = _new_decision(db, symbol="AAPL")
    reject_decision(db, did, rejected_by="system", reason="wash-sale guard active")
    assert find_open_decision_id(db, "AAPL") is None


def test_find_open_decision_id_picks_most_recent(db):
    d1 = _new_decision(db, symbol="AAPL")
    mark_executed(db, d1, trade_id=1)
    complete_decision(db, d1, realized_pnl_pct=0.05)
    d2 = _new_decision(db, symbol="AAPL")
    mark_executed(db, d2, trade_id=2)
    assert find_open_decision_id(db, "AAPL") == d2


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


def test_mark_waiting_approval_stores_suggested_values(db):
    did = _new_decision(db)
    mark_waiting_approval(db, did, suggested_notional=500.0, suggested_stop_loss=95.0,
                          suggested_take_profit=115.0, suggested_rr_ratio=2.5)
    row = db.execute(
        "SELECT suggested_notional, suggested_stop_loss, suggested_take_profit, suggested_rr_ratio "
        "FROM decision_log WHERE decision_id=?", (did,),
    ).fetchone()
    assert row == (500.0, 95.0, 115.0, 2.5)


def test_has_pending_decision_false_when_none(db):
    assert has_pending_decision(db, "AAPL") is False


def test_has_pending_decision_true_when_waiting_approval(db):
    did = _new_decision(db, symbol="AAPL")
    mark_waiting_approval(db, did)
    assert has_pending_decision(db, "AAPL") is True


def test_has_pending_decision_true_when_approved_not_executed(db):
    did = _new_decision(db, symbol="AAPL")
    approve_decision(db, did, approved_by="user")
    assert has_pending_decision(db, "AAPL") is True


def test_has_pending_decision_false_once_executed(db):
    did = _new_decision(db, symbol="AAPL")
    approve_decision(db, did, approved_by="user")
    mark_executed(db, did, trade_id=1)
    assert has_pending_decision(db, "AAPL") is False


def test_has_pending_decision_false_when_rejected(db):
    did = _new_decision(db, symbol="AAPL")
    reject_decision(db, did, rejected_by="user", reason="too expensive")
    assert has_pending_decision(db, "AAPL") is False


def test_list_pending_approvals_returns_waiting_only(db):
    d1 = _new_decision(db, symbol="AAPL", ai_confidence=70)
    mark_waiting_approval(db, d1, suggested_notional=500.0)
    d2 = _new_decision(db, symbol="MSFT")
    approve_decision(db, d2, approved_by="system")  # not waiting -- must not appear
    rows = list_pending_approvals(db)
    assert len(rows) == 1
    assert rows[0]["decision_id"] == d1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["suggested_notional"] == 500.0


def test_list_approved_unexecuted_returns_todays_supervised_approvals(db):
    did = _new_decision(db, symbol="AAPL")
    mark_waiting_approval(db, did, suggested_notional=500.0, suggested_stop_loss=95.0,
                          suggested_take_profit=115.0, suggested_rr_ratio=2.5)
    approve_decision(db, did, approved_by="user")
    rows = list_approved_unexecuted(db)
    assert len(rows) == 1
    assert rows[0]["decision_id"] == did
    assert rows[0]["suggested_notional"] == 500.0


def test_list_approved_unexecuted_excludes_autonomous_since_it_executes_atomically(db):
    """AUTONOMOUS mode calls approve_decision() then mark_executed() in the
    same function call — never leaves a gap where execution_status is still
    NOT_EXECUTED, so this list should never include AUTONOMOUS-mode rows."""
    did = _new_decision(db, symbol="AAPL")
    approve_decision(db, did, approved_by="system")
    mark_executed(db, did, trade_id=1)
    assert list_approved_unexecuted(db) == []


def test_expire_stale_decisions_expires_prior_day_waiting_approval(db):
    did = _new_decision(db, symbol="AAPL")
    mark_waiting_approval(db, did)
    db.execute("UPDATE decision_log SET decision_date='2020-01-01' WHERE decision_id=?", (did,))
    db.commit()
    n = expire_stale_decisions(db)
    assert n == 1
    status = db.execute("SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "EXPIRED"


def test_expire_stale_decisions_expires_prior_day_approved_unexecuted(db):
    did = _new_decision(db, symbol="AAPL")
    approve_decision(db, did, approved_by="user")
    db.execute("UPDATE decision_log SET decision_date='2020-01-01' WHERE decision_id=?", (did,))
    db.commit()
    n = expire_stale_decisions(db)
    assert n == 1
    status = db.execute("SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "EXPIRED"


def test_expire_stale_decisions_leaves_todays_decisions_alone(db):
    did = _new_decision(db, symbol="AAPL")
    mark_waiting_approval(db, did)
    n = expire_stale_decisions(db)
    assert n == 0
    status = db.execute("SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)).fetchone()[0]
    assert status == "WAITING_APPROVAL"


def test_expire_stale_decisions_leaves_executed_decisions_alone(db):
    did = _new_decision(db, symbol="AAPL")
    mark_executed(db, did, trade_id=1)
    db.execute("UPDATE decision_log SET decision_date='2020-01-01' WHERE decision_id=?", (did,))
    db.commit()
    n = expire_stale_decisions(db)
    assert n == 0


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


def test_list_rejected_decisions_excludes_approved_and_pending(db):
    d1 = _new_decision(db, symbol="AAPL")
    reject_decision(db, d1, rejected_by="system", reason="volume gate failed")
    d2 = _new_decision(db, symbol="MSFT")
    approve_decision(db, d2, approved_by="system")
    d3 = _new_decision(db, symbol="GOOGL")
    mark_waiting_approval(db, d3)
    rows = list_rejected_decisions(db)
    assert [r["decision_id"] for r in rows] == [d1]
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["decision_status"] == "SYSTEM_BLOCKED"
    assert rows[0]["gate_reason"] == "volume gate failed"


def test_list_rejected_decisions_includes_user_rejected_and_expired(db):
    d1 = _new_decision(db, symbol="AAPL")
    reject_decision(db, d1, rejected_by="user", reason="didn't like the setup")
    d2 = _new_decision(db, symbol="MSFT")
    mark_waiting_approval(db, d2)
    db.execute("UPDATE decision_log SET decision_date='2020-01-01' WHERE decision_id=?", (d2,))
    db.commit()
    expire_stale_decisions(db)
    rows = list_rejected_decisions(db)
    statuses = {r["decision_id"]: r["decision_status"] for r in rows}
    assert statuses[d1] == "USER_REJECTED"
    assert statuses[d2] == "EXPIRED"


def test_list_rejected_decisions_most_recent_first(db):
    d1 = _new_decision(db, symbol="AAPL")
    reject_decision(db, d1, rejected_by="system", reason="a")
    d2 = _new_decision(db, symbol="MSFT")
    reject_decision(db, d2, rejected_by="system", reason="b")
    rows = list_rejected_decisions(db)
    assert [r["decision_id"] for r in rows] == [d2, d1]


def test_evaluate_rejected_decision_no_such_decision(db):
    result = evaluate_rejected_decision(db, 99999)
    assert result["forward_return"] is None
    assert "no such decision" in result["error"]


def test_evaluate_rejected_decision_rejects_non_rejected_status(db):
    did = _new_decision(db)
    approve_decision(db, did, approved_by="system")
    result = evaluate_rejected_decision(db, did)
    assert result["forward_return"] is None
    assert "not rejected" in result["error"]


def test_evaluate_rejected_decision_window_not_yet_complete(db):
    """A decision rejected today, with the default 10-day window, can't have
    a known outcome yet -- must say so explicitly rather than compute a
    partial/misleading return."""
    did = _new_decision(db, symbol="AAPL")
    reject_decision(db, did, rejected_by="system", reason="rs gate failed")
    result = evaluate_rejected_decision(db, did)
    assert result["forward_return"] is None
    assert result["error"] == "window not yet complete"


def test_evaluate_rejected_decision_uses_expected_holding_period_as_window(db):
    """A decision rejected long enough ago that even a short expected_holding_period
    window has elapsed should proceed past the window check (network call to
    yfinance may fail in CI -- that's fine, this only checks the window gate)."""
    did = _new_decision(db, symbol="AAPL", expected_holding_period=3)
    reject_decision(db, did, rejected_by="system", reason="rs gate failed")
    old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    db.execute("UPDATE decision_log SET decision_date=? WHERE decision_id=?", (old_date, did))
    db.commit()
    result = evaluate_rejected_decision(db, did)
    assert result.get("error") != "window not yet complete"


def test_evaluate_rejected_decision_no_price_recorded(db):
    did = create_decision(db, symbol="AAPL", price_at_decision=0.0, portfolio_value_at_time=10000.0)
    reject_decision(db, did, rejected_by="system", reason="rs gate failed")
    old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    db.execute("UPDATE decision_log SET decision_date=? WHERE decision_id=?", (old_date, did))
    db.commit()
    result = evaluate_rejected_decision(db, did)
    assert result["forward_return"] is None
    assert "no price recorded" in result["error"]
