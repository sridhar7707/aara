"""Tests for the Phase 0 Decision Intelligence Foundation (ledger/ package),
data model v1.2.

Proves, rather than just claims:
  1. Schema creates cleanly with no errors.
  2. Direct UPDATE/DELETE against any Immutable Ledger or Versioned
     Reference table fails -- decision_events has zero exceptions (v1.2).
  3. A full event chain (candidate evaluation -> decision -> outcome) can
     be inserted and the hash chain verifies with zero breaks.
  4. Deliberately corrupting a stored value is caught by verification.
  5. The manifest lifecycle only allows legal transitions in order; an
     out-of-order transition is rejected.
  6. Reproducibility reconstruction returns a complete result for a sample
     decision using only historical tables.

Plus v1.2-specific coverage: the decision_state derived view (replacing the
old stored outcome_state column), the new BEFORE INSERT chain-integrity
triggers, the final_confidence CHECK, and the PROMOTED-requires-approval
CHECK constraint (enforced twice: application state machine + DB CHECK).
"""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

import ledger.db as db
import ledger.integrity as integrity
import ledger.ledger as ledger
import ledger.reproducibility as repro

_LEDGER_TABLES = list(ledger._LEDGER_TABLES.keys())
_REFERENCE_TABLES = [
    "model_artifacts", "model_training_runs", "strategy_versions",
    "risk_rulesets", "deployment_manifests",
]

_GENESIS = "0" * 64


@pytest.fixture
def conn():
    c = db.init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def reference_chain(conn):
    """A minimal, valid model_artifacts -> ... -> deployment_manifests chain,
    reused by several tests that need a real manifest_id to reference."""
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
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v2.1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()
    return "mani_v1"


def _candidate_payload(candidate_id="CAND-1", asset="AAPL", evaluation_completed=True):
    return {
        "candidate_event_id": candidate_id, "timestamp": "2026-07-28T10:00:00Z", "asset": asset,
        "screening_version": "v1", "screening_results": {"volume_ok": True},
        "data_available": True, "required_models_available": True,
        "evaluation_requested": True, "evaluation_completed": evaluation_completed,
    }


def _decision_payload(manifest_id, decision_id="DEC-1", candidate_event_id="CAND-1", asset="AAPL",
                      final_confidence=0.8):
    return {
        "decision_id": decision_id, "candidate_event_id": candidate_event_id,
        "timestamp": "2026-07-28T10:01:00Z", "asset": asset, "action": "BUY", "event_type": "EXECUTED",
        "portfolio_snapshot": {"value": 10000.0}, "market_context": {"regime": "bull"},
        "model_outputs": {"xgboost": 0.8}, "risk_checks": {"passed": True},
        "final_confidence": final_confidence, "deployment_manifest_id": manifest_id,
        "intent": {"primary_intent": "OPPORTUNITY_CAPTURE", "contributing_modules": []},
        "data_completeness": {"status": "COMPLETE", "missing_inputs": [], "stale_inputs": []},
    }


@pytest.fixture
def prereqs(conn, reference_chain):
    """One row each in candidate_evaluation_events (CAND-1), decision_events
    (DEC-1), and cost_models (cost_v1) -- FK targets shared by the
    UPDATE/DELETE-rejection parametrized tests below, which each need a
    real, referentially-valid row in every Group A table."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload("CAND-1"))
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain, "DEC-1", "CAND-1"))
    ledger.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_v1", "spread_assumption": 0.001, "slippage_assumption": 0.0005,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-01-01T00:00:00Z",
    })
    return reference_chain


_MINIMAL_PAYLOADS = {
    "candidate_evaluation_events": lambda: _candidate_payload("CAND-EXTRA", "MSFT"),
    "decision_events": lambda: _decision_payload("mani_v1", "DEC-EXTRA", "CAND-1", "MSFT"),
    "decision_outcome_events": lambda: {
        "outcome_id": "OUT-EXTRA", "decision_id": "DEC-1", "exit_timestamp": "2026-07-29T10:00:00Z",
        "gross_return": 0.01, "net_return": 0.009, "holding_period_days": 1,
        "cost_breakdown": {}, "cost_model_id": "cost_v1",
    },
    "risk_evaluation_events": lambda: {
        "event_id": "RISK-EXTRA", "timestamp": "2026-07-28T00:00:00Z",
        "from_state": "NORMAL", "to_state": "WARNING", "trigger_reason": "test",
        "validation_mode": "NATURAL",
    },
    "approval_events": lambda: {
        "approval_id": "APR-EXTRA", "timestamp": "2026-07-28T00:00:00Z",
        "subject_type": "WEIGHT_CHANGE", "subject_id": "x", "decision": "APPROVE",
        "reason_checklist": {}, "reason_comment": "test", "reviewer": "tester",
    },
    "deployment_manifest_events": lambda: {
        "event_id": "MFE-EXTRA", "manifest_id": "mani_v1", "event_type": "CREATED",
        "timestamp": "2026-07-28T00:00:00Z",
    },
    "cost_models": lambda: {
        "cost_model_id": "cost_v2", "spread_assumption": 0.001, "slippage_assumption": 0.0005,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-01-01T00:00:00Z",
    },
}


def _approve_and_promote(conn, manifest_id, approval_id="APR-1"):
    """Drive a manifest through CREATED -> ... -> PROMOTED, the sequence
    several tests need as setup."""
    ledger.transition_manifest(conn, manifest_id, "CREATED", "2026-07-28T00:01:00Z")
    ledger.transition_manifest(conn, manifest_id, "TESTING_STARTED", "2026-07-28T00:02:00Z")
    ledger.transition_manifest(conn, manifest_id, "REVIEW_REQUESTED", "2026-07-28T00:03:00Z")
    ledger.append_ledger_row(conn, "approval_events", {
        "approval_id": approval_id, "timestamp": "2026-07-28T00:04:00Z",
        "subject_type": "MANIFEST_PROMOTION", "subject_id": manifest_id, "decision": "APPROVE",
        "reason_checklist": {}, "reason_comment": "ok", "reviewer": "tester",
    })
    ledger.transition_manifest(conn, manifest_id, "APPROVED", "2026-07-28T00:05:00Z", approval_event_id=approval_id)
    ledger.transition_manifest(conn, manifest_id, "PROMOTED", "2026-07-28T00:06:00Z")


# ── 1. Schema creates cleanly ─────────────────────────────────────────────────

def test_schema_creates_cleanly(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]
    expected = set(_LEDGER_TABLES) | set(_REFERENCE_TABLES) | {
        "active_deployment_pointer", "data_quality_events", "schema_migrations",
    }
    assert expected.issubset(set(tables))

    views = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    assert "decision_state" in views


def test_schema_is_idempotent(conn):
    """init_schema can run twice without error (IF NOT EXISTS everywhere)."""
    db.init_schema(conn)  # second call, same connection


# ── 2. UPDATE/DELETE rejected on every ledger + reference table,
#      including decision_events with zero exceptions (v1.2) ────────────────

@pytest.mark.parametrize("table", _LEDGER_TABLES + _REFERENCE_TABLES)
def test_update_rejected(conn, prereqs, table):
    # SQLite BEFORE UPDATE/DELETE triggers fire per-row -- an UPDATE/DELETE
    # against zero matching rows never fires them at all, so every table
    # under test needs at least one real row first. prereqs already
    # populates the 5 Group B tables plus one candidate/decision/cost_model
    # row (FK targets for the remaining Group A tables inserted below).
    if table in _LEDGER_TABLES:
        ledger.append_ledger_row(conn, table, _MINIMAL_PAYLOADS[table]())
    cols = [d[1] for d in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"UPDATE {table} SET {cols[0]} = {cols[0]}")


@pytest.mark.parametrize("table", _LEDGER_TABLES + _REFERENCE_TABLES)
def test_delete_rejected(conn, prereqs, table):
    if table in _LEDGER_TABLES:
        ledger.append_ledger_row(conn, table, _MINIMAL_PAYLOADS[table]())
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"DELETE FROM {table}")


def test_decision_events_immutable_with_zero_exceptions(conn, reference_chain):
    """v1.2: unlike the removed v1.1 outcome_state carve-out, there is now
    NO column on decision_events that can be updated in place -- not even
    what used to be outcome_state, since that column no longer exists."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain))

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE decision_events SET final_confidence=0.9 WHERE decision_id='DEC-1'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE decision_events SET asset='MSFT' WHERE decision_id='DEC-1'")


# ── 3. Full event chain inserts and verifies with zero breaks ────────────────

def test_full_chain_insert_and_verify(conn, reference_chain):
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain))
    ledger.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_v1", "spread_assumption": 0.001, "slippage_assumption": 0.0005,
        "commission_rules": {"flat": 0.0}, "tax_assumptions": {"rate": 0.0}, "created_at": "2026-01-01T00:00:00Z",
    })
    ledger.append_ledger_row(conn, "decision_outcome_events", {
        "outcome_id": "OUT-1", "decision_id": "DEC-1", "exit_timestamp": "2026-07-29T10:00:00Z",
        "gross_return": 0.05, "net_return": 0.048, "holding_period_days": 1,
        "cost_breakdown": {"spread": 0.001, "slippage": 0.0005, "commission": 0.0},
        "cost_model_id": "cost_v1",
    })

    for table in ("candidate_evaluation_events", "decision_events", "decision_outcome_events", "cost_models"):
        assert ledger.verify_chain(conn, table) == [], f"{table} should have zero breaks"

    assert ledger.get_decision_state(conn, "DEC-1") == "CLOSED"


# ── 4. Deliberate corruption is caught ────────────────────────────────────────

def test_corruption_caught_by_verification(conn, reference_chain):
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload("CAND-2", "MSFT"))
    assert ledger.verify_chain(conn, "candidate_evaluation_events") == []

    # Simulate tampering that bypasses the application layer AND the
    # trigger (e.g. a direct file edit, restore from a stale backup) --
    # exactly the scenario the verification job exists to catch.
    conn.execute("DROP TRIGGER trg_candidate_evaluation_events_no_update")
    conn.execute("UPDATE candidate_evaluation_events SET asset='TAMPERED' WHERE sequence_number=1")
    conn.commit()

    breaks = ledger.verify_chain(conn, "candidate_evaluation_events")
    assert len(breaks) >= 1
    assert breaks[0]["sequence_number"] == 1
    assert "record_hash does not match" in breaks[0]["reason"]

    # And the integrity job surfaces it too
    report = integrity.run_integrity_check(conn)
    assert "candidate_evaluation_events" in report["broken_chains"]


def test_tampering_with_chain_linkage_is_also_caught(conn):
    """Corrupting previous_record_hash (not the payload) breaks the OTHER
    check verify_chain performs -- chain linkage, not just payload hash.
    Uses evaluation_completed=False so the *second* insert's
    previous_record_hash still differs from what a clean chain would have
    produced, keeping this test independent of the corruption below it."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload("CAND-2", "MSFT"))
    assert ledger.verify_chain(conn, "candidate_evaluation_events") == []

    conn.execute("DROP TRIGGER trg_candidate_evaluation_events_no_update")
    # Also drop the chain-integrity BEFORE INSERT trigger's cousin doesn't
    # apply here (this is an UPDATE, not INSERT) -- only the no-update
    # trigger needs dropping to simulate a bypass.
    conn.execute("UPDATE candidate_evaluation_events SET previous_record_hash=? WHERE sequence_number=2",
                 ("f" * 64,))
    conn.commit()

    breaks = ledger.verify_chain(conn, "candidate_evaluation_events")
    assert any("previous_record_hash does not match" in b["reason"] for b in breaks)


# ── New in v1.2: BEFORE INSERT chain-integrity triggers ──────────────────────

def test_chain_integrity_trigger_rejects_wrong_previous_hash_on_insert(conn):
    """A raw INSERT with an incorrect previous_record_hash is rejected by
    the new BEFORE INSERT trigger, independent of append_ledger_row ever
    being involved -- this is the DB refusing a bad chain pointer at write
    time, not the Python-side verify_chain() catching it after the fact."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    # Correct hash chain continuation would need the real record_hash of the
    # row above as previous_record_hash; deliberately use a wrong one.
    with pytest.raises(sqlite3.IntegrityError, match="previous_record_hash does not match current chain head"):
        conn.execute(
            "INSERT INTO candidate_evaluation_events "
            "(candidate_event_id, timestamp, asset, screening_version, screening_results, "
            "data_available, required_models_available, evaluation_requested, evaluation_completed, "
            "record_hash, previous_record_hash) "
            "VALUES ('CAND-BAD', '2026-07-28T10:05:00Z', 'MSFT', 'v1', '{}', 1, 1, 1, 1, 'somehash', ?)",
            ("wrong_previous_hash_value_not_matching_chain_head".ljust(64, "0"),),
        )


def test_chain_integrity_trigger_allows_correct_previous_hash(conn):
    """The trigger must not be a false-positive on legitimate inserts --
    append_ledger_row (which always computes the correct previous_record_hash)
    must keep working, which every other test in this file already exercises,
    but this asserts it explicitly against the genesis case."""
    row = ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    assert row["previous_record_hash"] == _GENESIS


# ── 5. Manifest lifecycle: legal order only ───────────────────────────────────

def test_manifest_lifecycle_legal_order_succeeds(conn, reference_chain):
    _approve_and_promote(conn, reference_chain)

    assert ledger.get_manifest_state(conn, reference_chain) == "PROMOTED"
    assert integrity.get_active_pointer(conn) == reference_chain
    assert ledger.rebuild_active_pointer(conn) == reference_chain


def test_manifest_out_of_order_transition_rejected(conn, reference_chain):
    ledger.transition_manifest(conn, reference_chain, "CREATED", "2026-07-28T00:01:00Z")
    with pytest.raises(ValueError, match="Illegal manifest transition"):
        ledger.transition_manifest(conn, reference_chain, "APPROVED", "2026-07-28T00:02:00Z", approval_event_id="APR-X")


def test_manifest_promoted_to_created_rejected(conn, reference_chain):
    """The exact example the requirements call out: PROMOTED -> CREATED."""
    _approve_and_promote(conn, reference_chain)
    with pytest.raises(ValueError, match="Illegal manifest transition"):
        ledger.transition_manifest(conn, reference_chain, "CREATED", "2026-07-28T00:07:00Z")


def test_manifest_approved_requires_approval_event_id(conn, reference_chain):
    ledger.transition_manifest(conn, reference_chain, "CREATED", "2026-07-28T00:01:00Z")
    ledger.transition_manifest(conn, reference_chain, "TESTING_STARTED", "2026-07-28T00:02:00Z")
    ledger.transition_manifest(conn, reference_chain, "REVIEW_REQUESTED", "2026-07-28T00:03:00Z")
    with pytest.raises(ValueError, match="requires a linked approval_event_id"):
        ledger.transition_manifest(conn, reference_chain, "APPROVED", "2026-07-28T00:04:00Z")


def test_manifest_retired_clears_active_pointer(conn, reference_chain):
    _approve_and_promote(conn, reference_chain)
    ledger.transition_manifest(conn, reference_chain, "RETIRED", "2026-07-28T00:07:00Z")

    assert integrity.get_active_pointer(conn) is None
    assert ledger.rebuild_active_pointer(conn) is None


def test_active_deployment_pointer_cleared_by_row_deletion_not_null(conn, reference_chain):
    """v1.3: "no active deployment" is row absence, not active_manifest_id
    set to NULL -- explicitly confirms the row is gone, not present-with-NULL
    (which would violate the column's NOT NULL constraint anyway)."""
    _approve_and_promote(conn, reference_chain)
    assert conn.execute("SELECT COUNT(*) FROM active_deployment_pointer").fetchone()[0] == 1

    ledger.transition_manifest(conn, reference_chain, "RETIRED", "2026-07-28T00:07:00Z")
    assert conn.execute("SELECT COUNT(*) FROM active_deployment_pointer").fetchone()[0] == 0


def test_active_deployment_pointer_rejects_null_active_manifest_id(conn, reference_chain):
    """v1.3: active_manifest_id is NOT NULL -- a raw attempt to insert a row
    with a NULL value is rejected outright, confirming there's no way to
    represent "no active deployment" other than the row simply not existing."""
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed"):
        conn.execute(
            "INSERT INTO active_deployment_pointer (id, active_manifest_id, updated_at) "
            "VALUES (1, NULL, '2026-07-28T00:00:00Z')"
        )


def test_manifest_event_id_auto_generated_and_sequential(conn, reference_chain):
    """v1.3: deployment_manifest_events.event_id is auto-generated by
    transition_manifest() in MFE-YYYYMMDD-NNN form, incrementing per day."""
    row1 = ledger.transition_manifest(conn, reference_chain, "CREATED", "2026-07-28T00:01:00Z")
    row2 = ledger.transition_manifest(conn, reference_chain, "TESTING_STARTED", "2026-07-28T00:02:00Z")

    assert row1["event_id"] == "MFE-20260728-001"
    assert row2["event_id"] == "MFE-20260728-002"


def test_transition_manifest_promoted_auto_resolves_approval_event_id(conn, reference_chain):
    """v1.2 (FR-0.12): PROMOTED auto-resolves approval_event_id from the
    manifest's own prior APPROVED event when the caller doesn't pass one."""
    ledger.transition_manifest(conn, reference_chain, "CREATED", "2026-07-28T00:01:00Z")
    ledger.transition_manifest(conn, reference_chain, "TESTING_STARTED", "2026-07-28T00:02:00Z")
    ledger.transition_manifest(conn, reference_chain, "REVIEW_REQUESTED", "2026-07-28T00:03:00Z")
    ledger.append_ledger_row(conn, "approval_events", {
        "approval_id": "APR-AUTO", "timestamp": "2026-07-28T00:04:00Z",
        "subject_type": "MANIFEST_PROMOTION", "subject_id": reference_chain, "decision": "APPROVE",
        "reason_checklist": {}, "reason_comment": "ok", "reviewer": "tester",
    })
    ledger.transition_manifest(conn, reference_chain, "APPROVED", "2026-07-28T00:05:00Z", approval_event_id="APR-AUTO")

    # No approval_event_id passed here -- must auto-resolve to APR-AUTO.
    row = ledger.transition_manifest(conn, reference_chain, "PROMOTED", "2026-07-28T00:06:00Z")
    assert row["approval_event_id"] == "APR-AUTO"


def test_deployment_manifest_events_promoted_requires_approval_check_constraint(conn, reference_chain):
    """v1.2 (FR-0.12): a raw INSERT of a PROMOTED row with a NULL
    approval_event_id is rejected by the DB CHECK constraint, independent
    of transition_manifest()'s own application-layer validation. Uses a
    correct previous_record_hash so a failure is unambiguously the CHECK
    constraint, not the chain-integrity trigger."""
    genesis_row = ledger.append_ledger_row(conn, "deployment_manifest_events", {
        "event_id": "MFE-TEST-001", "manifest_id": reference_chain, "event_type": "CREATED",
        "timestamp": "2026-07-28T00:01:00Z", "approval_event_id": None,
    })
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        conn.execute(
            "INSERT INTO deployment_manifest_events "
            "(event_id, manifest_id, event_type, approval_event_id, timestamp, record_hash, previous_record_hash) "
            "VALUES ('MFE-TEST-002', ?, 'PROMOTED', NULL, '2026-07-28T00:02:00Z', 'somehash', ?)",
            (reference_chain, genesis_row["record_hash"]),
        )


# ── final_confidence CHECK constraint ────────────────────────────────────────

def test_final_confidence_out_of_range_rejected(conn, reference_chain):
    """v1.2: final_confidence must be in [0.0, 1.0], DB-enforced."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain, final_confidence=1.5))


# ── evaluation_completed (FR-0.13) ───────────────────────────────────────────

def test_evaluation_completed_distinct_from_requested(conn):
    """A candidate can be requested-but-not-completed (crashed/partial
    evaluation) -- schema must support recording this distinctly, per
    FR-0.13. As of v1.4, a decision_events row referencing such a candidate
    is also rejected at the DB level -- see
    test_decision_events_requires_completed_evaluation below."""
    row = ledger.append_ledger_row(
        conn, "candidate_evaluation_events",
        _candidate_payload("CAND-CRASHED", evaluation_completed=False),
    )
    stored = conn.execute(
        "SELECT evaluation_requested, evaluation_completed FROM candidate_evaluation_events "
        "WHERE candidate_event_id='CAND-CRASHED'"
    ).fetchone()
    assert stored == (1, 0)
    assert row["evaluation_completed"] is False


def test_decision_events_requires_completed_evaluation(conn, reference_chain):
    """v1.4 (FR-0.1a/FR-0.13, candidate provenance): a decision_events row
    referencing a candidate whose evaluation never completed must be
    rejected by trg_decision_events_requires_completed_evaluation -- this
    was previously only a code comment, not DB-enforced."""
    ledger.append_ledger_row(
        conn, "candidate_evaluation_events",
        _candidate_payload("CAND-CRASHED", evaluation_completed=False),
    )
    with pytest.raises(sqlite3.IntegrityError):
        ledger.append_ledger_row(
            conn, "decision_events",
            _decision_payload(reference_chain, "DEC-BAD", "CAND-CRASHED"),
        )


def test_decision_events_allows_completed_evaluation(conn, reference_chain):
    """The v1.4 trigger only rejects incomplete evaluations -- a candidate
    with evaluation_completed=True must still insert cleanly."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload("CAND-OK"))
    row = ledger.append_ledger_row(
        conn, "decision_events",
        _decision_payload(reference_chain, "DEC-OK", "CAND-OK"),
    )
    assert row["decision_id"] == "DEC-OK"


# ── 6. Reproducibility reconstruction ─────────────────────────────────────────

def test_reproducibility_reconstruction_complete(conn, reference_chain):
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain))

    snapshot = repro.reconstruct_decision_snapshot(conn, "DEC-1")

    assert snapshot["decision"]["asset"] == "AAPL"
    assert snapshot["decision"]["final_confidence"] == 0.8
    assert snapshot["decision"]["outcome_state"] == "OPEN"  # derived, no outcome yet
    assert snapshot["candidate_evaluation"]["candidate_event_id"] == "CAND-1"
    assert snapshot["deployment_manifest"]["manifest_id"] == "mani_v1"
    assert snapshot["deployment_manifest"]["feature_pipeline_version"] == "fp_v2.1"  # v1.2
    assert snapshot["model_training_runs"]["xgboost"]["training_run_id"] == "run1"
    assert snapshot["model_training_runs"]["xgboost"]["artifact_size_bytes"] == 1024  # v1.2
    assert snapshot["strategy_version"]["strategy_version_id"] == "strat_v1"
    assert snapshot["risk_ruleset"]["risk_ruleset_id"] == "risk_v1"


def test_reproducibility_reflects_closed_state_after_outcome(conn, reference_chain):
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain))
    ledger.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_v1", "spread_assumption": 0.001, "slippage_assumption": 0.0005,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-01-01T00:00:00Z",
    })
    ledger.append_ledger_row(conn, "decision_outcome_events", {
        "outcome_id": "OUT-1", "decision_id": "DEC-1", "exit_timestamp": "2026-07-29T10:00:00Z",
        "gross_return": 0.05, "net_return": 0.048, "holding_period_days": 1,
        "cost_breakdown": {}, "cost_model_id": "cost_v1",
    })

    snapshot = repro.reconstruct_decision_snapshot(conn, "DEC-1")
    assert snapshot["decision"]["outcome_state"] == "CLOSED"


def test_reproducibility_uses_only_historical_tables(conn, reference_chain):
    """Reconstruction must not depend on active_deployment_pointer at all --
    it should work identically whether the pointer is populated, stale, or
    empty, since a decision from a long-retired manifest must still fully
    reconstruct."""
    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload(reference_chain))

    # active_deployment_pointer is untouched/empty in this test -- no manifest
    # has been promoted -- yet reconstruction must still fully succeed.
    assert integrity.get_active_pointer(conn) is None
    snapshot = repro.reconstruct_decision_snapshot(conn, "DEC-1")
    assert snapshot["deployment_manifest"]["manifest_id"] == "mani_v1"


def test_reproducibility_raises_on_unknown_decision(conn):
    with pytest.raises(ValueError, match="No such decision_id"):
        repro.reconstruct_decision_snapshot(conn, "DEC-NONEXISTENT")


def test_acceptance_test_fr_0_10_fails_on_checksum_mismatch(conn, tmp_path):
    """NFR-8: verify_artifact_integrity must catch a checksum mismatch, not
    just a missing file. Builds its own reference chain (rather than reusing
    the reference_chain fixture) since model_training_runs is append-only --
    the real artifact_storage_ref/checksum must be set at insert time, not
    patched in afterward via UPDATE."""
    artifact = tmp_path / "model.pkl"
    artifact.write_bytes(b"real weights")
    real_checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    real_size = artifact.stat().st_size

    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',?,?,?,'2026-06-01T00:00:00Z')",
        (str(artifact), real_checksum, real_size),
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v2.1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()

    ledger.append_ledger_row(conn, "candidate_evaluation_events", _candidate_payload())
    ledger.append_ledger_row(conn, "decision_events", _decision_payload("mani_v1"))
    repro.acceptance_test_fr_0_10(conn, "DEC-1")  # passes: checksum + size match

    # Now corrupt the file on disk -- checksum (and size) no longer match
    artifact.write_bytes(b"tampered weights, a different length")
    with pytest.raises(AssertionError, match="NFR-8 violated"):
        repro.acceptance_test_fr_0_10(conn, "DEC-1")


def test_verify_artifact_integrity_catches_size_mismatch_cheaply(tmp_path):
    """The v1.2 artifact_size_bytes pre-check rejects a wrong-size file
    without needing the checksum to also be wrong (belt-and-suspenders --
    in practice a size mismatch implies a checksum mismatch too, but the
    cheap check should fire on its own)."""
    artifact = tmp_path / "model.pkl"
    artifact.write_bytes(b"original content")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()

    training_run = {
        "artifact_storage_ref": str(artifact), "artifact_checksum": checksum,
        "artifact_size_bytes": 999999,  # deliberately wrong
    }
    assert repro.verify_artifact_integrity(training_run) is False


# ── HF-friendly storage footprint ─────────────────────────────────────────────

def test_ledger_module_has_no_third_party_dependencies():
    """v1.4 completion claim: ledger.py (the module doing all the writing/
    verification) must run on Python stdlib alone -- no numpy/pandas/ORM/
    server process -- since the project runs on HF Spaces' free tier and a
    heavy dependency here would be a real, not hypothetical, resource risk.
    Uses ast (not a substring scan) so a docstring that happens to start
    with the word "from" can't produce a false positive."""
    import ast
    import inspect

    stdlib_modules = {"hashlib", "json", "sqlite3", "datetime", "typing", "__future__"}
    tree = ast.parse(inspect.getsource(ledger))
    external = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            external += [n.name for n in node.names if n.name.split(".")[0] not in stdlib_modules]
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in stdlib_modules and root != "ledger":
                external.append(node.module)
    assert external == [], f"non-stdlib, non-local imports found in ledger.py: {external}"
