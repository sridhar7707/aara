# ADR-034: FinBERT Evidence Headline Provenance (Narrow ADR-002 Exception)

**Status:** Proposed
**Date:** 2026-08-16
**Decision Type:** Architecture — Narrow ADR-002 Exception
**Related ADRs:** ADR-002 (protected path this ADR would except), ADR-012 (governs the MODEL_OUTPUT Evidence shape this ADR adds a key inside, not modifies), ADR-026 (structural precedent for this ADR's format and narrow-exception discipline)

---

## 1. Context

A user reviewing the Trading Intelligence Decision Center's Audit Trail
payload disclosure (added this session) asked why a `NEWS_SENTIMENT`
evidence card shows `evidence_type`/`source`/a score, but never the actual
news headline(s) that produced it. A read-only trace of the real
(non-demo) evidence-write path found that this isn't a UI gap — the
headline text never reaches `Evidence.data` anywhere in the pipeline
today, for any decision, real or seeded.

Two things the demo seed gets wrong, discovered by this trace:

1. `applications/trading_intelligence/bootstrap.py`'s seed data invents
   `evidence_type="NEWS_SENTIMENT"` / `source="newsapi"` /
   `data={"score": <float>}`. The real pipeline never writes that shape.
2. The real pipeline (`bot/_main_trust_decisions.py` →
   `sentinel_engine/adapters/evidence_adapter.py`) always writes
   `evidence_type="MODEL_OUTPUT"`, one record per model
   (`xgboost`/`lstm`/`finbert`), each `data={"signal": ..., "confidence":
   ..., "metadata": {...}}`. The sentiment record is `source="finbert"`,
   `metadata={"raw_score": <-1..1 float>}` — a score, never a headline.

Tracing where headline text actually goes, end to end:

- `bot/strategy/sentiment.py:get_news_headlines(ticker)` (lines 103-152)
  fetches NewsAPI `/v2/everything`, keeps only `article["title"]` (line
  146), discards `url`/`description`/`publishedAt`. It caches the title
  list in two layers: an in-process dict `_NEWS_DAY_CACHE` (line 19,
  keyed `"TICKER:YYYY-MM-DD"`) and a SQLite table `news_cache` (schema at
  `bot/_main_db.py:124-126`: `symbol, fetch_date, headlines_json,
  cached_at`), written via `_news_db_set()` (lines 44-58).
- `scripts/prefetch_sentiment.py` runs once daily, calls
  `collect_headlines()`/`batch_sentiment_scores()`
  (`bot/strategy/sentiment.py:195-238`) to precompute each active
  symbol's FinBERT score, and writes only `{date, saved_at, scores:
  {symbol: float}}` to `data/sentiment_today.json` — headlines are
  fetched (and cached, per the point above) but never persisted past that
  run.
- `bot/_main_market.py:_compute_sentiments()` (lines 284-306) blends that
  precomputed FinBERT score with a real-time WallStreetBets
  mention-weighted score into one final float per symbol
  (`ctx.sentiments[symbol]`) — a second, independent point where
  per-source attribution is discarded.
- `bot/_main_trust_decisions.py` calls `build_model_outputs(...)` at two
  sites — `EntryDecisionRecorder.__init__` (line 118) and
  `record_exit_decision_safe` (line 219) — passing only the already-blended
  float. `build_model_outputs()`
  (`bot/strategy/model_output_adapter.py:35-69`) puts it straight into
  `finbert.metadata.raw_score` (line 67); no headline ever reaches this
  function.
- `sentinel_engine/adapters/evidence_adapter.py:to_evidence_records()`
  (governed by ADR-012) does `data=dict(model_outputs[model])` verbatim
  (line 48) — a faithful shallow copy of whatever `build_model_outputs()`
  produced. It adds and drops nothing; the gap is entirely upstream of it.

Reconstructing full sentiment provenance (which headline, and how much
WSB mentions versus FinBERT contributed to the final blended score) would
require touching `scripts/prefetch_sentiment.py`,
`bot/_main_market.py:_compute_sentiments()`/`_wsb()`, and
`data/sentiment_today.json`'s schema, in addition to the write path below
— a materially larger, higher-risk, multi-subsystem change than ADR-026's
precedent. This ADR does not propose that. It proposes the smallest
change that answers the user's actual question — "what headlines were
available when this symbol's sentiment was scored today" — using only
data that is *already fetched and cached today*, with zero new external
calls.

`bot/strategy/sentiment.py`, `bot/strategy/model_output_adapter.py`, and
`bot/_main_trust_decisions.py` are protected under
[ADR-002](ADR-002-bot-runtime-protection.md) (`bot/` — all submodules).
Per ADR-002 §"Lifting This Protection," any change to them requires its
own, separately governed ADR naming the specific modules, an isolated
branch/worktree, a full regression pass, a stated rollback plan, and
verification of both known trading-trigger paths. This ADR is written to
meet that checklist for exactly the three corrections in §3 below, and no
more.

## 2. Evidence

**Caching already makes this free in the common case.**
`get_news_headlines()`'s first two branches (lines 106-119) are pure
cache reads (L1 dict, then L2 SQLite) with no network call; only a cache
miss falls through to the live NewsAPI request (line 121 onward). Because
`prefetch_sentiment.py` runs once per trading day for the active
universe and populates both cache layers for every symbol it scores,
`_NEWS_DAY_CACHE`/`news_cache` already holds that day's headlines for any
symbol whose sentiment came from `premarket_sentiment`
(`_compute_sentiments()`, line 291) — the common path, per its own log
line "Using pre-market FinBERT sentiment — skipping in-cycle BERT pass".

**A naive fix would introduce a real regression.** Calling
`get_news_headlines(symbol)` directly at decision-record time, for a
symbol whose sentiment was *not* precomputed today (the `else` branch at
`bot/_main_market.py:293-294`, `finbert = {sym: 0.0 for sym in
active_symbols}`), would fall through to a live NewsAPI call inside
`record_decision_safe`'s best-effort try/except (`bot/
_main_trust_decisions.py:85-89`) — consuming NewsAPI's tracked
100-request/day quota (see project memory on the NewsAPI L2 cache) on
every such decision write, silently, with no existing test coverage to
catch it. `collect_headlines()` is worse still: it also calls
`get_sec_headlines()`, which makes a live, throttled (`time.sleep(0.13)`,
line 184) SEC EDGAR call on *every* invocation — it is never cached. Using
either function as-is would add unbounded new external I/O to the live
decision-write path.

**No existing test asserts the current `metadata` shape exactly.**
`tests/phase1a/test_decision_capture.py:79` asserts
`set(out.keys()) == {"xgboost", "lstm", "finbert"}` (top-level keys only);
line 84 asserts `out["finbert"]["signal"]`. No test in
`tests/phase1a/test_trust_decision_evidence_integration.py` or elsewhere
asserts the exact contents of `finbert["metadata"]`. Adding a key to it
is additive and does not conflict with any existing assertion (verified
by grep, not assumed).

**Precedent for exactly this pattern already exists in the same
function.** `build_model_outputs()` already accepts an optional
`xgb_drivers` parameter and threads it into `xgboost.metadata.shap_drivers`
(`bot/strategy/model_output_adapter.py:39,46-49,54`) — an
optional-parameter-into-metadata shape this ADR replicates for `finbert`,
not a new convention.

**ADR-012 does not constrain `metadata`'s internal shape.** ADR-012 §
"Decision" item 3 requires only that `metadata` "must be present and must
be a dict" — it places no constraint on its keys, and its own
"Relationship to EVIDENCE_POLICY_DECISIONS.md" section confirms the
model-output producer's metadata shape is `bot/`'s own convention, not
something ADR-012 governs. Adding a `headlines` key inside
`finbert.metadata` therefore modifies no Sentinel Engine contract and
requires no change to `evidence_adapter.py` itself (confirmed: it already
does a generic `dict(model_outputs[model])` shallow copy, line 48).

## 3. Decision

Authorize exactly three corrections, all confined to `bot/`:

### 3.1 Fix 1 — cache-only headline read, `bot/strategy/sentiment.py`

- **New function**, added after `get_news_headlines()` (after line 152):
  `get_cached_headlines(ticker: str) -> list[str]`.
- **Behavior:** replicate exactly the L1/L2 cache-read logic already in
  `get_news_headlines()` lines 106-119 (check `_NEWS_DAY_CACHE`, then
  `_news_db_get()`) and return `[]` immediately on a miss in either layer
  — **no fallthrough to the NewsAPI request block (lines 121-152) under
  any circumstance.** This is the one piece of new logic this ADR
  introduces; everything else is wiring.
- **Risk:** Low. No new network call, no new external dependency, no
  change to any existing function's behavior — `get_news_headlines()`
  itself is untouched.
- **Existing consumer impact:** `.github/workflows/trade.yml:208` runs
  `scripts/prefetch_sentiment.py`, which calls `collect_headlines()` and
  `batch_sentiment_scores()` — both defined in this same file
  (`bot/strategy/sentiment.py`). This ADR adds only the new
  `get_cached_headlines()` function; it does not modify
  `collect_headlines()`, `batch_sentiment_scores()`,
  `get_news_headlines()`, or `get_sec_headlines()` in any way, so
  `prefetch_sentiment.py`'s existing behavior is unaffected. No change is
  authorized to `scripts/prefetch_sentiment.py` itself.

### 3.2 Fix 2 — thread headlines through `build_model_outputs()`

- **File/lines:** `bot/strategy/model_output_adapter.py:35-69`.
- **Current:** `build_model_outputs()` has no headline parameter;
  `finbert.metadata` is exactly `{"raw_score": float(sentiment_score)}`
  (line 67).
- **Corrected:** add `sentiment_headlines: list[str] | None = None` to
  the signature (same optional-parameter shape as `xgb_drivers`, line
  39), and set `finbert.metadata` to `{"raw_score":
  float(sentiment_score), "headlines": list(sentiment_headlines or [])}`.
- **Risk:** Low. Additive keyword-only-by-convention parameter, default
  preserves today's exact output for any caller that doesn't pass it
  (confirmed: `tests/phase1a/test_decision_capture.py`'s existing calls
  at lines 66/77/91 omit it and would see `headlines: []`, not a
  behavior change to `signal`/`confidence`/`raw_score`).

### 3.3 Fix 3 — pass cached headlines at both evidence-write call sites

- **File/lines:** `bot/_main_trust_decisions.py`.
  - Add `from bot.strategy.sentiment import get_cached_headlines` to the
    import block (after line 26).
  - `EntryDecisionRecorder.__init__` (line 118-121): add
    `sentiment_headlines=get_cached_headlines(self.symbol)` to the
    `build_model_outputs(...)` call. `self.symbol` is already set at
    line 114, before this call.
  - `record_exit_decision_safe` (line 219): add
    `sentiment_headlines=get_cached_headlines(symbol)` to the
    `build_model_outputs(...)` call. `symbol` is already a direct
    parameter of this function (line 206).
- **Risk:** Low. `get_cached_headlines()` (Fix 1) never raises or blocks
  on I/O beyond a local SQLite read already used elsewhere in this same
  file's call graph indirectly (via the existing `news_cache` table), and
  both call sites already execute inside `record_decision_safe`'s
  best-effort `try/except` (lines 66-93) — a failure here degrades to no
  headlines recorded, not a write failure.
- **Interaction with `record_executed()`:**
  `EntryDecisionRecorder.record_executed()` (lines 146-189) may rebuild
  `model_outputs["xgboost"]["metadata"]` when its caller supplies
  `xgb_drivers` (lines 163-168), but never rebuilds or touches
  `model_outputs["finbert"]`. `finbert.metadata.headlines`, set once at
  `__init__` time by Fix 3's call-site change, therefore survives into
  `record_executed()`'s write unchanged. No additional change to
  `record_executed()` is needed or authorized by this ADR.

### 3.4 Semantic scope of `headlines`

`finbert.metadata.headlines` is qualitative textual context that was
available to FinBERT when it produced `raw_score` for that symbol on
that day — nothing more. It must not be represented, in this ADR or in
any later consumer of this field, as the complete rationale, proof,
causal explanation, or deterministic basis of the investment decision.
The decision's actual, governed basis remains `final_confidence`
(`ensemble_confidence()`'s combined weighted score) and the gate trace
already recorded elsewhere in `decision_events` — `headlines` is
retrospective supporting context for a score that already existed, not a
new input to, or justification of, the decision itself.

## 4. Explicit Non-Authorization

This ADR, if accepted, authorizes **only** the three corrections in §3,
across the three named files. It does not authorize:

- Any read-path/UI change. `sentinel_engine/queries/decision_query.py`'s
  `EvidenceSummary` (which does not carry `data` today) and the Trading
  Intelligence Decision Center's Evidence rendering remain untouched —
  surfacing the new `headlines` metadata in the UI is separate,
  unauthorized future work, requiring its own scoping (see the
  Evidence-vs-UI classification `[C]` finding from this session's earlier
  read-only Decision Detail audit).
- Capturing SEC EDGAR headlines (`get_sec_headlines()`) — deliberately
  excluded because, unlike NewsAPI titles, they are never cached and
  every call is a live, throttled external request; adding them to the
  decision-write path is a materially different risk profile this ADR
  does not take on.
- Any change to `_compute_sentiments()`, `_wsb()`, or
  `scripts/prefetch_sentiment.py` — the FinBERT/WSB blend and its
  discarding of per-source attribution is unchanged; this ADR surfaces
  "headlines available that day," not "headlines that produced the final
  blended score."
- Correcting `applications/trading_intelligence/bootstrap.py`'s demo seed
  to match the real `MODEL_OUTPUT`/`finbert` shape — a separate, smaller,
  non-`bot/` fix this ADR does not bundle in.
- Any strategy/signal logic change (entry/exit gate thresholds, ensemble
  weighting).
- Any execution-path, feed-selection, or `EXECUTION_BACKEND` change.
- Any dependency/`requirements.txt` version change.
- Any persistence-schema or ledger-backend change — `news_cache`'s
  existing schema (`bot/_main_db.py:124-126`) is read, not altered.
- Any change to `dashboard/`, `database/`, `scheduler/`, top-level
  `ledger/`, or `.github/workflows/*.yml`.
- Any change to `sentinel_engine/adapters/evidence_adapter.py` or any
  other Sentinel Engine contract — confirmed unnecessary in §2.
- Any change to ADR-002, ADR-012, or ADR-026.

This is a narrow, additive exception — it does not reopen `bot/`
generally and lapses in scope the moment these three named corrections
are implemented and verified.

## 5. ADR-002 Compliance Requirements

Per `ADR-002` §"Lifting This Protection," before implementation begins:

1. **Named modules:** `bot/strategy/sentiment.py` (new function only, no
   existing function modified), `bot/strategy/model_output_adapter.py`
   (lines 35-69), `bot/_main_trust_decisions.py` (import block + lines
   118-121 + line 219). No other file.
2. **Isolated branch/worktree**, not directly on `main`.
3. No workflow YAML references any of these three files by name beyond
   the existing, unmodified entry points (`trade.yml` →
   `bot/main.py`); no workflow file requires updating.
4. **Full regression pass** before and after (see §6).
5. **Rollback plan stated before the change starts** (see §8).
6. **Both known trading-trigger paths verified** — the CLI path
   (`trade.yml` → `python bot/main.py --mode paper --loop`) and the
   `scheduler`-mediated HTTP path (`watchdog.yml` ping →
   `dashboard/http_endpoints.py` `GET /run/cron` →
   `scheduler.dispatcher.main()` → `scheduler/trading_job.py` →
   `bot.main.run()`) — per ADR-002's own two-entry-point finding, restated
   in full, not shortened.

## 6. Tests Required

- New unit test(s) for `get_cached_headlines()`: returns the L1-cached
  list when present; returns the L2 (SQLite) cached list when L1 is
  empty; returns `[]` on a full cache miss **without** calling
  `requests.get` (assert the NewsAPI request function/mock is never
  invoked — this is the one behavior this ADR must not regress).
- New unit test(s) for `build_model_outputs()`: `sentiment_headlines`
  omitted → `finbert["metadata"]["headlines"] == []` (matches today's
  behavior exactly, no regression to existing callers); provided →
  threaded through unchanged.
- New unit test(s) for both `bot/_main_trust_decisions.py` call sites:
  `get_cached_headlines()` is called with the correct symbol and its
  result reaches `model_outputs["finbert"]["metadata"]["headlines"]`.
- Full existing suite re-run, at minimum:
  `tests/test_sentiment.py`, `tests/phase1a/test_decision_capture.py`,
  `tests/phase1a/test_trust_decision_evidence_integration.py`, and the
  full `pytest tests/` baseline — zero regressions required, matching
  ADR-026's own validation precedent.
- `sentinel_engine/tests/` and `applications/trading_intelligence/`
  suites re-run as a sanity check even though neither package is touched
  — confirming ADR-012's "no Sentinel Engine contract modified"
  guarantee holds in practice, not just by inspection.

## 7. Verification

- **CLI path:** a local or CI dry run of `python bot/main.py --mode
  paper --loop` confirming `record_decision_safe()` still succeeds for
  at least one symbol, and that `Evidence.data["metadata"]["headlines"]`
  is populated for a symbol whose sentiment came from
  `premarket_sentiment`, and is an empty list (not an error) for one
  that didn't.
- **Watchdog/HF entry path:** confirmation that `watchdog.yml`'s ping,
  through the full chain — `dashboard/http_endpoints.py` `GET /run/cron`
  → `scheduler.dispatcher.main()` → `scheduler/trading_job.py` →
  `bot.main.run()` — exercises the same corrected code path with the same
  result. None of these four intermediate files are modified by this
  ADR; they are traced only to confirm the corrected code in
  `bot/_main_trust_decisions.py` actually executes on this path, not
  only on the CLI path.
- **NewsAPI quota:** confirm via logs that no new NewsAPI request is
  made as a result of this change — `get_cached_headlines()` must show
  zero additional entries in NewsAPI request logs/quota counters across
  a full cycle, cache-hit or cache-miss.
- Both trading-trigger-path verifications must be performed; per
  ADR-002's own stated finding, verifying only one and assuming the
  other is unaffected is exactly the gap ADR-002 exists to prevent.

## 8. Rollback Plan

All three fixes are additive (new function, new optional parameter with
a default that reproduces today's exact output, new keyword argument at
two call sites) and non-schema, non-persistent. Rollback is a plain `git
revert` of the implementing commit(s). No database schema, ledger
record, or external state is written or altered by any of the three
fixes — `news_cache` is read, never written differently — so no
data-level rollback step is required beyond reverting the code.

## 9. Consequences

**Positive:**
- Closes a real, evidenced gap: no NEWS_SENTIMENT/MODEL_OUTPUT Evidence
  record has ever carried the headline text behind its score, for any
  decision.
- Zero new external API calls or added latency in the common case
  (cache hit), and a bounded, explicit `[]` fallback (not a live call)
  in the uncommon case (cache miss) — the NewsAPI quota risk this ADR
  identified is designed out, not merely accepted.
- Matches an existing, precedented pattern (`xgb_drivers` →
  `metadata.shap_drivers`) rather than inventing a new one.
- Covered by new, previously-nonexistent tests for both the cache-only
  read guarantee and the threading.

**Negative:**
- Does not solve full sentiment provenance — WSB mention text and the
  FinBERT/WSB blend ratio remain unrecoverable per decision, and this
  ADR does not attempt that (see §1, "materially larger... change").
- Does not make this visible anywhere yet — a human still cannot see
  the headlines in the Decision Center until a separate, future
  read-path change is authorized (§4).
- Does not fix the demo seed's mismatched `NEWS_SENTIMENT`/`newsapi`
  shape (§1, point 1) — a real decision seen through the seeded demo
  will still not reflect what this ADR changes about the live pipeline.

## 10. Status

**Proposed.** Awaiting explicit acceptance. If accepted, the three
corrections named in §3 are authorized, strictly bounded by §4's
Explicit Non-Authorization list. Acceptance authorizes the exception
itself; it does not waive §5's ADR-002 compliance requirements (isolated
branch/worktree, full regression pass, stated rollback plan, both
trading-trigger paths verified) or §6's required tests — those remain
preconditions to be satisfied during implementation, not retroactively
satisfied by acceptance.
