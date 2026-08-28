# ADR-055 — Trading Intelligence: Read-Only Consumption of the Published `trades.db` HuggingFace Dataset Snapshot

**Status:** Accepted
**Date Proposed:** 2026-08-27
**Date Accepted:** 2026-08-27
**Decision Type:** Architecture / Governance — External Data-Source Admission (read-only consumer)
**Related ADRs:** ADR-002 (bot/dashboard/scheduler frozen — not imported here),
ADR-004 (Sentinel-ledger ownership deferred; the "Q1" question about hash-chained
event tables — not touched here), ADR-023 (workflow exception precedent —
deferred to ADR-056 if a workflow change is chosen), ADR-035 (documented
multi-process `trades.db`-from-HuggingFace pull hazard — directly addressed
below)

---

## 1. Context

Units 1–3's four SQLite-backed adapters —
`legacy_capital_source.py`, `legacy_regime_source.py`, `legacy_position_source.py`,
`legacy_candidate_screening_source.py` — read `trades.db` at a fixed relative
path (`_DB_PATH = "trades.db"`), each opening its own
`sqlite3.connect("file:trades.db?mode=ro", uri=True)` read-only connection and
importing nothing under `bot/`/`dashboard/`/`scheduler/`/`database/`/`ledger/`
(`legacy_candidate_screening_source.py:20-27`). Their own docstrings state the
gap: *"the deployed Trading Intelligence HF Space has no mechanism today to
obtain `trades.db` … until a separate sync step is added, `get_*()` will
consistently return `None`, and callers fall back to the existing unavailable
section."*

**A read-only pull primitive for exactly this file already exists in the
repository, in two independent protected locations:**

- `dashboard/data.py:142-159` `_sync_db()`:
  `hf_hub_download(repo_id=HF_REPO_ID, filename="trades.db",
  repo_type="dataset", token=HF_TOKEN or None, force_download=True)` →
  `shutil.copy(cached, DB_PATH)`. In that module, `HF_REPO_ID` is a **local
  alias** that resolves from `HF_DB_REPO_ID` first (`dashboard/data.py:21`:
  `os.getenv("HF_DB_REPO_ID", os.getenv("HF_REPO_ID", "ksri77/ai-trading-bot-db"))`);
  it is the same dataset repository identifier, not a different one. Runs behind
  a TTL (`_HF_SYNC_TTL`); a 404 deletes the local copy. `token=None` works for a
  public dataset repo.
- `scheduler/startup_job.py:59-73` `_sync_db()`: the same
  `hf_hub_download(repo_id=HF_DB_REPO_ID, filename="trades.db",
  repo_type="dataset")` pull.

**The writer / publisher is the bot**, via `bot/monitor/sync_db.py`
(`HfApi().upload_file(...)`), driven by `config.HF_DB_REPO_ID`
(default `ksri77/ai-trading-bot-db`, a `dataset` repo). Nothing in
`applications/trading_intelligence/` writes to, or should write to, that repo.

**Freshness / staleness.** The published snapshot is only as current as the
bot's last successful upload. `legacy_candidate_screening_source.py` already
handles this correctly — it returns `screened_at` verbatim and its docstring
requires the caller to *"render the literal persisted date so stale local data …
is never presented as a fresh, current-day result."*
`legacy_regime_source.py` follows the same rule.

**WAL/SHM.** The `-wal`/`-shm` sidecar files exist only next to a database with a
live writer holding a WAL-mode connection. A downloaded standalone `trades.db`
snapshot opened `mode=ro` needs no `-wal`/`-shm` companion and no checkpoint —
`dashboard/data.py` sets `PRAGMA journal_mode=WAL` only for its *own* local
writes, which a pure consumer does not perform.

**ADR-035 hazard.** ADR-035's Context warns that multiple processes pulling
"the same `trades.db` from HuggingFace" and then acting on it can "submit
duplicate orders, and race." That hazard is about *writers/traders* sharing a
pulled DB. Trading Intelligence places no orders and writes nothing, so the
duplicate-order race does not apply; the residual concern is only
partial-file / mid-download read, addressed in §2.

## 2. Decision

**Trading Intelligence may obtain a read-only, ephemeral local snapshot of
`trades.db` from the existing published HuggingFace *dataset* repository, as a
consumer only.**

1. **Source.** The existing published dataset repo identified by
   `config.HF_DB_REPO_ID` (today `ksri77/ai-trading-bot-db`), file
   `trades.db`, `repo_type="dataset"`. No new repo is created.
2. **Mechanism.** A small Trading-Intelligence-owned primitive that calls
   `huggingface_hub.hf_hub_download(...)` for that one file and copies it to a
   local path **inside the product's own runtime area** — not the bot's working
   `trades.db` path. The primitive is **duplicated/adapted within
   `applications/trading_intelligence/`**, never imported from `dashboard/` or
   `scheduler/` (per this product's standing "duplicate the primitive, never
   import the protected package" convention).
3. **Consumer only.** Trading Intelligence **never** calls `upload_file`,
   `upload_folder`, `create_commit`, or any write/delete operation against that
   repo, and never sets or relies on `HF_REPO_ID` as a push target. It is not
   the owner or writer of the dataset; the bot remains the sole
   producer/publisher (`bot/monitor/sync_db.py`).
4. **Fail closed.** If the download fails for any reason (missing token for a
   private repo, network error, 404, malformed file), the primitive yields no
   usable path and the four `legacy_*` adapters continue to return `None`,
   leaving each section on its existing honest-unavailable / illustrative
   fallback. A failed or absent snapshot is never substituted with fabricated
   data.
5. **Read-only open, no WAL sync.** Downstream adapters open the local snapshot
   with `mode=ro` exactly as they do today. No `-wal`/`-shm` handling, no
   `PRAGMA journal_mode`, and no checkpoint are introduced. The snapshot is
   treated as an immutable file for the life of the process/refresh.
6. **Staleness stays visible and honest.** The snapshot is **not** treated as
   real-time authoritative state. Every adapter that surfaces a persisted
   timestamp (`screened_at`, regime `as_of`, etc.) must continue to render it
   verbatim so the user can see how current the data is. No adapter may compare
   the snapshot's contents against "today" and present them as current.
7. **Ephemerality.** The local copy is a cache for the running Space only; it
   carries no guarantee of persistence and may be re-fetched or discarded
   between refreshes/restarts.

Where the download runs (at Space **runtime** inside
`applications/trading_intelligence/`, versus inside
`deploy_trading_intelligence.yml` at deploy time) is **not fixed by this ADR**.
The runtime option requires no ADR-002 exception; the deploy-time option would,
and is deferred to ADR-056. This ADR authorizes the *dependency and the consumer
contract*, not the placement.

## 3. Alternatives Considered

1. **Read-only consumer of the existing published dataset snapshot (selected).**
   Reuses a primitive already proven in two protected code paths; zero new
   infrastructure; consistent with `TRADING_INTELLIGENCE_BOUNDARY.md` §5 ("TI
   owns `trades.db`") — TI reading its own product's data from the channel the
   bot already publishes to.
2. **Import `dashboard.data._sync_db` (or `scheduler.startup_job._sync_db`).**
   Rejected: both modules are ADR-002-protected; importing either couples the
   product to a frozen package and pulls in unrelated dashboard/scheduler code.
3. **Stand up a new Trading-Intelligence-owned dataset repo and a bot→TI
   publish path.** Rejected: makes TI (or a new pipeline) a second writer,
   contradicts "bot remains the sole producer", and is far more than Units 1–3
   need.
4. **Bundle a `trades.db` copy into the deploy artifact at build time as a
   static file.** Rejected: the snapshot would be frozen at each deploy and
   silently rot between deploys, with no visible staleness signal beyond the
   persisted row timestamps; a runtime pull keeps it as fresh as the bot's last
   publish.
5. **Do nothing — leave the SQLite-backed sections permanently unavailable in
   the Space.** Rejected for the same reason as ADR-054 §3.4.
6. **Handle this as an inline "boundary decision (recorded)" docstring, no
   ADR.** Considered, because the `legacy_*` SQLite adapters themselves were
   admitted that way. Rejected: those adapters only assumed a *local* file that
   might or might not be present; this decision *adds a new external repository
   to the product's runtime dependency set*, which is an architectural
   dependency worth a citable record — and it must be reconciled explicitly with
   ADR-035.

## 4. Consequences

**Positive:**
- Units 1–3's four SQLite-backed sections can render real data in the deployed
  Space, using a pull mechanism already battle-tested in `dashboard/` and
  `scheduler/`.
- The bot stays the single writer; no new write path, no second producer, no
  ledger-ownership implication.
- Fail-closed + verbatim-timestamp rules mean a stale or missing snapshot
  degrades honestly, never misleadingly.

**Negative / Limitation:**
- Adds an external dependency (HuggingFace dataset availability) to the product
  runtime; mitigated by the fail-closed contract.
- The snapshot is eventually-consistent with the bot's activity; users see
  "as-of" data, and the UI must keep saying so.
- `TRADING_INTELLIGENCE_BOUNDARY.md` §5–§7 needs a dated addendum recording the
  HuggingFace dataset as a TI runtime input — follow-up, not done here.
- If the deploy-time placement is later chosen, a separate ADR-002 exception
  (ADR-056) is required; this ADR does not grant it.

## 5. Non-Authorization / Scope Boundary

This ADR authorizes **only** §2. It explicitly does **not**:

1. Authorize any write, upload, commit, or delete against any HuggingFace repo.
2. Make Trading Intelligence an owner, writer, or co-publisher of `trades.db` or
   its dataset repo.
3. Authorize importing `dashboard/`, `scheduler/`, `bot/`, `database/`, or
   top-level `ledger/` from any Trading Intelligence module.
4. Authorize any change to `.github/workflows/*.yml` — including staging a
   `trades.db` pull step into `deploy_trading_intelligence.yml` (ADR-056 scope).
5. Authorize creating or setting any GitHub or HuggingFace secret (e.g. an
   `HF_TOKEN` for a private dataset).
6. Authorize reading any hash-chained Trust Ledger event table
   (`candidate_evaluation_events`, `decision_events`, `risk_evaluation_events`,
   `approval_events`, `decision_outcome_events`,
   `constitution_enforcement_events`, `decision_confidence_events`,
   `deployment_manifest_events`) — those remain gated behind ADR-004 / "Q1". The
   four in-scope adapters read only the plain application-state tables
   (`trades`, `screener_log`, capital/regime/position tables).
7. Introduce `-wal`/`-shm` synchronization, WAL-mode `PRAGMA`s, or any write
   connection to the snapshot.
8. Treat the snapshot as real-time or authoritative live state.
9. Select or affect ADR-004 Option A/B/C.
10. Modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
    `sentinel_engine/`, or `config.py`.
11. Amend, reopen, or reinterpret ADR-002, ADR-004, ADR-023, or ADR-035.

## 6. Relationship to Existing ADRs

**ADR-002:** Preserved. The chosen mechanism duplicates a primitive rather than
importing `dashboard/`/`scheduler/`. If a runtime-only placement is used, no
workflow file changes; a deploy-time placement is explicitly deferred to ADR-056.

**ADR-004:** Untouched. This ADR reads plain application-state tables from the
bot's own published `trades.db`; it makes no ledger-backend or ownership choice
and does not read the hash-chained event tables the "Q1" question concerns.

**ADR-023:** Not extended here. Any workflow-file change to realise this
dependency is ADR-056's scope.

**ADR-035:** Directly addressed. ADR-035's duplicate-order race concerns
processes that *trade* on a pulled DB; Trading Intelligence trades nothing and
writes nothing. The residual partial-download concern is handled by the
fail-closed contract (a malformed/incomplete file yields `None`, not a partial
render) and by treating the local copy as immutable for the refresh.

## 7. Evidence / Rationale

- `dashboard/data.py:142-159` — the existing read-only `hf_hub_download`
  `trades.db` dataset pull + `shutil.copy`, TTL-gated, 404-tolerant.
- `scheduler/startup_job.py:59-73` — the same pull primitive, independently.
- `bot/monitor/sync_db.py:56-95` — the bot's `HfApi().upload_file` publish path;
  establishes the bot as the writer.
- `config.py:16-18` — `HF_TOKEN`, `HF_REPO_ID` (empty default), `HF_DB_REPO_ID`
  (`ksri77/ai-trading-bot-db`).
- `applications/trading_intelligence/adapters/legacy_candidate_screening_source.py:20-39`
  — read-only `mode=ro` open; "never imports bot.*/dashboard.*/database.*/
  scheduler.*/ledger.*, never writes"; verbatim `screened_at` staleness rule.
- `applications/trading_intelligence/adapters/legacy_regime_source.py`,
  `legacy_capital_source.py`, `legacy_position_source.py` — same read-only
  pattern.
- `docs/decisions/ADR-035-keepalive-native-schedule-backup.md` — Context
  paragraph on the multi-process HuggingFace `trades.db` pull hazard.
- `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §5 — "Trading Intelligence
  owns: Trading databases (`trades.db` …)".

## 8. ADR-002 Safety Statement

This ADR does not modify `bot/`, `dashboard/`, `scheduler/`, `database/`,
top-level `ledger/`, `sentinel_engine/`, `config.py`, or any
`.github/workflows/*.yml` file. It authorizes no import of any protected
package. It authorizes no write of any kind to any HuggingFace repo, no secret
creation, and no deployment. ADR-002 and ADR-004 remain exactly as in force as
before this ADR.

## 9. Rollback

This ADR authorizes an architectural admission (a read-only external data
source), not a deployment, Trust Ledger, or protected-path change; reversing it
carries no data-level risk:

- Remove/revert the Trading-Intelligence-owned HuggingFace dataset consumption
  primitive introduced under this decision.
- The four SQLite-backed sections return to their existing data-unavailable /
  fallback behavior.
- No bot-owned `trades.db` data — the local working copy or the published
  dataset repository — is modified or deleted by this rollback; Trading
  Intelligence is a read-only consumer holding only an ephemeral copy.
- No Trust Ledger, ADR-004 "Q1", workflow, secret, or ADR-002-protected-set
  change is implied.

## 10. Acceptance Criteria

Accepted only when the architecture owner confirms in writing:
- Ratification of §2 (read-only ephemeral consumer of the existing published
  `trades.db` dataset snapshot; bot remains sole writer; fail-closed; staleness
  stays visible), or explicit rejection with reasoning.
- Whether the download runs at Space runtime or is deferred pending an ADR-056
  deploy-time staging decision.
- That acceptance authorizes no code, workflow, secret, or deployment change by
  itself.

## 11. Status

**Accepted — 2026-08-27.**

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-27
**Accepted By:** Architecture Owner

Acceptance ratifies §2 only, and does not decide the open runtime-vs-deploy-time
placement question in §10. Per the Non-Authorization list (§5), it authorizes no
code, workflow, secret, or deployment change; the bot remains the sole writer of
`trades.db`.
