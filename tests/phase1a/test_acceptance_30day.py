"""Tests for scripts/phase1a_daily_acceptance_check.py (Phase 1A Sprint 6).

Builds a synthetic multi-day dataset exercising the full pipeline --
candidate -> decision -> risk evaluation -> outcome -- reusing the same
fixture patterns established across Sprints 1-5, and asserts the
acceptance checks hold clean, then verifies each check function actually
catches the specific problem it claims to.
"""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ledger.db as ledger_db  # noqa: E402
import ledger.ledger as ledger_svc  # noqa: E402
import bot.trust_ledger.candidates as candidates  # noqa: E402
import bot.trust_ledger.decisions as decisions  # noqa: E402
import bot.trust_ledger.outcomes as outcomes  # noqa: E402
from bot.strategy.model_output_adapter import build_model_outputs  # noqa: E402
from scripts import phase1a_daily_acceptance_check as check_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_module_cache():
    candidates._recorded_today.clear()
    candidates._recorded_date = ""
    yield
    candidates._recorded_today.clear()
    candidates._recorded_date = ""


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "acceptance_test.db")
    c = ledger_db.init_db(db_path)
    yield c
    c.close()


@pytest.fixture
def bootstrapped_chain(conn, tmp_path):
    """A real, promoted manifest with a real checksummed artifact file --
    close enough to scripts/phase1a_bootstrap_ledger.py's shape for
    sample_reproducibility() to exercise reconstruct_decision_snapshot
    against, not a stub."""
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
        "('mani_v1','{\"xgboost\":\"run1\"}','risk_v1','strat_v1','fp_v1','{}','2026-06-15T00:00:00Z')"
    )
    conn.commit()
    # append_ledger_row, not a raw INSERT with a fake hash -- this table's
    # chain is verified by check_hash_chains below, and a fabricated hash
    # would make the chain genuinely broken, not just look broken.
    ledger_svc.append_ledger_row(conn, "cost_models", {
        "cost_model_id": "cost_model_v1", "spread_assumption": 0.001, "slippage_assumption": 0.001,
        "commission_rules": {}, "tax_assumptions": {}, "created_at": "2026-06-15T00:00:00Z",
    })

    ledger_svc.transition_manifest(conn, "mani_v1", "CREATED", "2026-06-15T00:00:00Z")
    ledger_svc.transition_manifest(conn, "mani_v1", "TESTING_STARTED", "2026-06-15T00:01:00Z")
    ledger_svc.transition_manifest(conn, "mani_v1", "REVIEW_REQUESTED", "2026-06-15T00:02:00Z")
    approval = ledger_svc.append_ledger_row(conn, "approval_events", {
        "approval_id": "APR-1", "timestamp": "2026-06-15T00:03:00Z", "subject_type": "MANIFEST_PROMOTION",
        "subject_id": "mani_v1", "decision": "APPROVE", "reason_checklist": {}, "reason_comment": "ok",
        "reviewer": "tester",
    })
    ledger_svc.transition_manifest(conn, "mani_v1", "APPROVED", "2026-06-15T00:04:00Z",
                                   approval_event_id=approval["approval_id"])
    ledger_svc.transition_manifest(conn, "mani_v1", "PROMOTED", "2026-06-15T00:05:00Z")
    return "mani_v1"


def _write_full_decision(conn, manifest_id, asset, day, action="BUY", event_type="EXECUTED"):
    """One full candidate -> decision -> (outcome if BUY) cycle for one
    (asset, day), mirroring what the live pipeline actually produces."""
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, asset, day, {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    row = decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset=asset, action=action,
        event_type=event_type, portfolio_snapshot={"value": 10000.0}, market_context={"regime": "bull"},
        model_outputs=build_model_outputs(0.7, 0.6, 0.2), risk_checks={"gates": []}, final_confidence=0.65,
        deployment_manifest_id=manifest_id, intent=decisions.build_intent(action),
        data_completeness=decisions.build_data_completeness(),
        timestamp=f"{day}T10:00:00Z",
    )
    if action == "BUY" and event_type == "EXECUTED":
        outcomes.write_decision_outcome_event(
            conn, asset, row["decision_id"], f"{day}T15:00:00Z", 0.02, 3,
        )
    return row


def test_clean_multi_day_dataset_passes_acceptance(conn, bootstrapped_chain):
    _write_full_decision(conn, bootstrapped_chain, "AAPL", "2026-07-01")
    _write_full_decision(conn, bootstrapped_chain, "MSFT", "2026-07-02")
    _write_full_decision(conn, bootstrapped_chain, "AAPL", "2026-07-15", action="REJECT", event_type="QUALIFIED_REJECTION")

    results = {
        "broken_chains": {t: b for t, b in ledger_svc.verify_all_chains(conn).items() if b},
        "orphan_candidate_linkage": check_mod.check_candidate_linkage(conn, "2026-01-01T00:00:00Z"),
        "orphan_manifest_linkage": check_mod.check_manifest_linkage(conn, "2026-01-01T00:00:00Z"),
        "incomplete_executed_decisions": check_mod.check_executed_completeness(conn, "2026-01-01T00:00:00Z"),
        "duplicate_fingerprints": check_mod.check_duplicate_fingerprints(conn, "2026-01-01T00:00:00Z"),
        "reproducibility_failures": check_mod.sample_reproducibility(conn),
        "active_pointer_drift": False,
    }
    assert check_mod.is_clean(results)


def test_manifest_linkage_catches_never_promoted_manifest(conn, bootstrapped_chain):
    """A decision referencing a manifest that was created but never
    PROMOTED shouldn't be possible from the real pipeline (which only ever
    has an active_deployment_pointer for a promoted manifest) -- but is
    reachable via a direct insert, and the check must catch it."""
    conn.execute(
        "INSERT INTO deployment_manifests VALUES "
        "('mani_unpromoted','{}','risk_v1','strat_v1','fp_v1','{}','2026-07-01T00:00:00Z')"
    )
    conn.commit()
    row = _write_full_decision(conn, "mani_unpromoted", "TSLA", "2026-07-01")
    bad = check_mod.check_manifest_linkage(conn, "2026-01-01T00:00:00Z")
    assert row["decision_id"] in bad


def test_executed_completeness_catches_missing_model_outputs(conn, bootstrapped_chain):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, "NVDA", "2026-07-01", {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    row = decisions.write_decision_event(
        conn, candidate_event_id=cand["candidate_event_id"], asset="NVDA", action="BUY",
        event_type="EXECUTED", portfolio_snapshot={}, market_context={}, model_outputs={},  # empty!
        risk_checks={"gates": []}, final_confidence=0.6, deployment_manifest_id=bootstrapped_chain,
        intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
    )
    bad = check_mod.check_executed_completeness(conn, "2026-01-01T00:00:00Z")
    assert row["decision_id"] in bad


def test_duplicate_fingerprint_catches_same_day_duplicate_without_override(conn, bootstrapped_chain):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, "GOOG", "2026-07-01", {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    kwargs = dict(
        candidate_event_id=cand["candidate_event_id"], asset="GOOG", action="BUY", event_type="EXECUTED",
        portfolio_snapshot={}, market_context={}, model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65, deployment_manifest_id=bootstrapped_chain,
        intent=decisions.build_intent("BUY"), data_completeness=decisions.build_data_completeness(),
    )
    first = decisions.write_decision_event(conn, timestamp="2026-07-01T09:30:00Z", **kwargs)
    second = decisions.write_decision_event(conn, timestamp="2026-07-01T09:35:00Z", **kwargs)

    duplicates = check_mod.check_duplicate_fingerprints(conn, "2026-01-01T00:00:00Z")
    ids_involved = {d for pair in duplicates for d in pair}
    assert first["decision_id"] in ids_involved
    assert second["decision_id"] in ids_involved


def test_duplicate_fingerprint_allows_override(conn, bootstrapped_chain):
    cand = candidates.record_candidate_evaluation_if_concluded(
        conn, "AMZN", "2026-07-01", {}, data_available=True, required_models_available=True,
        evaluation_completed=True,
    )
    base_kwargs = dict(
        candidate_event_id=cand["candidate_event_id"], asset="AMZN", action="BUY", event_type="EXECUTED",
        portfolio_snapshot={}, market_context={}, model_outputs=build_model_outputs(0.7, 0.6, 0.2),
        risk_checks={"gates": []}, final_confidence=0.65, deployment_manifest_id=bootstrapped_chain,
        data_completeness=decisions.build_data_completeness(),
    )
    decisions.write_decision_event(
        conn, intent=decisions.build_intent("BUY"), timestamp="2026-07-01T09:30:00Z", **base_kwargs,
    )
    decisions.write_decision_event(
        conn, intent=decisions.build_intent("BUY", override_reason="manual re-entry"),
        timestamp="2026-07-01T09:35:00Z", **base_kwargs,
    )
    duplicates = check_mod.check_duplicate_fingerprints(conn, "2026-01-01T00:00:00Z")
    assert duplicates == []


def test_sample_reproducibility_catches_checksum_mismatch(conn, bootstrapped_chain, tmp_path):
    _write_full_decision(conn, bootstrapped_chain, "AAPL", "2026-07-01")
    artifact_path = conn.execute(
        "SELECT artifact_storage_ref FROM model_training_runs WHERE training_run_id='run1'"
    ).fetchone()[0]

    assert check_mod.sample_reproducibility(conn) == []  # clean before tampering

    with open(artifact_path, "wb") as f:
        f.write(b"tampered weights, a different length entirely")

    failures = check_mod.sample_reproducibility(conn)
    assert len(failures) == 1
    assert "NFR-8" in failures[0]


def test_run_check_end_to_end_against_a_real_db_file(conn, bootstrapped_chain):
    """run_check() opens its own connection from a path (unlike the other
    tests here, which call the check_* functions directly against an
    already-open fixture connection) -- exercises that real entry point."""
    _write_full_decision(conn, bootstrapped_chain, "AAPL", "2026-07-01")
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    conn.close()

    results = check_mod.run_check(db_path=db_path)
    assert check_mod.is_clean(results)
