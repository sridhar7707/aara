"""Direct tests for bot/trust_ledger/connection.py and ids.py -- these are
only exercised indirectly elsewhere (via the bootstrap script and
candidates.py), so arch_review.py correctly flags them as having no direct
test coverage. Closing that here rather than dismissing it as a checker
naming-convention false positive."""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot.trust_ledger.connection import get_ledger_conn  # noqa: E402
from bot.trust_ledger.ids import (  # noqa: E402
    new_candidate_event_id, new_decision_id, new_event_id,
    new_outcome_id, new_approval_id, new_cost_model_id,
)


def test_get_ledger_conn_opens_and_initializes_schema(tmp_path):
    db_path = str(tmp_path / "infra_test.db")
    conn = get_ledger_conn(db_path)
    try:
        assert isinstance(conn, sqlite3.Connection)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "decision_events" in tables
        assert "candidate_evaluation_events" in tables
    finally:
        conn.close()


def test_get_ledger_conn_is_reusable_across_calls(tmp_path):
    """Second call against the same path must not error or re-wipe data
    (schema.sql uses CREATE TABLE IF NOT EXISTS throughout)."""
    db_path = str(tmp_path / "reuse_test.db")
    conn1 = get_ledger_conn(db_path)
    conn1.execute(
        "INSERT INTO model_artifacts VALUES ('a1','xgboost','v1',NULL,'fh1','2026-01-01T00:00:00Z')"
    )
    conn1.commit()
    conn1.close()

    conn2 = get_ledger_conn(db_path)
    row = conn2.execute("SELECT artifact_id FROM model_artifacts WHERE artifact_id='a1'").fetchone()
    assert row == ("a1",)
    conn2.close()


def test_id_generators_produce_correctly_prefixed_unique_ids():
    ids = [
        new_candidate_event_id("AAPL"),
        new_decision_id("AAPL"),
        new_event_id(),
        new_event_id("AAPL"),
        new_outcome_id("AAPL"),
        new_approval_id(),
    ]
    assert len(ids) == len(set(ids))  # all unique
    assert ids[0].startswith("CAND-")
    assert ids[1].startswith("DEC-")
    assert ids[2].startswith("RISK-")
    assert "AAPL" in ids[0]
    assert "AAPL" in ids[1]
    assert "NA" in ids[2]  # no symbol passed
    assert ids[4].startswith("OUT-")
    assert ids[5].startswith("APR-")


def test_id_generators_called_twice_never_collide():
    first = new_decision_id("AAPL")
    second = new_decision_id("AAPL")
    assert first != second


def test_cost_model_id_is_human_labeled_not_random():
    """Documented exception (see ids.py docstring) -- no collision
    protection by design, cost models are low-cardinality/human-versioned."""
    assert new_cost_model_id("v1") == "cost_model_v1"
    assert new_cost_model_id("v1") == new_cost_model_id("v1")  # deterministic, not unique
