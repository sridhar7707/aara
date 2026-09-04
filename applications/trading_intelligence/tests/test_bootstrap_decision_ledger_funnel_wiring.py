"""Wave 3D: composition-root wiring for the Decision Ledger funnel
summary (ADR-064, no scope expansion).

``_build_performance_learning_screen`` now also derives the count-only
``LedgerFunnelSummary`` from the SAME already-materialized Wave 3B
inspection (no extra read, no new source) and attaches it to the screen.
"""
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters import trust_ledger_snapshot as _tls


@pytest.fixture(autouse=True)
def _clean_runtime_ledger_snapshot():
    for leftover in list(_tls._RUNTIME_DIR.glob("*trust_ledger_snapshot*")):
        try:
            leftover.unlink()
        except OSError:
            pass
    yield


from applications.trading_intelligence.bootstrap import (
    _build_performance_learning_screen,
)
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    LedgerFunnelSummary,
)

_LEDGER_DDL = """
CREATE TABLE candidate_evaluation_events (
    sequence_number           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_event_id        TEXT NOT NULL UNIQUE,
    timestamp                 TEXT NOT NULL,
    asset                     TEXT NOT NULL,
    screening_version         TEXT NOT NULL,
    screening_results         TEXT NOT NULL,
    data_available            INTEGER NOT NULL,
    required_models_available  INTEGER NOT NULL,
    evaluation_requested      INTEGER NOT NULL,
    evaluation_completed      INTEGER NOT NULL,
    record_hash               TEXT NOT NULL,
    previous_record_hash      TEXT NOT NULL
);
CREATE TABLE decision_events (
    sequence_number        INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id            TEXT NOT NULL UNIQUE,
    candidate_event_id     TEXT NOT NULL,
    timestamp              TEXT NOT NULL,
    asset                  TEXT NOT NULL,
    action                 TEXT NOT NULL,
    event_type             TEXT NOT NULL,
    portfolio_snapshot     TEXT NOT NULL,
    market_context         TEXT NOT NULL,
    model_outputs          TEXT NOT NULL,
    risk_checks            TEXT NOT NULL,
    final_confidence       REAL NOT NULL,
    deployment_manifest_id TEXT NOT NULL,
    intent                 TEXT NOT NULL,
    data_completeness      TEXT NOT NULL,
    record_hash            TEXT NOT NULL,
    previous_record_hash   TEXT NOT NULL
);
"""


def _make_ledger_db(*, candidates, decisions):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(_LEDGER_DDL)
    for c in candidates:
        conn.execute(
            "INSERT INTO candidate_evaluation_events "
            "(candidate_event_id,timestamp,asset,screening_version,screening_results,"
            "data_available,required_models_available,evaluation_requested,"
            "evaluation_completed,record_hash,previous_record_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", c)
    for d in decisions:
        conn.execute(
            "INSERT INTO decision_events "
            "(decision_id,candidate_event_id,timestamp,asset,action,event_type,"
            "portfolio_snapshot,market_context,model_outputs,risk_checks,"
            "final_confidence,deployment_manifest_id,intent,data_completeness,"
            "record_hash,previous_record_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", d)
    conn.commit()
    conn.close()
    return path


def _cand(cid, seq, completed=1):
    return (cid, f"2026-07-29T14:{seq:02d}:00+00:00", "BLK", "screen_universe_v1",
            '{"rank":3,"composite_score":0.62}', 1, 0, 1, completed, "h", "p")


def _dec(did, cid, seq, action, event_type, risk_checks):
    return (did, cid, f"2026-07-30T13:{seq:02d}:00+00:00", "BLK", action, event_type,
            "{}", '{"regime":"BULL"}',
            '{"xgboost":{"signal":"BUY","confidence":0.57}}', risk_checks,
            0.56, "MFE-1", '{"primary_intent":"NO_ACTION"}', '{"status":"COMPLETE"}',
            "h", "p")


_REJ = '{"gate_trace":[{"gate":"volume","passed":false,"detail":"d"}]}'
_ENTRY = '{"gate_trace":[{"gate":"all_entry_gates","passed":true,"detail":"x"}]}'
_HOLD = '{"exit_reason":"no exit condition met"}'


def test_no_ledger_snapshot_leaves_the_funnel_summary_none():
    screen = _build_performance_learning_screen(None, ledger_db_path=None)
    assert screen.ledger_available is False
    assert screen.ledger_funnel_summary is None
    assert screen.ledger_funnel_available is False


def test_valid_snapshot_attaches_a_matching_funnel_summary():
    cands = [_cand("C1", 1), _cand("C2", 2), _cand("C3", 3), _cand("C4", 4),
             _cand("C5", 5, completed=0)]
    decs = [
        _dec("D1", "C1", 1, "BUY", "EXECUTED", _ENTRY),
        _dec("D2", "C2", 2, "HOLD", "QUALIFIED_REJECTION", _HOLD),
        _dec("D3", "C3", 3, "REJECT", "QUALIFIED_REJECTION", _REJ),
        _dec("D4", "C4", 4, "REJECT", "QUALIFIED_REJECTION", _REJ),
    ]
    path = _make_ledger_db(candidates=cands, decisions=decs)
    try:
        screen = _build_performance_learning_screen(None, ledger_db_path=path)
        assert screen.ledger_available is True
        s = screen.ledger_funnel_summary
        assert isinstance(s, LedgerFunnelSummary)
        assert s.total_candidates == 5
        assert s.evaluations_completed == 4
        assert s.evaluations_incomplete == 1
        assert s.candidates_with_decision == 4
        assert s.candidates_without_decision == 1
        assert s.decision_events_recorded == 4
        assert (s.buy_count, s.sell_count, s.hold_count, s.reject_count) == (1, 0, 1, 2)
        assert s.executed_count == 1
        assert s.candidates_executed == 1
        assert s.candidates_hold == 1
        assert s.candidates_rejected == 2
        assert s.candidates_incomplete == 1
        assert [(r.gate, r.count) for r in s.rejection_reasons] == [("volume", 2)]
    finally:
        os.remove(path)


def test_empty_snapshot_yields_a_zeroed_summary_but_screen_stays_empty():
    path = _make_ledger_db(candidates=[], decisions=[])
    try:
        screen = _build_performance_learning_screen(None, ledger_db_path=path)
        assert screen.ledger_available is True
        assert screen.ledger_is_empty is True
        # summary is computed (not None) but the funnel panel is suppressed
        assert screen.ledger_funnel_summary is not None
        assert screen.ledger_funnel_summary.total_candidates == 0
        assert screen.ledger_funnel_available is False
    finally:
        os.remove(path)


def test_missing_ledger_file_is_unavailable_and_summary_none():
    screen = _build_performance_learning_screen(
        None, ledger_db_path="no_such_ledger_snapshot_wave3d.db")
    assert screen.ledger_available is False
    assert screen.ledger_funnel_summary is None


# --- opt-in production regression (real published snapshot shape) ---

_PROD = os.environ.get("AARA_WAVE3A_LEDGER_SNAPSHOT")


@pytest.mark.skipif(not _PROD, reason="set AARA_WAVE3A_LEDGER_SNAPSHOT to a real trust_ledger.db")
def test_production_snapshot_funnel_counts():
    screen = _build_performance_learning_screen(None, ledger_db_path=_PROD)
    s = screen.ledger_funnel_summary
    assert s.total_candidates == 202
    assert s.decision_events_recorded == 135
    assert s.buy_count == 3
    assert s.sell_count == 2
    assert s.hold_count == 26
    assert s.reject_count == 104
    assert s.executed_count == 5
    assert s.candidates_without_decision == 173
    # every REJECT event is accounted for in the gate breakdown
    assert sum(r.count for r in s.rejection_reasons) == s.reject_count
    # buckets partition the candidate population
    assert (s.candidates_executed + s.candidates_hold + s.candidates_rejected
            + s.candidates_no_decision + s.candidates_incomplete
            + s.candidates_other) == 202
