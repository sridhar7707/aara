"""Tests for dashboard.components.pending_approvals."""
import pytest

import dashboard.data as ddata
from bot._main_db import init_db
from database.services.decision_service import create_decision, mark_waiting_approval, approve_decision
import dashboard.components.pending_approvals as pa


@pytest.fixture
def dash_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "pa_test.db")
    con = init_db(db_path)
    monkeypatch.setattr(ddata, "DB_PATH", db_path)
    return con


def test_empty_state_when_no_pending(dash_db):
    html = pa.render_pending_approvals()
    assert "No decisions awaiting approval" in html


def test_lists_waiting_approval_decisions(dash_db):
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0, ai_confidence=65,
                          decision_reason="XGB 70%, LSTM 60%")
    mark_waiting_approval(dash_db, did, suggested_notional=500.0)
    html = pa.render_pending_approvals()
    assert "AAPL" in html
    assert "65%" in html
    assert "$500.00" in html
    assert "1 awaiting a decision" in html


def test_excludes_already_approved_decisions(dash_db):
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    approve_decision(dash_db, did, approved_by="system")
    html = pa.render_pending_approvals()
    assert "No decisions awaiting approval" in html


def test_do_approve_decision_flips_status(dash_db):
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    mark_waiting_approval(dash_db, did)
    result = pa.do_approve_decision(str(did))
    assert "Approved" in result
    status = dash_db.execute(
        "SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)
    ).fetchone()[0]
    assert status == "APPROVED"


def test_on_approve_click_handles_gr_number_float_input(dash_db):
    """Regression test: gr.Number always hands the click handler a float
    (e.g. 19.0, never the int 19), and str(19.0) == "19.0" -- a real bug
    where do_approve_decision's int("19.0") raised ValueError and silently
    fell through to "Invalid decision ID", found via manual Playwright
    verification (unit tests using str(int) inputs never exercised this)."""
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    mark_waiting_approval(dash_db, did)
    status_html, _table_html = pa.on_approve_click(float(did))
    assert "Approved" in status_html
    assert dash_db.execute(
        "SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)
    ).fetchone()[0] == "APPROVED"


def test_on_reject_click_handles_gr_number_float_input(dash_db):
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    mark_waiting_approval(dash_db, did)
    status_html, _table_html = pa.on_reject_click(float(did), "no thanks")
    assert "Rejected" in status_html
    assert dash_db.execute(
        "SELECT decision_status FROM decision_log WHERE decision_id=?", (did,)
    ).fetchone()[0] == "USER_REJECTED"


def test_do_approve_decision_never_touches_execution_status(dash_db):
    """The dashboard must never place an order itself -- approving only
    flips decision_status; execution_status stays NOT_EXECUTED until the
    bot's own loop picks it up."""
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    mark_waiting_approval(dash_db, did)
    pa.do_approve_decision(str(did))
    row = dash_db.execute(
        "SELECT execution_status, trade_id FROM decision_log WHERE decision_id=?", (did,)
    ).fetchone()
    assert row[0] == "NOT_EXECUTED"
    assert row[1] is None


def test_do_reject_decision_flips_status_with_reason(dash_db):
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    mark_waiting_approval(dash_db, did)
    result = pa.do_reject_decision(str(did), "Too risky right now")
    assert "Rejected" in result
    row = dash_db.execute(
        "SELECT decision_status, gate_reason FROM decision_log WHERE decision_id=?", (did,)
    ).fetchone()
    assert row[0] == "USER_REJECTED"
    assert row[1] == "Too risky right now"


def test_do_approve_decision_rejects_invalid_id(dash_db):
    result = pa.do_approve_decision("not-a-number")
    assert "Invalid decision ID" in result


def test_do_approve_decision_rejects_unknown_id(dash_db):
    result = pa.do_approve_decision("99999")
    assert "not found" in result


def test_do_approve_decision_rejects_non_pending_decision(dash_db):
    """A decision that's already EXECUTED (or otherwise resolved) must not
    be silently re-approved."""
    did = create_decision(dash_db, "AAPL", 100.0, 10000.0)
    approve_decision(dash_db, did, approved_by="system")
    result = pa.do_approve_decision(str(did))
    assert "not awaiting approval" in result
