"""Read-only, one-off dry run exercising real sentinel_engine adapter code
against real production trust_ledger.db row shapes (ADR-004 Criterion 3
adapter-level gap).

Reuses scripts/phase1a_verification.py's existing HF fetch mechanism
(fetch_production_dbs / _load_hf_config) rather than duplicating
authentication/configuration. Copies the fetched ledger snapshot into its
own disposable temp directory and opens it with sqlite3 mode=ro only --
never writes to the real repo copies, the HF cache download itself, or its
own disposable copy. Removes the disposable copy on exit.

Scope, deliberately narrow (see the Criterion 3 feasibility review this
script implements):

- Exercises evidence_adapter.to_evidence_records(), recommendation_adapter
  .recommend_entry_action(), and governance_adapter.to_policy_id() -- each
  fed a real, unmodified value taken directly from a real decision_events
  row (model_outputs parsed with json.loads(), or the bare action string).
- Does NOT exercise decision_adapter.to_decision() or execution_adapter
  .to_execution_outcome() -- both require a derived translation/
  reconstruction layer rather than a direct real-row match; exercising them
  here would create the appearance of adapter-level real-data coverage
  without actually providing it.
- Calls no service (DecisionService/EvidenceService), no persistence path,
  no execution, no retraining, and makes no network call beyond the
  existing HF snapshot download.
- Emits nothing -- this is a console-only diagnostic, not a Phase 1A
  evidence-producing tool. It does not touch docs/analysis/phase1a_verification/.

Usage:
    python scripts/verify_adapters_against_real_ledger.py
    python scripts/verify_adapters_against_real_ledger.py --sample-size 10
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.phase1a_verification import _load_hf_config, fetch_production_dbs  # noqa: E402
from sentinel_engine.adapters.evidence_adapter import to_evidence_records  # noqa: E402
from sentinel_engine.adapters.governance_adapter import to_policy_id  # noqa: E402
from sentinel_engine.adapters.recommendation_adapter import recommend_entry_action  # noqa: E402

DEFAULT_SAMPLE_SIZE = 10

_SELECT_SAMPLE = (
    "SELECT decision_id, action, model_outputs FROM decision_events "
    "WHERE model_outputs IS NOT NULL AND action IS NOT NULL "
    "ORDER BY sequence_number DESC LIMIT ?"
)


def _fetch_disposable_ledger_copy(work_dir: Path) -> dict:
    """Reuses phase1a_verification.py's own fetch mechanism. Returns the
    fetch result dict ({"status": "ok"/"unavailable", "ledger": {...}})."""
    repo_id, token = _load_hf_config()
    return fetch_production_dbs(work_dir, repo_id=repo_id, token=token)


def run(sample_size: int = DEFAULT_SAMPLE_SIZE) -> bool:
    """Returns True on overall PASS (every sampled row cleared all three
    adapter paths), False otherwise. Never writes to any database."""
    work_dir = Path(tempfile.mkdtemp(prefix="verify_adapters_"))
    print(f"Disposable working directory: {work_dir}")
    overall_pass = False
    try:
        fetch_result = _fetch_disposable_ledger_copy(work_dir)
        if fetch_result.get("status") != "ok":
            print(f"FAIL -- could not obtain production ledger snapshot: "
                  f"{fetch_result.get('detail', 'unknown error')}")
            return False

        ledger_info = fetch_result["ledger"]
        print(f"Source: HF repo_id={fetch_result.get('repo_id')} "
              f"revision={ledger_info.get('revision')}")

        disposable_ledger = work_dir / "ledger_readonly_copy.db"
        shutil.copy2(ledger_info["src"], disposable_ledger)

        conn = sqlite3.connect(f"file:{disposable_ledger}?mode=ro", uri=True)
        try:
            rows = conn.execute(_SELECT_SAMPLE, (sample_size,)).fetchall()
        finally:
            conn.close()

        print(f"Rows sampled: {len(rows)} (requested up to {sample_size}, "
              f"most recent by sequence_number, non-null model_outputs/action)")

        evidence_ok = recommendation_ok = policy_ok = 0
        failures: list[str] = []

        for decision_id, action, model_outputs_raw in rows:
            try:
                model_outputs = json.loads(model_outputs_raw)
            except (TypeError, ValueError) as exc:
                failures.append(f"{decision_id}: model_outputs JSON parse failed "
                                 f"-- {type(exc).__name__}: {exc}")
                continue

            try:
                to_evidence_records(model_outputs)
                evidence_ok += 1
            except Exception as exc:
                failures.append(f"{decision_id}: evidence_adapter.to_evidence_records "
                                 f"failed -- {type(exc).__name__}: {exc}")

            try:
                recommend_entry_action(model_outputs)
                recommendation_ok += 1
            except Exception as exc:
                failures.append(f"{decision_id}: recommendation_adapter"
                                 f".recommend_entry_action failed -- "
                                 f"{type(exc).__name__}: {exc}")

            try:
                to_policy_id({"action": action})
                policy_ok += 1
            except Exception as exc:
                failures.append(f"{decision_id}: governance_adapter.to_policy_id "
                                 f"failed -- {type(exc).__name__}: {exc}")

        print(f"evidence_adapter.to_evidence_records:              {evidence_ok}/{len(rows)}")
        print(f"recommendation_adapter.recommend_entry_action:     {recommendation_ok}/{len(rows)}")
        print(f"governance_adapter.to_policy_id:                   {policy_ok}/{len(rows)}")

        if failures:
            print(f"\nFailures ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
        else:
            print("\nFailures: none")

        overall_pass = (
            len(rows) > 0
            and evidence_ok == len(rows)
            and recommendation_ok == len(rows)
            and policy_ok == len(rows)
        )
        print(f"\nOverall result: {'PASS' if overall_pass else 'FAIL'}")
        return overall_pass
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"Disposable working directory removed: {work_dir}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only: exercise sentinel_engine adapters against real "
                    "production trust_ledger.db decision_events rows."
    )
    ap.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    args = ap.parse_args()
    passed = run(sample_size=args.sample_size)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
