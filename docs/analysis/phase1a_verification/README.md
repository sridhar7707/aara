# Phase 1A §14 Verification — evidence directory

Purpose: hold the dated, persisted evidence produced by
`scripts/phase1a_verification.py` — the read-only orchestrator that runs the
automatable Phase 1A **Section 14** acceptance checks against the accumulated
**production** Hugging Face-synced snapshots of `trust_ledger.db` and
`trades.db`.

Authority: created under the Task 5 read-only design review (no `.github/workflows/`
change, no ADR, no ADR-002 exception). ADR-071 (Accepted) scopes §14's
"single decision-creation path / second write path" wording; this tooling
implements no interpretation and changes no production behaviour.

## Invocation

```
# Full run against production snapshots (writes a dated evidence pair here):
python scripts/phase1a_verification.py

# Labelled dry-run before the window opens (does NOT start the 30-day window):
python scripts/phase1a_verification.py --label pre-window-baseline

# Print only, write nothing:
python scripts/phase1a_verification.py --no-emit

# Also require the snapshot to be recent (for a live/ongoing window):
python scripts/phase1a_verification.py --require-recent --staleness-hours 24

# Offline / test: skip the HF fetch and use explicit DB paths:
python scripts/phase1a_verification.py --ledger-db /path/trust_ledger.db --trades-db /path/trades.db
```

`--window-start` / `--window-end` default to `2026-07-28` / `2026-08-27`
(inclusive). `--output-dir` defaults to this directory.

## Verdict states

| Verdict | Meaning |
| --- | --- |
| `PASS` | The check ran against a fresh, covering snapshot and established the criterion. |
| `FAIL` | The check ran and found a concrete violation (offending IDs listed). |
| `INCONCLUSIVE` | The check cannot prove the criterion from available durable evidence — e.g. an EXECUTED-only check with **zero** EXECUTED rows (reported as *vacuous*, never `PASS`); the FinBERT provenance gap; failed writes; the 30-consecutive-days enumeration. |
| `SNAPSHOT_UNAVAILABLE` | The production snapshot could not be fetched (no token, network, 404). Forces the overall verdict; no `PASS` is emitted. |
| `SNAPSHOT_STALE` | The snapshot does not cover the window (`max event date < window end`), or `--require-recent` is set and it is older than `--staleness-hours`. Forces the overall verdict. |

**`INCONCLUSIVE` is never treated as `PASS`.** The orchestrator **never emits an
overall `PASS` on its own**: `FAILED_WRITES` and `PER_DAY_ENUMERATION`
(30 consecutive days) are inherently `INCONCLUSIVE` and require a named human
reviewer to adjudicate them against the enumeration and record acceptance per
ADR-058 D2. Overall `PASS` would require every check `PASS` and no `INCONCLUSIVE`.

## Read-only DB safety model

* Production DBs are obtained **only** via `huggingface_hub.hf_hub_download`
  (same dataset `ksri77/ai-trading-bot-db`, same `HF_TOKEN` convention) — never
  `bot/monitor/sync_db.py`'s `pull_db()` / `pull_ledger_db()`, which overwrite
  the repo copies.
* The downloaded files land in the HF cache; the orchestrator **copies them
  into a disposable temporary directory** and operates only on those copies.
* `scripts/phase1a_daily_acceptance_check.run_check()` and `ledger.db.init_db()`
  migrate the SQLite file they open, so they are pointed **only** at the
  temp copy — never at `data/trust_ledger.db`, `trades.db`, or the HF cache.
* Every other read uses `mode=ro`. The temp directory is removed after the run.
* `tests/phase1a/test_phase1a_verification.py` asserts the source DB file
  hash + mtime are unchanged and the repo production DBs are untouched.

## Evidence naming

`<UTC-timestamp>-phase1a-verification[-<label>].{json,md}`
(e.g. `20260910T130501Z-phase1a-verification-pre-window-baseline.json`).
Append-only: `write_evidence` refuses to overwrite an existing file.

## Each evidence record contains

Run timestamp (UTC); HF dataset id and resolved revision per DB; source
SHA-256 per DB; snapshot max ledger timestamp; window start/end; per-check
`id` / `name` / `verdict` / `detail` / `counts` / `offending_ids`; the full
per-calendar-day evidence enumeration; the overall verdict.

## What a run does NOT do

* It does **not** close Phase 1A §14 or ADR-004 Criterion 1 (ADR-004 remains
  Deferred).
* It does **not** start the 30-consecutive-day validation window. A
  `--label pre-window-baseline` run is a labelled dry-run only.
* An overall verdict other than `FAIL` still requires human adjudication of the
  `INCONCLUSIVE` items and a recorded sign-off before §14 can be considered met.
* Scheduling this orchestrator (a `.github/workflows/` change) is deferred and
  would require its own scoped ADR-002 exception.
