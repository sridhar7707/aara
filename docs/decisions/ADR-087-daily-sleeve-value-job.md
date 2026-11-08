# ADR-087: Daily Sleeve Value Job (Read/Write Split, Public-Repo Rules)

**Status:** Accepted by ksri77 on 2026-11-08 ("i approve adr-087"), for the structure, the schema rules, the status enum, the credential rules and the branch protection requirements. The **publication option** (section 4) is open and must be confirmed by the owner before the first row is published.
**Decision Type:** Extends ADR-084 (workflow) and amends ADR-086 section 1.5 (daily sleeve value). Does not touch trading code, stop logic, sizing, or any limit.

## Context
ADR-086 defers a daily sleeve value. A daily job needs the Alpaca paper key. The repository is public, so anything pushed to a public branch is readable and cannot be fully withdrawn once copied or cached.

## 1. Structure: read job and write job
- **Read job.** `permissions: contents: read`. Holds the Alpaca paper key in one step only. Makes read-only calls (`get_account`, `get_all_positions`, `get_clock`). Writes one row as a workflow artifact. Never pushes.
- **Write job.** `permissions: contents: write`. Holds no Alpaca secret. Downloads the artifact, validates it against the schema in section 3, and appends it to the data branch. Declares `needs:` on the read job.
- Workflow-level permissions are removed in favour of per-job permissions.
- The read job uses `persist-credentials: false`. Its Python dependencies are pinned to exact versions (including `alpaca-py`). The job does not print the environment or run with shell tracing.
- The Alpaca endpoint is checked with `assert_paper_endpoint` before any call. A live endpoint is refused.

## 2. Credentials
- The job reuses the existing repository secrets `ALPACA_KEY` and `ALPACA_SECRET`. These are already used by the trading workflows and are paper-only. A dedicated key would be preferable if Alpaca provides one; this is recorded as an open question, not a requirement.
- No environment is created, because a repository-level secret would be readable by the same jobs regardless.
- If a live or other-broker key ever replaces the paper key, this job must be removed first.

## 3. Row schema and rules
- **Fields:** `date` (New York calendar date, ISO), `asof_utc`, `status`, `error_class`, `sleeve_value` (number or empty), per-symbol `qty`, `broker_price`, `market_value` for overlay symbols, `broker_overlay_value`, `held_symbols`, `price_flag`.
- **Never in any row:** account identifier, account equity, cash, order identifiers, exception text.
- **`status` enum:** `ok`, `market_closed`, `unreadable`, `refused`.
- **`error_class` enum:** `auth`, `http_4xx`, `http_5xx`, `timeout`, `no_account`, `other`. Exception text is never written.
- **`unreadable` never carries `sleeve_value` 0.** An empty value is the only way to record an unreadable account.
- **`ok` with no overlay holdings** records `sleeve_value` 0.0 and an empty `held_symbols`. This is distinct from `unreadable`.
- **Validation.** The write job rejects any row with a non-numeric field where a number is required, an unknown enum value, a malformed date, or an extra field. A rejected row fails the job.
- **Append-only.** Rows are never edited. A date that already has an `ok` row is skipped. The latest row per date is authoritative.
- **Stale price flag.** `price_flag = stale` when the broker price differs from the same-date official close in the price log by more than **1%**. The threshold is fixed here, before the first row.
- **Missed days.** A trading day in the last five with no row fails the workflow. No backfill is performed (ADR-084).
- Daily rows are **supplementary**. They are not a verdict input. The ADR-086 verdict stays on month-end data.

## 4. Publication (OPEN: owner to confirm)
Two options. The owner must choose one before the first row is published.

- **Option A (recommended by the reviewers).** Publish to the public data branch only: sleeve value indexed to 100 at the start, daily percentage returns, drawdown, and the SPY comparison on the same basis. No dollar amounts. Raw dollar rows go to a private repository owned by the owner.
- **Option B.** Publish dollar values to the public data branch, as in section 3. The owner accepts that the figures are permanently public.

The schema in section 3 applies to option B. Option A uses the indexed fields only, and the write job rejects any dollar field.

## 5. Branch protection (owner action in GitHub settings)
- `forward-log-data`: ruleset blocking force-push and deletion. Required before the first write job runs.
- `main`: ruleset requiring changes through a pull request, with the owner as the bypass actor. Required before the write job is merged.
- These cannot be applied by an agent. The owner applies them and confirms.

## 6. Failure handling
- A failed read or an invalid row fails the workflow and leaves no partial data on the branch (the write job writes all or nothing).
- The recovery steps are: check the key against the paper dashboard if the error class is `auth` (never paste a key into a log or an issue); rerun the workflow, which skips an existing `ok` date.
- Never force-push the data branch, never edit a row, and never point the job at a non-paper endpoint.

## Concurrency
The read job and write job share the existing `forward-log` concurrency group, with `cancel-in-progress: false`.

## Open questions (recorded, not blocking)
- Whether Alpaca offers a read-only or dedicated paper key. Assumed not until verified.
- Whether the paper account permits two key pairs. Not needed while the shared key is used.

## Rollback
Disable the workflow. The data branch remains as the record of every row written.

## Acceptance
- Accepted by ksri77 on 2026-11-08 for sections 1, 2, 3, 5, 6 and the concurrency rule.
- Section 4 (publication): **pending owner choice** (Option A or B).
