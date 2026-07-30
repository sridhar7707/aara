"""Phase 1A Sprint 6 -- daily acceptance check, per phase1a_requirements.md
Section 14's acceptance criteria. Read-only: verifies, never repairs -- a
broken chain or orphan row is evidence something bypassed the application
layer (a direct DB edit, a code path that skipped append_ledger_row) and
must be investigated, not silently patched forward.

Reuses ledger.integrity.run_integrity_check() for hash-chain verification
and active_deployment_pointer drift detection rather than reimplementing
either -- this script adds the Phase 1A-specific checks on top: candidate/
manifest linkage, EXECUTED-decision completeness, duplicate fingerprints,
and a reproducibility sample.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ledger.db as ledger_db  # noqa: E402
import ledger.integrity as integrity  # noqa: E402
import ledger.reproducibility as repro  # noqa: E402
from bot.trust_ledger.connection import DEFAULT_LEDGER_DB_PATH  # noqa: E402

LOOKBACK_DAYS = 30
REPRODUCIBILITY_SAMPLE_SIZE = 5


def _since(lookback_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()


def check_candidate_linkage(conn, since: str) -> list[str]:
    """Every decision_events row's candidate_event_id must resolve to
    evaluation_completed=1. Already DB-enforced by
    trg_decision_events_requires_completed_evaluation (Phase 0, frozen) --
    re-verified here to catch any code path that bypassed append_ledger_row
    entirely (a direct INSERT, a bug in a future sprint)."""
    rows = conn.execute(
        "SELECT d.decision_id FROM decision_events d "
        "LEFT JOIN candidate_evaluation_events c ON c.candidate_event_id = d.candidate_event_id "
        "WHERE d.timestamp >= ? AND (c.candidate_event_id IS NULL OR c.evaluation_completed != 1)",
        (since,),
    ).fetchall()
    return [r[0] for r in rows]


def check_manifest_linkage(conn, since: str) -> list[str]:
    """Every decision's deployment_manifest_id must reference a manifest
    that reached PROMOTED at some point -- currently-active or since-retired,
    either is legitimate (it was the active manifest when the decision was made)."""
    rows = conn.execute(
        "SELECT DISTINCT decision_id, deployment_manifest_id FROM decision_events WHERE timestamp >= ?",
        (since,),
    ).fetchall()
    bad = []
    for decision_id, manifest_id in rows:
        promoted = conn.execute(
            "SELECT 1 FROM deployment_manifest_events WHERE manifest_id=? AND event_type='PROMOTED' LIMIT 1",
            (manifest_id,),
        ).fetchone()
        if not promoted:
            bad.append(decision_id)
    return bad


def check_executed_completeness(conn, since: str) -> list[str]:
    """Every EXECUTED decision must carry non-empty model_outputs (all 3
    model keys), risk_checks, and data_completeness -- the "100% data
    integrity" half of Section 14's acceptance criteria."""
    rows = conn.execute(
        "SELECT decision_id, model_outputs, risk_checks, data_completeness FROM decision_events "
        "WHERE event_type='EXECUTED' AND timestamp >= ?",
        (since,),
    ).fetchall()
    bad = []
    for decision_id, model_outputs, risk_checks, data_completeness in rows:
        try:
            mo, rc, dc = json.loads(model_outputs), json.loads(risk_checks), json.loads(data_completeness)
        except (TypeError, json.JSONDecodeError):
            bad.append(decision_id)
            continue
        if not mo or not all(k in mo for k in ("xgboost", "lstm", "finbert")) or not rc or not dc:
            bad.append(decision_id)
    return bad


def check_duplicate_fingerprints(conn, since: str) -> list[tuple[str, str]]:
    """No duplicate (asset, action, trading_day) among EXECUTED decisions
    without an intent.override_reason -- decision idempotency, checked
    independently of check_fingerprint's own insert-time enforcement
    (this catches anything that slipped through, e.g. a direct insert)."""
    rows = conn.execute(
        "SELECT decision_id, asset, action, timestamp, intent FROM decision_events "
        "WHERE event_type='EXECUTED' AND timestamp >= ? ORDER BY sequence_number",
        (since,),
    ).fetchall()
    seen: dict[tuple[str, str, str], str] = {}
    duplicates = []
    for decision_id, asset, action, timestamp, intent_json in rows:
        intent = json.loads(intent_json) if intent_json else {}
        if intent.get("override_reason"):
            continue
        key = (asset, action, timestamp[:10])
        if key in seen:
            duplicates.append((decision_id, seen[key]))
        else:
            seen[key] = decision_id
    return duplicates


def sample_reproducibility(conn, sample_size: int = REPRODUCIBILITY_SAMPLE_SIZE) -> list[str]:
    """Runs the FR-0.10 acceptance test against a sample of the most recent
    EXECUTED decisions -- exercises reconstruct_decision_snapshot end-to-end
    against real data, not synthetic fixtures."""
    rows = conn.execute(
        "SELECT decision_id FROM decision_events WHERE event_type='EXECUTED' "
        "ORDER BY sequence_number DESC LIMIT ?",
        (sample_size,),
    ).fetchall()
    failures = []
    for (decision_id,) in rows:
        try:
            repro.acceptance_test_fr_0_10(conn, decision_id)
        except Exception as e:
            failures.append(f"{decision_id}: {e}")
    return failures


def run_check(db_path: str = DEFAULT_LEDGER_DB_PATH, lookback_days: int = LOOKBACK_DAYS) -> dict:
    # init_db (not get_conn) so a DB snapshot pulled before the latest
    # schema.sql change (e.g. constitution_enforcement_events, added
    # post-Phase-0-freeze) gets migrated in place rather than crashing on
    # a missing table -- CREATE TABLE IF NOT EXISTS is a no-op once current.
    conn = ledger_db.init_db(db_path)
    try:
        since = _since(lookback_days)
        integrity_result = integrity.run_integrity_check(conn)
        return {
            "broken_chains": integrity_result["broken_chains"],
            "active_pointer_drift": integrity_result["pointer_drift"],
            "orphan_candidate_linkage": check_candidate_linkage(conn, since),
            "orphan_manifest_linkage": check_manifest_linkage(conn, since),
            "incomplete_executed_decisions": check_executed_completeness(conn, since),
            "duplicate_fingerprints": check_duplicate_fingerprints(conn, since),
            "reproducibility_failures": sample_reproducibility(conn),
        }
    finally:
        conn.close()


def is_clean(results: dict) -> bool:
    return (
        not results["broken_chains"]
        and not results["active_pointer_drift"]
        and not results["orphan_candidate_linkage"]
        and not results["orphan_manifest_linkage"]
        and not results["incomplete_executed_decisions"]
        and not results["duplicate_fingerprints"]
        and not results["reproducibility_failures"]
    )


def main() -> int:
    results = run_check()
    if is_clean(results):
        print(f"Phase 1A acceptance check: CLEAN (trailing {LOOKBACK_DAYS} days)")
        return 0
    print(f"Phase 1A acceptance check: ISSUES FOUND (trailing {LOOKBACK_DAYS} days)")
    for key, value in results.items():
        if value:
            print(f"  {key}: {value}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
