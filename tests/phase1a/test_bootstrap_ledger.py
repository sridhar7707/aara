"""Tests for scripts/phase1a_bootstrap_ledger.py (Phase 1A Sprint 1)."""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.ledger as ledger_svc  # noqa: E402
import ledger.integrity as integrity  # noqa: E402
from scripts import phase1a_bootstrap_ledger as bootstrap_mod  # noqa: E402


@pytest.fixture
def ledger_conn(tmp_path):
    db_path = str(tmp_path / "test_trust_ledger.db")
    conn = bootstrap_mod.bootstrap(db_path=db_path, close=False)
    yield conn
    conn.close()


def test_bootstrap_promotes_manifest_and_sets_active_pointer(ledger_conn):
    active_manifest = integrity.get_active_pointer(ledger_conn)
    assert active_manifest == bootstrap_mod.MANIFEST_ID


def test_bootstrap_all_group_a_chains_verify_clean(ledger_conn):
    breaks = ledger_svc.verify_all_chains(ledger_conn)
    for table, table_breaks in breaks.items():
        assert table_breaks == [], f"{table} has chain breaks: {table_breaks}"


def test_bootstrap_is_idempotent(tmp_path):
    db_path = str(tmp_path / "idempotent.db")
    conn1 = bootstrap_mod.bootstrap(db_path=db_path, close=False)
    row_count_before = conn1.execute("SELECT COUNT(*) FROM deployment_manifest_events").fetchone()[0]
    conn1.close()

    conn2 = bootstrap_mod.bootstrap(db_path=db_path, close=False)
    row_count_after = conn2.execute("SELECT COUNT(*) FROM deployment_manifest_events").fetchone()[0]
    conn2.close()

    assert row_count_after == row_count_before


def test_bootstrap_default_close_returns_none_on_second_call(tmp_path):
    """Regression test: bootstrap(close=True)'s early-return path (already
    bootstrapped) used to close the connection but still return it, instead
    of returning None like the main path does -- a caller using the return
    value would get a dead sqlite3.Connection instead of a clean signal that
    nothing happened."""
    db_path = str(tmp_path / "close_contract.db")
    first = bootstrap_mod.bootstrap(db_path=db_path, close=True)
    assert first is None
    second = bootstrap_mod.bootstrap(db_path=db_path, close=True)
    assert second is None


def test_training_run_checksum_matches_independent_rehash(ledger_conn):
    xgb_path = "models/saved/xgb_predictor.pkl"
    with open(xgb_path, "rb") as f:
        real_checksum = hashlib.sha256(f.read()).hexdigest()

    stored = ledger_conn.execute(
        "SELECT artifact_checksum, artifact_size_bytes FROM model_training_runs "
        "WHERE artifact_storage_ref=?", (xgb_path,),
    ).fetchone()
    assert stored is not None
    assert stored[0] == real_checksum
    assert stored[1] == os.path.getsize(xgb_path)


def test_deployment_manifest_references_both_training_runs(ledger_conn):
    import json
    row = ledger_conn.execute(
        "SELECT component_training_runs FROM deployment_manifests WHERE manifest_id=?",
        (bootstrap_mod.MANIFEST_ID,),
    ).fetchone()
    component_runs = json.loads(row[0])
    assert "xgboost" in component_runs
    assert "lstm" in component_runs


def test_validation_metrics_flagged_stale(ledger_conn):
    import json
    rows = ledger_conn.execute("SELECT validation_metrics FROM model_training_runs").fetchall()
    assert len(rows) == 2
    for (metrics_json,) in rows:
        metrics = json.loads(metrics_json)
        assert "STALE" in metrics["status"]
