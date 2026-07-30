"""Shared fixtures for tests/phase1b/ -- mirrors tests/phase2/conftest.py's
reference_chain pattern (minimal Group B chain + a candidate_evaluation_events
row) so decision_events/decision_outcome_events/constitution_enforcement_events
rows can be written against a fresh in-memory ledger.
"""
from __future__ import annotations

import hashlib

import pytest

import ledger.db as ledger_db
import ledger.ledger as ledger_svc
import bot.trust_ledger.candidates as candidates


@pytest.fixture(autouse=True)
def _clear_module_cache():
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
def reference_chain(conn):
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
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}


@pytest.fixture
def reproducible_chain(conn, tmp_path):
    """Same shape as reference_chain, but with a real, checksummed artifact
    file on disk -- reference_chain's '/tmp/x.pkl' is a fake path that
    verify_artifact_integrity() will correctly report as missing, which is
    fine for tests that don't check reproducibility but wrong for ones that
    do (analytics/scorecard.py's reproducibility gate). Mirrors
    tests/phase1a/test_acceptance_30day.py's bootstrapped_chain fixture.
    """
    artifact = tmp_path / "xgb.pkl"
    artifact.write_bytes(b"fake model weights")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    size = artifact.stat().st_size

    conn.execute("INSERT INTO model_artifacts VALUES ('xgb_v1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO model_training_runs VALUES "
        "('run1','xgb_v1','2026-01-01','2026-06-01','{}','2026-06-01T00:00:00Z',?,?,?,'2026-06-01T00:00:00Z')",
        (str(artifact), checksum, size),
    )
    conn.execute("INSERT INTO strategy_versions VALUES ('strat_v1','{}','2026-01-01T00:00:00Z',NULL)")
    conn.execute("INSERT INTO risk_rulesets VALUES ('risk_v1','{}','2026-01-01T00:00:00Z')")
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-07-28T00:00:00Z')"
    )
    conn.commit()
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-07-28T00:00:00Z",
    })
    row = candidates.record_candidate_evaluation_if_concluded(
        conn, "AAPL", "2026-07-28", {}, data_available=True,
        required_models_available=True, evaluation_completed=True,
    )
    return {"manifest_id": "mani_v1", "candidate_event_id": row["candidate_event_id"]}
