# ADR-071 — Phase 1A §14 Single-Write-Path Scope Interpretation

**Status:** Accepted
**Date Proposed:** 2026-09-10
**Date Accepted:** 2026-09-10
**Decision Type:** Architecture / Governance — bounded interpretation of an existing recovered requirement. No code, schema, contract, behavior, workflow, database, or index change. No ADR-002 exception. Not an implementation authorization.
**Related ADRs:** ADR-004 (Deferred — ledger-ownership; unamended here), ADR-058 (ratification rule this ADR is landed under), ADR-059 (live governed production decision write path — the authority this interpretation rests on), ADR-067 (causal Sentinel lifecycle boundary — in-memory, non-durable), ADR-069 (B2 recommendation authority — no second persistence model). Context only, not amended: ADR-043 (temporary read-only lineage projection), ADR-045 (governance-service composition), ADR-066 (decision/evidence vocabulary).

Per **ADR-058 D4**, this file is a **proposal** and carries no authority until it is landed under **ADR-058 D2** — tracked on the authoritative default branch, `Status: Accepted`, landed under the applicable write / merge controls. The `Accepted By` line in `## Acceptance`, once filled, is metadata, not the source of authority.

---

## Context

### The recovered §14 wording at issue

Recovered `phase1a_requirements.md` v1.5 **Section 14 ("Acceptance Criteria")**, under "Single write path (verified, not assumed)", requires — measured over the same 30-day window:

- clause (a): "**`decision_log` receives zero new writes after cutover**" (with the direction: "audit the write path directly — grep the codebase for any remaining call sites, don't infer this from the ledger looking populated");
- clause (b): "**exactly one decision-creation path exists end to end (Scanner → Ledger → Paper Execution)**, not **two parallel paths** that happen to agree so far … this criterion **fails if a second write path exists at all**, regardless of whether its output currently matches the ledger's."

§14 grounds this in "`phase0_decisions.md` #7 states `decision_log` is **superseded, not run in parallel**." §14 itself is a recovered document; it has no ratified status of its own (it is not tracked as an Accepted ADR).

### What changed after the original Phase 1A window

The original Phase 1A validation window (2026-07-28 → 2026-08-27) ran with a singular decision path and zero `decision_log` writes after the cutover. After that window, commit `1137dde` (2026-09-08), under **ADR-067 / ADR-069**, wired a pre-gate "causal Sentinel decision" into the live entry path:

- `bot/_main_trust_decisions.py:32` imports `get_decision_service` from `sentinel_engine.composition.decision_lifecycle`.
- `bot/_main_trust_decisions.py:182` calls `get_decision_service().create_decision(Decision(...))` when a BUY candidate is formed.

This raises a scope question against §14's clause (b): does that call constitute "a second decision-creation path" / "a second write path" whose existence would fail the criterion?

### The code facts (read-only inspection at HEAD `092cd15`)

- `sentinel_engine/composition/decision_lifecycle.py` constructs the lifecycle service pair on `_LifecycleLedgerStore` (line 38), whose backing store is an in-memory list: `self._events: List[Event] = []` (line 40), `self._events.append(event)` (line 43). Its module docstring states it is "one temporary in-memory LedgerStore" (line 4), "**Process-local and non-durable**" (line 22), and "**Not the production Sentinel repository architecture; ADR-004 remains deferred**" (line 21).
- `sentinel_engine/services/decision_service.py::DecisionService.create_decision` (line 28) builds an `Event` and a `DecisionProjection` and calls `self._ledger_repository.save_event(event)` (line 49). The service is "**Storage-implementation independent: only depends on the repository abstractions … never on a concrete backend**" (line 4).
- `sentinel_engine/repositories/ledger_repository.py` imports only `typing` and two `sentinel_engine` modules — no `sqlite3`, no `decision_log`, no SQL.
- The only durable `INSERT INTO decision_log` in the repository is in `database/services/decision_service.py` (module-level `create_decision`, line 42; the SQL at line 61). **No file under `bot/` imports `database.services.decision_service`** (verified by grep). The two `create_decision` functions are unrelated implementations that share a name.
- Production verification (read-only, against the Hugging Face-synced `trades.db`) showed the `decision_log` table has **zero rows with `created_at` after the cutover `2026-07-28T20:54:30`** (`scripts/verify_single_write_path.py:38` `CUTOVER_TIMESTAMP`); the latest `decision_log` row predates the cutover.

### The residual ambiguity

Clause (a) is answerable by direct fact (below). The only genuine interpretive question is clause (b)'s phrase "a second write path … at all" applied to an ephemeral in-memory event. Existing ratified ADRs (ADR-059, ADR-067, ADR-069) already establish the operative principle, but none of them cites §14's acceptance wording, and §14 is unratified. `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` ("Resolving future conflicts") directs that such a scope question be settled by "a new ADR under `docs/decisions/` that references both and states which wins and why." This ADR is that record, for this one term.

---

## Decision

### 1. §14 clause (a) — "`decision_log` receives zero new writes after cutover" — factual finding

This clause is satisfied **on its face**. This ADR makes **no interpretation of the term `decision_log`** and does not narrow, broaden, or redefine it.

The finding, stated factually:

- The ADR-067 / ADR-069 causal Sentinel facade invoked from `bot/_main_trust_decisions.py:182` uses `sentinel_engine.composition.decision_lifecycle`.
- That lifecycle's `LedgerStore` is a process-local, non-durable, **in-memory** list of events (`sentinel_engine/composition/decision_lifecycle.py:38–46`).
- It does **not** call `database.services.decision_service`; no file under `bot/` imports that module.
- It performs **no `INSERT` or `UPDATE` against the `decision_log` table**, and **no SQLite persistence of any kind**.
- Production verification showed **zero `decision_log` rows after the `2026-07-28T20:54:30` cutover**.

Therefore the causal facade adds no row to `decision_log`, and §14's clause (a) holds as written.

### 2. §14 clause (b) — "exactly one decision-creation path" / "a second write path" — bounded scope interpretation

For the purposes of Phase 1A §14, **"exactly one decision-creation path end to end" and "a second write path" are read as referring to a *durable production decision-persistence path*** — a path that records a production decision into a persistent store that survives process termination and could stand as, or diverge from, a system of record.

A process-local, non-durable, in-memory causal event — as produced by `DecisionService.create_decision` on the `sentinel_engine.composition.decision_lifecycle` in-memory store — **is not such a second write path**, because it:

- creates no durable decision record;
- persists no competing decision identity;
- constitutes no second system of record;
- cannot survive process termination (the backing `list` is discarded when the OS process exits);
- holds no durable state that could be reconciled against, or diverge from, `data/trust_ledger.db::decision_events`.

This ADR does **not** claim that an in-memory object is equivalent to, a substitute for, or a component of the production decision path. It claims the narrower point that an ephemeral in-memory event does not meet §14 clause (b)'s notion of a "second write path."

### 3. Authority basis

This interpretation rests on already-ratified ADRs and adds no principle of its own:

- **ADR-059 §D1**: "There is one live, governed production decision write path — Scanner → Ledger → Paper Execution, as verified by `scripts/verify_single_write_path.py`. That path persists every production decision it creates as exactly one row in `data/trust_ledger.db::decision_events`." (See also ADR-059 line 15, tying this to `phase1a_requirements.md` Section 14.)
- **ADR-059 Scope of This Record**: "'The live governed production write path' means the single path `scripts/verify_single_write_path.py` verifies … **whatever set of files implements it at a given time** — not to a fixed file list."
- **ADR-059 §D3**: the identity authority does not "retire, delete, migrate, deprecate, **re-enable**, or otherwise modify the legacy `decision_log` path."
- **ADR-059 §D4**: "`sentinel_engine.Decision.decision_id` is **not** the live governed production write path's decision identity: it is a contract-level string with no production producer." (ADR-067's implementation commit later gave that identifier a production *producer* via `bot/_main_trust_decisions.py:182`, so D4's literal "no production producer" clause is now factually overtaken; D4's *conclusion* — that this identifier is not the live governed production write path's identity — is unaffected, because that producer writes only to the in-memory, non-persisting lifecycle store.)
- **ADR-067 §3.C** and related text: the causal lifecycle uses one process-scoped, "non-durable, process-local" pair (§3.C) — "temporary, in-memory, process-local" (line 610); its composition module docstring calls it "one temporary in-memory LedgerStore" and states "Not the production Sentinel repository architecture; ADR-004 remains deferred" (`sentinel_engine/composition/decision_lifecycle.py:4, 21`). ADR-067 §3.B and its checklist item 18 require that "`scripts/verify_single_write_path.py` must continue to pass unchanged" / "passes unchanged" (lines 152, 402).
- **ADR-069 §3.4**: the causal recommendation reuses "the **same** ADR-067 `Decision` / `decision_id` / `DecisionProjection`. No `Recommendation` class, no second `Decision`, no second lifecycle, no second persistence model." (line 145); "**no** second lifecycle, **no** duplicate persistence model, and **no** new" identity (line 543); "`scripts/verify_single_write_path.py` must pass before and after" / "passes unchanged" (lines 743, 1031).

### 4. Operative verification mechanism (unchanged)

`scripts/verify_single_write_path.py` remains the operative verification for §14's single-write-path criterion. Specifically:

- **check 1** (`scripts/verify_single_write_path.py:186`): no `decision_log` `INSERT` / `UPDATE` SQL literal is reachable from the live trading cycle (`bot/main.py`, `bot/_main_*.py`).
- **check 5** (`scripts/verify_single_write_path.py:260`, `:276`): the `decision_log` table has zero rows written after the `2026-07-28T20:54:30` cutover, checked directly against the accumulated database.

This ADR does **not** assert that §14's automated / persisted / accumulated-30-day-database verification has already been performed, and does **not** assert that the accumulated-30-day-database verification requirement has been satisfied. The script exists and is the correct instrument; running it on a schedule with persisted, dated output against the accumulated production database is a separate, still-outstanding acceptance-review task.

---

## Scope of This Record

- This ADR records exactly one scope interpretation — the meaning of "second write path" / "one decision-creation path" in §14 clause (b) — and the factual finding for §14 clause (a). It does not add to, narrow, generalize, or infer beyond that.
- The interpretation applies to Phase 1A §14 acceptance evaluation. It does not restate or alter ADR-059/067/069; it relies on them.
- Nothing here depends on Phase 1A being closed, or on any ADR-004 criterion being met.

---

## Preserved §14 Requirements — Status Unchanged

This ADR narrows nothing else in §14. Every other §14 requirement stands exactly as recovered, and the previously established satisfied / unmet / not-provable status of each is unchanged by this record:

- 30 consecutive days of evidence collection;
- 100% data integrity, including per-decision: candidate-evaluation linkage; deployment-manifest linkage; model outputs present; risk evaluation present; `data_completeness` recorded;
- provenance (Decision → Deployment Manifest → Models → Training Runs → Strategy → Risk Rules, resolvable in one query);
- zero broken hash chains;
- zero orphan BUY/SELL decisions;
- zero duplicate decisions (per §12);
- zero failed writes;
- verification that is automated;
- verification evidence that is persisted;
- verification that is rerunnable against the accumulated 30-day database;
- a formal review / sign-off of the results.

The prior review's overall result for Phase 1A §14 (PARTIALLY SATISFIED, with the 30-consecutive-day and single-write-path-verification items among the open blockers) is not changed by this ADR. This ADR removes only a scope ambiguity about clause (b); it does not close the criterion.

---

## Explicit Non-Goals / Non-Claims

This ADR does **not**:

1. close Phase 1A §14, or declare the Phase 1A validation window successful;
2. close, satisfy, or make any finding on ADR-004 Criterion 1 ("Phase 1A's 30-day live-validation window has completed, and its results … have been reviewed");
3. select, prefer, rank, constrain, or comment on ADR-004 Option A, Option B, or Option C;
4. select or establish a permanent ledger architecture or a durable Sentinel ledger backend;
5. amend, supersede, or reinterpret ADR-004 — **ADR-004 remains `Status: Deferred`, unamended**;
6. amend, supersede, or reinterpret ADR-058, ADR-059, ADR-067, ADR-069, or ADR-002;
7. modify, narrow, or amend recovered `phase1a_requirements.md` §14 (or §6, §12, §4.3);
8. redefine, narrow, or broaden the term `decision_log`;
9. change any `bot/` behavior, decision-creation flow, or execution path;
10. authorize any implementation, code change, test change, schema change, contract change, workflow change, database change, or index/authority-document change;
11. authorize durable Sentinel ledger persistence, or authorize the ADR-067/069 in-memory lifecycle to become a production persistence path;
12. authorize, require, or constitute an ADR-002 exception;
13. resolve, reinterpret, or accommodate the separate FinBERT provenance question, or the separate failed-write-evidence question — both remain independent Phase 1A acceptance-review items and §14 is not altered for either;
14. introduce any new governance rule.

---

## Evidence

Repository state at HEAD `092cd156cd3c351213b72046f15424ed74eff528` (read-only inspection):

- `docs/decisions/ADR-071-...` (this file) — recovered `phase1a_requirements.md` v1.5 §14 clauses quoted in Context are from the recovery record established earlier in this repository's working history; §14 is not tracked as an Accepted ADR.
- `bot/_main_trust_decisions.py:32` — `from sentinel_engine.composition.decision_lifecycle import get_decision_service`.
- `bot/_main_trust_decisions.py:182` — `get_decision_service().create_decision(Decision(...))` (pre-gate causal decision; the module header, lines 6–9, describes Trust Ledger writes as "Best-effort … an audit system, not a trading gate").
- `sentinel_engine/composition/decision_lifecycle.py:4` ("one temporary in-memory LedgerStore"), `:21` ("Not the production Sentinel repository architecture; ADR-004 remains deferred"), `:22` ("Process-local and non-durable"), `:38` (`class _LifecycleLedgerStore(LedgerStore)`), `:40` (`self._events: List[Event] = []`), `:43` (`self._events.append(event)`), `:67` (`def get_decision_service`).
- `sentinel_engine/services/decision_service.py:4` ("Storage-implementation independent"), `:19` (`class DecisionService`), `:28` (`def create_decision`), `:49` (`self._ledger_repository.save_event(event)`).
- `sentinel_engine/repositories/ledger_repository.py` — imports only `typing`, `sentinel_engine.events.event`, `sentinel_engine.ledger.ledger`; no `sqlite3` / SQL / `decision_log`.
- `database/services/decision_service.py:42` (`def create_decision`), `:61` (`INSERT INTO decision_log`) — the only durable `decision_log` writer; no `bot/` import of this module (grep, zero hits).
- `scripts/verify_single_write_path.py:38` (`CUTOVER_TIMESTAMP = "2026-07-28T20:54:30-05:00"`), `:186` (check 1 — "decision_log has no write call sites in the live trading cycle"), `:260` / `:276` (check 5 — "decision_log has zero rows written after cutover").
- Production `decision_log` verification: Hugging Face-synced `trades.db` (dataset `ksri77/ai-trading-bot-db`, read `mode=ro`) — `decision_log` has 18 rows, latest `created_at` `2026-07-17T18:21:11`, zero rows after the cutover.
- `docs/decisions/ADR-059-production-decision-identity-live-governed-write-path.md:15`, `:33` (§D1), `:41` (§D3), `:55` (§D4), `:62` (Scope of This Record — "the single path `scripts/verify_single_write_path.py` verifies … whatever set of files implements it").
- `docs/decisions/ADR-067-sentinel-causal-decision-lifecycle-boundary.md` §3.C, `:152`, `:187`, `:402`, `:610` (process-scoped, in-memory, "non-durable, process-local" causal-lifecycle pair; "verify_single_write_path.py must continue to pass unchanged" / "passes unchanged").
- `docs/decisions/ADR-069-sentinel-b2-recommendation-authority.md:145`, `:543`, `:743`, `:1031` ("no second lifecycle, no second persistence model … no duplicate persistence model"; "verify_single_write_path.py must pass before and after" / "passes unchanged").
- `docs/decisions/ADR-058-architecture-authority-and-adr-ratification-rule.md` — §Decision D2 (when an ADR is authoritative), D4 (proposing is separate from ratifying).
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` — "Resolving future conflicts" ("Write a new ADR under `docs/decisions/` that references both and states which wins and why"); Hierarchy §2 (ADRs are "explicit, dated resolutions of a specific conflict").
- `docs/decisions/ADR-002-bot-runtime-protection.md` — §Decision: the protection is against "moves … import changes … refactors … file changes" to `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, top-level `ledger/`. This ADR changes none of those; it adds one file under `docs/decisions/`.

---

## Decision Character

This is a **bounded interpretation of an existing recovered requirement**. It:

- introduces **no new governance rule**;
- authorizes **no implementation** of any kind;
- resolves **only** the scope ambiguity around §14 clause (b) — the meaning of "a second write path" / "one decision-creation path" — and states the factual finding for §14 clause (a);
- rests entirely on already-ratified architectural authority (ADR-059 §D1/§D3/§D4 and its Scope statement; ADR-067; ADR-069).

Per ADR-058 D4, this document is a **proposal** and confers no authority until it is landed per ADR-058 D2.

---

## Consequences

**Positive:**

- Records, in the repository's ratified-decision layer, the mapping between §14 clause (b)'s wording and the already-ratified ADR-059/067/069 principle — so a future Phase 1A §14 single-write-path review is not blocked by a false ambiguity about the in-memory causal facade.
- Keeps the factual clause (a) finding (no `decision_log` write) on record without reinterpreting `decision_log`.
- Leaves every other §14 requirement, and Phase 1A's overall open status, untouched.

**Limitations / what remains open:**

- Does not perform, schedule, or evidence the §14 automated / persisted / accumulated-30-day-database verification — that task is still outstanding.
- Does not address the 30-consecutive-day gap, FinBERT provenance, failed-write evidence, or the formal review / sign-off — each remains a separate acceptance-review item.
- §14 itself remains a recovered, unratified document; this ADR interprets one of its terms but does not confer status on §14 as a whole.
- The interpretation is scoped to the current in-memory, non-durable ADR-067/069 lifecycle. Any future change that makes a second decision path *durable* is outside this record and would require its own governance treatment.

---

## Acceptance

*(Per ADR-058 D2, authority follows from this document being tracked on the authoritative default branch `main` with `Status: Accepted`, landed under the repository's applicable write / merge controls — the direct-to-`main` flow, in the commit named in the Status Log below. Per ADR-058 D2 the `Accepted By` line is metadata, not the source of authority. Completing this section does not alter the substantive interpretation in §Decision.)*

**Status:** Accepted
**Date Accepted:** 2026-09-10
**Accepted By:** Architecture Owner (explicit act — accepted and landed)

---

## Status Log

- **2026-09-10 — Proposed.** Drafted as a read-only bounded interpretation of recovered `phase1a_requirements.md` §14 clause (b), with a factual finding for clause (a). Not landed; not accepted; no landing commit. Authority contingent on ADR-058 D2.
- **2026-09-10 — Accepted + Landed.** Following an independent architectural/governance acceptance review (result: READY TO ACCEPT), the Architecture Owner explicitly accepted ADR-071 in the form drafted, with three non-substantive review-identified corrections applied (ADR-067 evidence line reference tightened to §3.C; emphasis in the ADR-069 §3.4 quotation matched to source; ADR-059 §D4 parenthetical clarified re the post-window producer). It was landed on the default branch `main` in the same commit, `docs: accept and land ADR-071 Phase 1A §14 single-write-path scope interpretation`. `Status` now reads `Accepted`. This acceptance is scoped exactly to the §Decision interpretation: §14 clause (a) is satisfied as a factual `decision_log`-table finding (no term redefined); §14 clause (b)'s "second write path" / "one decision-creation path" is read as a durable production decision-persistence path, from which the process-local, non-durable, in-memory ADR-067/069 causal facade is excluded. All other §14 requirements retain their prior status; ADR-004 remains `Deferred`, unamended; no implementation, schema, database, `bot/`, contract, workflow, or ADR-002 exception is authorized.
