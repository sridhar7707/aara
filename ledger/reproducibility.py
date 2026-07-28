"""FR-0.10 reproducibility reconstruction and NFR-8 artifact retention
verification. (NFR-8, not NFR-6 -- phase0_data_model.md Section 7 uses
NFR-8 specifically to avoid colliding with ai_trust_architecture_requirements.md
Section 7's own, unrelated NFR-6 "Cost realism".)

reconstruct_decision_snapshot() resolves a decision_id to everything the AI
saw and used, using only historical tables -- never current live state
(no reads of active_deployment_pointer, no "current" model/strategy
lookups). This is what makes the reconstruction trustworthy months or years
after a manifest has been retired and superseded many times over.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from ledger.ledger import _deserialize_row, get_decision_state  # Group A JSON/bool-aware row reconstruction

_GROUP_B_JSON_FIELDS: dict[str, set[str]] = {
    "deployment_manifests": {"component_training_runs", "runtime_environment"},
    "model_training_runs": {"validation_metrics"},
    "strategy_versions": {"rules"},
    "risk_rulesets": {"rules"},
}


def _fetch_row(conn: sqlite3.Connection, table: str, id_col: str, id_val: str) -> dict | None:
    cur = conn.execute(f"SELECT * FROM {table} WHERE {id_col}=?", (id_val,))
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    result = dict(zip(cols, row))
    for field in _GROUP_B_JSON_FIELDS.get(table, set()):
        if result.get(field) is not None:
            result[field] = json.loads(result[field])
    return result


def reconstruct_decision_snapshot(conn: sqlite3.Connection, decision_id: str) -> dict:
    """Resolve decision_id -> candidate eligibility -> deployment manifest ->
    model training runs (one per component) -> strategy version -> risk
    ruleset, entirely from historical (Group A/B) tables. Raises ValueError
    if the decision or any of its referenced records can't be found --
    a broken reference is a data-integrity problem worth surfacing loudly,
    not a reason to return a partial snapshot silently.
    """
    cur = conn.execute("SELECT * FROM decision_events WHERE decision_id=?", (decision_id,))
    raw = cur.fetchone()
    if raw is None:
        raise ValueError(f"No such decision_id: {decision_id}")
    cols = [d[0] for d in cur.description]
    decision_row = dict(zip(cols, raw))
    decision = _deserialize_row("decision_events", decision_row)
    decision["decision_id"] = decision_row["decision_id"]
    # outcome_state is not a decision_events column (v1.2) -- it's derived,
    # read here from the decision_state view rather than the row itself.
    decision["outcome_state"] = get_decision_state(conn, decision_id)

    candidate = _fetch_row(
        conn, "candidate_evaluation_events", "candidate_event_id", decision_row["candidate_event_id"]
    )
    if candidate is None:
        raise ValueError(
            f"decision {decision_id} references missing candidate_event_id "
            f"{decision_row['candidate_event_id']!r}"
        )

    manifest = _fetch_row(
        conn, "deployment_manifests", "manifest_id", decision_row["deployment_manifest_id"]
    )
    if manifest is None:
        raise ValueError(
            f"decision {decision_id} references missing deployment_manifest_id "
            f"{decision_row['deployment_manifest_id']!r}"
        )

    training_runs: dict[str, dict] = {}
    for component, training_run_id in manifest["component_training_runs"].items():
        run = _fetch_row(conn, "model_training_runs", "training_run_id", training_run_id)
        if run is None:
            raise ValueError(
                f"manifest {manifest['manifest_id']} references missing training_run_id "
                f"{training_run_id!r} for component {component!r}"
            )
        training_runs[component] = run

    strategy = _fetch_row(conn, "strategy_versions", "strategy_version_id", manifest["strategy_version_id"])
    if strategy is None:
        raise ValueError(
            f"manifest {manifest['manifest_id']} references missing strategy_version_id "
            f"{manifest['strategy_version_id']!r}"
        )

    risk_ruleset = _fetch_row(conn, "risk_rulesets", "risk_ruleset_id", manifest["risk_ruleset_id"])
    if risk_ruleset is None:
        raise ValueError(
            f"manifest {manifest['manifest_id']} references missing risk_ruleset_id "
            f"{manifest['risk_ruleset_id']!r}"
        )

    return {
        "decision": decision,
        "candidate_evaluation": candidate,
        "deployment_manifest": manifest,
        "model_training_runs": training_runs,
        "strategy_version": strategy,
        "risk_ruleset": risk_ruleset,
    }


def verify_artifact_integrity(training_run: dict) -> bool:
    """NFR-8: confirm a training run's serialized model file still exists
    and matches its recorded checksum -- proves the retained file is
    bit-for-bit the one actually used, not a same-named replacement.

    Checks artifact_size_bytes (v1.2) first, if recorded -- a cheap
    file-size comparison that rejects an obviously-wrong file without
    reading and hashing the whole thing. This is a fast-fail, not a
    replacement for the checksum: a size match proves nothing on its own,
    but a size *mismatch* means the checksum will fail too, so there's no
    reason to hash first."""
    path = training_run.get("artifact_storage_ref")
    expected = training_run.get("artifact_checksum")
    if not path or not expected or not os.path.exists(path):
        return False
    expected_size = training_run.get("artifact_size_bytes")
    if expected_size is not None and os.path.getsize(path) != expected_size:
        return False
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected


def acceptance_test_fr_0_10(conn: sqlite3.Connection, decision_id: str) -> None:
    """Formal FR-0.10 acceptance test. Raises AssertionError on any
    violation; passes silently otherwise."""
    snapshot = reconstruct_decision_snapshot(conn, decision_id)
    for component, run in snapshot["model_training_runs"].items():
        assert verify_artifact_integrity(run), (
            f"NFR-8 violated: artifact for {component} "
            f"({run['training_run_id']}) missing or checksum mismatch"
        )
    # Extend here once the actual inference pipeline exists: re-run each
    # component model against the recorded inputs and confirm the output
    # matches snapshot["decision"]["model_outputs"][component] within
    # tolerance. Not buildable yet -- no inference pipeline exists in
    # Phase 0 (trading/decision logic is explicitly out of scope here).
