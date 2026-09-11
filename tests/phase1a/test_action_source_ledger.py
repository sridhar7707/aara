"""Sprint 4 Item #2 -- decision_action_source_events persistence slice.

The ADR-069 (B2) action-source provenance ("SENTINEL" / "STRATEGY") that is
authored in EntryDecisionRecorder.__init__ is now persisted as an immutable
sibling Group-A event, one row per entry decision, referencing the
authoritative decision_events row. decision_events itself is untouched.

Fixture pattern mirrors tests/phase1a/test_constitution.py /
tests/phase1a/test_causal_decision_lifecycle.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest  # noqa: E402
import sqlite3  # noqa: E402

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import bot._main_trust_decisions as mtd  # noqa: E402
import bot.trust_ledger.action_source as action_source_ledger  # noqa: E402
from bot._main_trust_decisions import EntryDecisionRecorder  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402
from bot.trust_ledger.ids import new_action_source_event_id  # noqa: E402
from sentinel_engine.domain.action_source import ActionSource  # noqa: E402

_TABLE = "decision_action_source_events"


@pytest.fixture(autouse=True)
def _clear_candidate_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def conn():
    c = ledger_db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def chain(conn):
    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',"
        "'/tmp/x.pkl','deadbeef',1024,'2026-06-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


def _write_parent(conn, chain, asset="AAPL", action="BUY", event_type="EXECUTED", decision_id=None):
    return decisions.write_decision_event(
        conn, candidate_event_id=chain["candidate_event_id"], asset=asset,
        action=action, event_type=event_type,
        portfolio_snapshot={"portfolio_value": 10000.0},
        market_context={"regime": "bull"},
        model_outputs={"xgboost": 0.7}, risk_checks={"gates": []},
        final_confidence=0.65, deployment_manifest_id=chain["manifest_id"],
        intent=decisions.build_intent(action),
        data_completeness=decisions.build_data_completeness(),
        decision_id=decision_id,
    )


def _count(conn, decision_id=None):
    if decision_id is None:
        return conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
    return conn.execute(
        f"SELECT COUNT(*) FROM {_TABLE} WHERE decision_id=?", (decision_id,)
    ).fetchone()[0]


# ── schema / ledger registration ──────────────────────────────────────────

def test_table_exists(conn):
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert _TABLE in names


def test_required_columns_exist(conn):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({_TABLE})").fetchall()}
    assert {
        "sequence_number", "event_id", "decision_id", "action_source",
        "recorded_at", "record_hash", "previous_record_hash",
    }.issubset(cols)


def test_table_is_registered_in_ledger_tables(conn):
    assert _TABLE in ledger_svc._LEDGER_TABLES
    meta = ledger_svc._LEDGER_TABLES[_TABLE]
    assert meta["json_fields"] == set()
    assert meta["bool_fields"] == set()


def test_independent_chain_first_row_links_to_genesis(conn, chain):
    parent = _write_parent(conn, chain)
    row = action_source_ledger.write_action_source_event(
        conn, parent["decision_id"], "SENTINEL", "2026-07-28T10:00:00Z",
    )
    assert row["previous_record_hash"] == "0" * 64
    assert ledger_svc.verify_chain(conn, _TABLE) == []


def test_chain_verifies_after_multiple_inserts(conn, chain):
    a = _write_parent(conn, chain, decision_id="DEC-A")
    b = _write_parent(conn, chain, asset="MSFT", decision_id="DEC-B")
    r1 = action_source_ledger.write_action_source_event(conn, a["decision_id"], "SENTINEL", "2026-07-28T10:00:00Z")
    r2 = action_source_ledger.write_action_source_event(conn, b["decision_id"], "STRATEGY", "2026-07-28T10:01:00Z")
    assert r2["previous_record_hash"] == r1["record_hash"]
    assert ledger_svc.verify_chain(conn, _TABLE) == []


def test_update_and_delete_are_rejected(conn, chain):
    parent = _write_parent(conn, chain)
    action_source_ledger.write_action_source_event(conn, parent["decision_id"], "SENTINEL", "2026-07-28T10:00:00Z")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"UPDATE {_TABLE} SET action_source='STRATEGY'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"DELETE FROM {_TABLE}")


def test_decision_id_foreign_key_is_enforced(conn):
    # No parent decision_events row for this id -> FK violation.
    with pytest.raises(sqlite3.IntegrityError):
        action_source_ledger.write_action_source_event(
            conn, "DEC-does-not-exist", "SENTINEL", "2026-07-28T10:00:00Z",
        )


def test_check_constraint_rejects_values_outside_the_live_vocabulary(conn, chain):
    parent = _write_parent(conn, chain)
    with pytest.raises(sqlite3.IntegrityError):
        action_source_ledger.write_action_source_event(
            conn, parent["decision_id"], "MADE_UP", "2026-07-28T10:00:00Z",
        )


def test_decision_events_schema_has_no_action_source_column(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(decision_events)").fetchall()}
    assert "action_source" not in cols


# ── writer ────────────────────────────────────────────────────────────────

def test_event_id_generator_follows_repository_convention():
    eid = new_action_source_event_id("AAPL")
    assert eid.startswith("ASRC-")
    assert eid.split("-")[-1] and len(eid.split("-")[-1]) == 8  # uuid4 hex suffix


@pytest.mark.parametrize("value", ["SENTINEL", "STRATEGY"])
def test_writer_persists_each_live_value(conn, chain, value):
    parent = _write_parent(conn, chain)
    row = action_source_ledger.write_action_source_event(
        conn, parent["decision_id"], value, "2026-07-28T10:00:00Z",
    )
    assert row["decision_id"] == parent["decision_id"]
    assert row["action_source"] == value
    assert row["recorded_at"] == "2026-07-28T10:00:00Z"
    assert row["event_id"].startswith("ASRC-")
    assert row["record_hash"] and row["previous_record_hash"]
    assert "sequence_number" in row
    stored = conn.execute(
        f"SELECT action_source, recorded_at FROM {_TABLE} WHERE decision_id=?",
        (parent["decision_id"],),
    ).fetchone()
    assert stored == (value, "2026-07-28T10:00:00Z")


# ── value flow: EntryDecisionRecorder -> record_decision_safe ──────────────

def _make_recorder(trust_conn=None, xgb_prob=0.7, lstm_prob=0.6, sentiment=0.1):
    return EntryDecisionRecorder(
        trust_conn, "cand-x", "mani_v1", "AAPL",
        xgb_prob=xgb_prob, lstm_prob=lstm_prob, sentiment=sentiment, macro_score=0.5,
        regime_name="TRENDING_UP", portfolio_value=10000.0, available_cash=5000.0,
        price_data_timestamp="2026-09-08T13:00:00Z",
    )


def test_recorder_stashes_sentinel_action_source_for_unanimous_buy():
    rec = _make_recorder()  # unanimous BUY -> B2 concurs
    assert rec.action_source == ActionSource.SENTINEL.value


def test_recorder_stashes_strategy_action_source_on_b2_fallback(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("b2 down")

    monkeypatch.setattr(mtd, "recommend_entry_action", _boom)
    rec = _make_recorder()  # must not raise
    assert rec.action_source == ActionSource.STRATEGY.value


def test_record_executed_writes_exactly_one_sentinel_sibling_row(conn, chain):
    rec = _make_recorder(trust_conn=conn)
    # Drive the value flow through record_decision_safe exactly as
    # record_executed() does (record_decision_safe(..., decision_id=,
    # action_source=)):
    mtd.record_decision_safe(
        conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "BUY", "EXECUTED",
        rec.portfolio_snapshot, rec.market_context, rec.model_outputs,
        {"gate_trace": []}, rec.final_confidence,
        decisions.build_intent("BUY"), rec.data_completeness,
        decision_id=rec.decision_id, action_source=rec.action_source,
    )
    parent_id = conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL' ORDER BY sequence_number DESC LIMIT 1"
    ).fetchone()[0]
    assert parent_id == rec.decision_id
    assert _count(conn, rec.decision_id) == 1
    stored = conn.execute(
        f"SELECT action_source FROM {_TABLE} WHERE decision_id=?", (rec.decision_id,)
    ).fetchone()[0]
    assert stored == "SENTINEL"


def test_reject_terminal_method_threads_action_source_through(conn, chain, monkeypatch):
    captured = {}
    real = mtd.record_decision_safe

    def _spy(*args, **kwargs):
        captured["action_source"] = kwargs.get("action_source")
        return real(*args, **kwargs)

    monkeypatch.setattr(mtd, "record_decision_safe", _spy)
    rec = _make_recorder(trust_conn=conn)
    rec.trust_conn = conn
    rec.candidate_event_id = chain["candidate_event_id"]
    rec.deployment_manifest_id = chain["manifest_id"]
    rec.reject("some_gate", "some detail")
    assert captured["action_source"] == ActionSource.SENTINEL.value
    assert _count(conn, rec.decision_id) == 1


# ── failure isolation ─────────────────────────────────────────────────────

def test_sibling_write_failure_does_not_block_parent_or_downstream(conn, chain, monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("simulated action-source write failure")

    monkeypatch.setattr(action_source_ledger, "write_action_source_event", _boom)
    mtd.record_decision_safe(
        conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "BUY", "EXECUTED",
        {"portfolio_value": 10000.0}, {"regime": "bull"},
        build_model_outputs(0.7, 0.6, 0.2),
        {"gate_trace": []}, 0.65,
        decisions.build_intent("BUY"), decisions.build_data_completeness(),
        risk=None, action_source="SENTINEL",
    )
    # parent still written
    assert conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0] == 1
    # no sibling row (its write raised and was swallowed)
    assert _count(conn) == 0
    # downstream still ran: constitution wrote its 6 rows
    parent_id = conn.execute(
        "SELECT decision_id FROM decision_events WHERE asset='AAPL'"
    ).fetchone()[0]
    assert conn.execute(
        "SELECT COUNT(*) FROM constitution_enforcement_events WHERE decision_id=?", (parent_id,)
    ).fetchone()[0] == 6


# ── absence semantics: no row unless action_source is a real value ────────

def test_no_sibling_row_when_action_source_is_none(conn, chain):
    mtd.record_decision_safe(
        conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "REJECT", "QUALIFIED_REJECTION",
        {"portfolio_value": 1.0}, {"regime": "x"},
        {"xgboost": {"signal": "HOLD", "confidence": 0.5, "metadata": {}}},
        {"gate_trace": []}, 0.5,
        decisions.build_intent("REJECT"), decisions.build_data_completeness(),
        decision_id=None, action_source=None,
    )
    assert conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0] == 1
    assert _count(conn) == 0


def test_exit_path_writes_no_action_source_row(conn, chain):
    ctx = mtd.ExitLedgerContext(
        trust_conn=conn, candidate_event_id=chain["candidate_event_id"],
        deployment_manifest_id=chain["manifest_id"],
        xgb_prob=0.3, lstm_prob=0.4, sentiment=-0.1, macro_score=0.5,
    )
    mtd.record_exit_decision_safe(ctx, "AAPL", "SELL", "EXECUTED", "stop-loss", 10000.0, 50.0)
    assert conn.execute(
        "SELECT COUNT(*) FROM decision_events WHERE asset='AAPL' AND action='SELL'"
    ).fetchone()[0] == 1
    assert _count(conn) == 0


# ── compatibility: existing positional callers unaffected ─────────────────

def test_record_decision_safe_still_accepts_the_pre_existing_call_shape(conn, chain):
    # No action_source kwarg -> behaves exactly as before, no sibling row.
    mtd.record_decision_safe(
        conn, chain["candidate_event_id"], chain["manifest_id"],
        "AAPL", "REJECT", "QUALIFIED_REJECTION",
        {"portfolio_value": 1.0}, {"regime": "x"},
        {"xgboost": {"signal": "HOLD", "confidence": 0.5, "metadata": {}}},
        {"gate_trace": []}, 0.5,
        decisions.build_intent("REJECT"), decisions.build_data_completeness(),
    )
    assert conn.execute("SELECT COUNT(*) FROM decision_events WHERE asset='AAPL'").fetchone()[0] == 1
    assert _count(conn) == 0
