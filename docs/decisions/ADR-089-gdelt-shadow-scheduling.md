# ADR-089: Scheduled GDELT Shadow Collection

**Status:** Proposed. Not accepted. The runner script exists; no schedule has been added.
**Decision Type:** Narrow ADR-002 exception, prospective. Adds a scheduled, read-only data collection. No trading decision reads its output.
**Related:** ADR-086 (data-source licensing remediation), ADR-052 (backtest quality gate before any model use).

## 1. Context

- The GDELT shadow logger reads the 15-minute GKG files from `data.gdeltproject.org`. Each file is about 1.5 MB, so one day is about 96 files, roughly 150 MB.
- Output is shadow only. It feeds no decision. Kill criteria are fixed in `analytics/gdelt_shadow.py`: coverage below 80% per covered name, or no out-of-sample signal after about 90 trading days.
- Coverage is limited to seven names (`SHADOW_ALIASES`). The 80% rule is measured per covered name.

## 2. Decision (proposed)

1. Run `scripts/gdelt_shadow_run.py` once per day, after the GKG files for the day are published, covering the previous day.
2. Store output in `logs/gdelt_shadow.jsonl` (gitignored) and copy it weekly to `aara-private`, so the point-in-time record survives the 90-day window of the runner.
3. The schedule lives in a workflow file, which is a frozen path. Adding it needs this ADR's acceptance and a separate workflow change.

## 3. Consequences

- The shadow record grows by about 1 row per covered name per file, a few KB a day.
- Failures are logged and visible in the record. A run that fails is counted against coverage.

## 4. Acceptance

Owner: __________________ Date: __________
