# ADR-061 — Generalized Integration Health Contract (Platform-Level, Advisory)

**Status:** Accepted
**Date Proposed:** 2026-08-31
**Decision Type:** Architecture / Governance — Cross-Cutting Contract Definition and Ownership Assignment
**Related ADRs:** ADR-002 (bot/dashboard/scheduler/workflows freeze — **not** excepted by this ADR), ADR-010 (FRED/macro failure-state semantics — the scoped precedent this ADR generalizes; ADR-010 §Non-Goals 6 explicitly deferred "a universal external-data failure policy" to a separate decision — this is that decision, for the contract layer only), ADR-044 (tracked-governance principle — governs where this contract must live to be binding), ADR-047 / ADR-048 / ADR-049 / ADR-050 / ADR-051 (Constitution advisory-vs-enforcing boundary — this ADR stays entirely on the advisory side of that line), ADR-054 (Alpaca paper read-only provider — its collapsed-`None` failure behavior is a motivating example; **not reopened**), ADR-055 (HuggingFace `trades.db` read-only consumer — same; **not reopened**), ADR-056 / ADR-060 (Alpaca/HF credential provisioning — cited only for the credential-hygiene carry-over in §Decision 7; **not reopened or modified**), ADR-058 (D2/D4 ratification model this ADR follows), ADR-015 (precedent: a governance decision that fixes a contract and a bounded allowed scope while deferring all downstream work)

---

## 1. Context

A read-only architecture assessment (this working session) examined how every external
integration/provider in this repository reports health and failure, and whether an existing
authoritative source already owns a generalized contract for it. Its findings were
independently re-verified against the repository before this ADR was drafted.

### 1.1 There is no unified contract today

Three disconnected, partial mechanisms exist. None is a shared, consumable contract:

- **ADR-010 halt-reason metadata** — `bot/db/macro_cache.py:24-27` defines
  `REASON_NONE / REASON_VIX_THRESHOLD / REASON_DATA_UNAVAILABLE` and persists it separately
  from the cached macro values (ADR-010 Amendment 1). It is **FRED-specific**, a 3-value
  `int`, and does not distinguish an authentication failure from a connectivity failure —
  every fetch failure collapses to `REASON_DATA_UNAVAILABLE`.
- **`data_quality_events`** — `bot/trust_ledger/data_quality.py:15` defines
  `_VALID_STATUSES = {"HEALTHY", "DEGRADED", "DOWN"}` and appends insert-only rows
  `(source, status, detail)`. Its own docstring states the table "has existed in
  `ledger/schema.sql` since Phase 0 … but nothing wrote to it"; it is written today only by
  `bot/main.py`'s account gate and the macro path, has **no reader** anywhere, and is not
  surfaced in any UI. It is the closest existing shape to a normalized enum, but it is a
  bot-internal append-only log, not a queryable current-status contract.
- **Fail-closed `None`** — every adapter under `applications/trading_intelligence/adapters/`
  (`alpaca_paper_source.py`, `alpaca_paper_orders_source.py`, `alpaca_news_source.py`,
  `trades_db_snapshot.py`, `live_price_source.py`, and the five `legacy_*_source.py`)
  returns a bare `None` on **any** failure — missing `config.py`, missing credentials, SDK
  import failure, 401, network error, timeout, 500, malformed response — and the caller
  falls back to an "honest unavailable" section. This is a prose convention repeated in
  ADR-054, ADR-055, and each module docstring; there is no shared type and the failure
  *reason* never reaches the UI.

The one structured distinction that exists — `ReadStatus{OK, ERROR}` at
`applications/trading_intelligence/ui/decision_center/screen.py:49-56`, with
`TradingIntelligenceReadError` (`applications/trading_intelligence/contracts/read_error.py`)
— is 2-state, product-local, and covers only the `sentinel_engine` projection read path,
not external providers.

### 1.2 There is no place that owns such a contract

`applications/platform/` contains identity, entitlements, product/workspace registry,
navigation, and the shell — and **no integration or provider abstraction of any kind**.
`applications/wealth_intelligence/` has no adapters directory (it is a facade over
`sentinel_engine`). `applications/trading_intelligence/adapters/` is the only real external-
integration adapter layer in the platform. There is currently no cross-product location
where a shared integration-health contract could live.

### 1.3 Verified behaviors that silently degrade honesty

- **Fabricated financial data on provider failure.** `dashboard/data.py:184` and `:199`
  return `{symbol: 0.0}` for every symbol when the yfinance batch is empty or raises;
  `:195` sets `prices[sym] = 0.0` per symbol on a parse failure. A real symbol/quantity is
  then rendered next to a fabricated `$0.00` market value.
- **Provider failure masked as "no rows."** `dashboard/data.py:73-80` `safe_query()` returns
  a caller-supplied `default` (often `[]` / `None`) on *any* exception; the caller cannot
  distinguish "query succeeded, zero rows" from "the database read failed."
- **Missing key and rate-limit both become an empty list.**
  `bot/strategy/sentiment.py:104-105` returns `[]` when `NEWSAPI_KEY` is unset;
  `:133-138` returns `[]` on HTTP 426 (quota exhausted). Downstream this is
  indistinguishable from "no headlines exist," and both feed a neutral sentiment score.
- **Whole-cycle abort that cannot name its cause.** `bot/main.py:179-197` aborts the entire
  trading cycle — including exit management — when `client.get_account()` raises or returns
  `portfolio_value <= 0`. The code's own comment at `:191-192` states the value being
  `$0.00` is "likely an auth/connection failure," acknowledging it cannot tell the two
  apart.
- **Authentication failure is indistinguishable from connectivity failure everywhere.** No
  integration in the repository separates `401`/`403` from a timeout or DNS error without
  parsing exception text.

### 1.4 ADR-010 already pointed here

ADR-010 §Non-Goals 6: *"A universal external-data failure policy — this ADR decides
FRED/macro handling only. Any other provider's failure semantics (NewsAPI, SEC, Reddit) is
a separate decision."* This ADR is that separate decision, scoped to the **contract and
ownership layer** — not to any enforcement behavior.

---

## 2. Decision

A repository-wide governance decision, in nine parts. It **defines a contract and assigns
ownership**; it authorizes a narrowly bounded, advisory-only implementation scope (§3
Category A) and defers everything else (§3 Category B). It creates **no** ADR-002 exception.

### 2.1 A platform-level Integration Health abstraction is established, owned by `applications/platform/`

The normalized integration-health contract — the status vocabulary of §2.3, the value shape
that carries it, and the classification mapping of §2.4 — is a **cross-cutting platform
concern**. Its canonical definition is owned by `applications/platform/` (a new area under
it, e.g. `applications/platform/integrations/`, is the expected home; the exact module
layout is an implementation detail this ADR does not fix). This satisfies ADR-044: the
contract must live in a tracked, authoritative location to bind, and `applications/platform/`
is where the platform's other cross-product contracts (identity, entitlements, navigation)
already live.

`sentinel_engine/` is **not** the owner. Per ADR-015 §6.5 the engine core depends on no
product/application/integration package and must not learn about concrete providers
(Alpaca, HuggingFace, yfinance, FRED, …). Integration health is adapter-boundary
infrastructure, not decision-domain reasoning.

### 2.2 Concrete provider adapters stay in their existing product / provider boundaries

This ADR does **not** move, consolidate, or re-home any adapter. Trading Intelligence's
adapters remain in `applications/trading_intelligence/adapters/`, each keeping its own
independent client per the standing "duplicate the primitive, never import the protected
package" convention (ADR-002, ADR-054, ADR-055). The bot's integrations remain inside the
frozen `bot/` tree, untouched. The platform layer owns the **contract**; each product owns
its **conformance to it**.

### 2.3 Provider-level health — normalized status vocabulary (v1, normative)

Every integration, when asked for its health, reports exactly one of:

| Status | Meaning |
|---|---|
| `HEALTHY` | Reachable, authenticated, and returned a well-formed response. The payload may legitimately be empty. |
| `NOT_CONFIGURED` | A required credential or configuration value is absent. Determined **before** any network call is attempted. |
| `AUTH_FAILED` | Credentials were presented and rejected (`401` / `403` / token or signature rejected). |
| `RATE_LIMITED` | The provider signalled quota exhaustion or throttling (`429`, or a provider-specific quota response such as NewsAPI `426`). |
| `UNAVAILABLE` | The provider could not be reached or did not respond in time: DNS failure, connection refused, connect/read timeout, or a transient server error (`502` / `503` / `504`). |
| `API_ERROR` | The provider was reached but the exchange failed in a way the caller did not expect: `500`, an unmapped `4xx`, a `2xx` body that will not parse, or a response whose shape does not match the contract. |

`DEGRADED` (reachable and authenticated, but stale-beyond-intent or partial) is
**explicitly excluded from the v1 normative enum.** The assessment found no authoritative,
unambiguous definition for it: `data_quality_events` uses a `DEGRADED` label, but ADR-010
Amendment 1 rules that a valid within-TTL cached value is *"explicitly not a failure state
and must not be treated as one,"* which leaves "degraded/stale" semantics contested. A
future ADR may add `DEGRADED` (or a separate staleness signal) with a precise definition;
until then, a stale-but-valid read reports `HEALTHY` and staleness is communicated by the
existing verbatim-timestamp rule (ADR-055 §2.6). See §5.

### 2.4 Canonical classification mapping (normative)

| Observed condition | Status |
|---|---|
| Required credential / config value empty or absent (checked before any call) | `NOT_CONFIGURED` |
| HTTP `401`, HTTP `403`, token / signature rejected | `AUTH_FAILED` |
| HTTP `429`; provider-specific quota-exhausted response | `RATE_LIMITED` |
| DNS failure, connection refused, connect/read timeout, HTTP `502` / `503` / `504` | `UNAVAILABLE` |
| HTTP `500`, other `4xx`, unparseable `2xx` body, response-shape mismatch | `API_ERROR` |
| `2xx` and a well-formed response (including zero rows / items) | `HEALTHY` |

### 2.5 The four-way distinction is preserved and mandatory

Consumers of an integration's result MUST be able to tell these four states apart, and no
implementation conforming to this ADR may collapse them:

1. **Genuinely empty, valid data** — the read succeeded and there is legitimately nothing to
   report (`HEALTHY` + an empty payload). This remains distinct from every failure state,
   exactly as the current Trading Intelligence adapters already treat an empty tuple as
   different from `None`.
2. **Unavailable data** — `UNAVAILABLE` or `RATE_LIMITED`.
3. **Authentication / configuration failure** — `AUTH_FAILED` or `NOT_CONFIGURED`.
4. **Provider / API failure** — `API_ERROR`.

**The Integration Health contract MUST preserve a provider failure as a non-`HEALTHY`
state, and consumers within the authorized Category A scope (§3) MUST NOT convert that
state into fabricated, defaulted, or zero-valued financial data. The existing frozen-tree
violations identified in §1.3 remain deferred under Category B and are not authorized to be
corrected by this ADR.** Within the Category A scope, a section backed by an integration
that is not `HEALTHY` renders an explicit non-`HEALTHY` state; it never renders `$0.00`, an
empty table, or normal-looking output that a reader would mistake for real data.

### 2.6 Capability-level health — a separate, advisory resolver

A capability resolver, also owned by `applications/platform/`, MAY derive whether a named
capability is currently available from the health of the integrations that capability
requires (an "all required providers healthy" / "any one required provider healthy" rule
per capability). Examples of capability names: `broker_portfolio_view`, `broker_execution`,
`local_intelligence`. The resolver's output is a derived fact about availability plus the
underlying reason; it is **informational**.

### 2.7 Capability behavior authorized by this ADR is ADVISORY / UI-only

The resolver and the health contract, in the scope this ADR authorizes, may drive:

- what a product screen displays (a clear "execution unavailable" / "not configured" /
  "authentication failed" state instead of blank or fabricated output), and
- operator-facing messaging (which specific reason to name).

They may **not**, in this ADR's scope, block, gate, veto, defer, or alter any operation.
"Alpaca unavailable → the broker capability is *reported* unavailable → the UI clearly
indicates execution is unavailable" is the full extent of the behavior authorized here. No
new autonomous-execution enforcement, and no new trade-blocking, is introduced by this ADR.

### 2.8 Enforcement is explicitly deferred

Any promotion of capability health from advisory to **enforcing** — anything that would
cause an operation to be blocked, gated, or refused because an integration is unhealthy — is
out of scope and requires its own separate ADR. That future ADR must be reconciled with
ADR-047 through ADR-051 (a health-derived block is a safety control, not an advisory
Constitution escalation, and cannot be introduced under those rulings' cover) and, for any
change inside the frozen tree, with ADR-002.

### 2.9 Credential hygiene carries over

The value type that carries an `IntegrationStatus` (and any `detail` string, `repr`, or log
line derived from it) MUST NEVER contain a credential value, for any status — including
`AUTH_FAILED` and `API_ERROR`. This restates, and does not weaken, ADR-054 §2.5 and
ADR-060 §2.2.

---

## 3. Authorized Scope vs. Deferred Scope

### Category A — behaviors this ADR authorizes correcting

Within non-frozen code (`applications/platform/`, `applications/trading_intelligence/`
outside any ADR-002-protected path), a subsequent implementation change MAY, without a
further ADR, and staying strictly advisory / UI-only:

1. Introduce the platform-level `IntegrationStatus` vocabulary, the value type that carries
   it, and the shared classification helper, in `applications/platform/`.
2. Introduce the advisory capability resolver in `applications/platform/`.
3. Change Trading Intelligence adapters so their result also carries an
   `IntegrationStatus` — replacing the single collapsed `None` with a value that still
   distinguishes "genuinely empty" from each failure reason. The read paths stay read-only;
   no new provider, endpoint, credential, or write is added (ADR-054 / ADR-055 unchanged).
4. Change Trading Intelligence screen dataclasses and their rendering so each
   integration-dependent section shows the specific non-`HEALTHY` state
   (`NOT_CONFIGURED` / `AUTH_FAILED` / `RATE_LIMITED` / `UNAVAILABLE` / `API_ERROR`)
   instead of one generic "unavailable" message — via one shared rendering mechanism, not
   per-page provider logic.
5. Add classification to
   `applications/platform/identity/supabase_authentication_provider.py` so a GoTrue failure
   returns a classified health rather than propagating a raw exception.
6. Reconcile the existing `ReadStatus{OK, ERROR}` /
   `TradingIntelligenceReadError` mechanism with the new contract.
7. Add tests for all of the above (see §8).

Category A authorizes a **direction and a vocabulary**, not a design. It prescribes no
module names beyond the ownership statement in §2.1, no class hierarchy, and no wire format.

### Category B — behaviors explicitly deferred to a separate decision

Not authorized by this ADR:

1. Any change inside `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
   `sentinel_engine/`, or `.github/workflows/*.yml`. The verified dangerous behaviors in
   §1.3 that live in `dashboard/data.py` (`{symbol: 0.0}`, `safe_query` default),
   `bot/strategy/sentiment.py` (`return []`), and `bot/main.py` (whole-cycle abort) are
   **named here as the motivation**, but correcting them is frozen-tree work that requires
   its own ADR-002 exception on the ADR-010 / ADR-054 / ADR-060 pattern.
2. Any new trade-blocking, gating, or veto logic anywhere — including any enforcing use of
   the capability resolver.
3. Any change to the Risk Governor, `RiskManager`, or Constitution rule behavior.
4. Any change to execution mode, `EXECUTION_BACKEND`, paper/live selection, or autonomous-
   trading posture.
5. Broker failover, multi-broker routing, or any alternate-provider substitution.
6. A retry, backoff, circuit-breaker, or health-probe *architecture*. (Observing that
   `bot/execution/alpaca_client.py` already has `call_with_retry` is context, not a mandate
   to build a general one.)
7. Any change to ADR-002, or any new execution authority of any kind.
8. Adding `DEGRADED` or any staleness signal to the normative enum.
9. Wiring `data_quality_events` to a reader, or making `bot/` emit the new contract.
10. Registering this contract in the platform documentation indexes (see §9).

---

## 4. Alternatives Considered

1. **Platform-owned contract, product-owned adapters, advisory only (selected).** Puts the
   one shared thing (the vocabulary + mapping) in the one place that already holds cross-
   product contracts, leaves every concrete adapter where ADR-002 / ADR-054 / ADR-055
   require it, and introduces no new control surface. Smallest decision that removes the
   ambiguity the assessment found.
2. **Own it in `sentinel_engine/`.** Rejected: violates ADR-015 §6.5 (engine core must not
   depend on or know about integration packages); integration health is not decision-domain
   reasoning.
3. **Extend ADR-010's FRED mechanism in place, per provider.** Rejected: reproduces the
   current state (N bespoke, incompatible per-provider signals) and ADR-010 §Non-Goals 6
   explicitly declined to be that vehicle.
4. **Treat `data_quality_events` as the contract.** Rejected: it is a bot-internal, insert-
   only log with no reader and a 3-value vocabulary that cannot express the
   `NOT_CONFIGURED` / `AUTH_FAILED` / `RATE_LIMITED` distinctions the assessment identified
   as the core gap. It remains valid as a coarse conformant subset (`DOWN` ⊇
   `{NOT_CONFIGURED, AUTH_FAILED, UNAVAILABLE, API_ERROR}`), noted for a future reader, but
   is not promoted to the contract.
5. **Include enforcement now (health-gated execution).** Rejected: a health-derived block is
   a new preventive safety control; ADR-047–ADR-051 place exactly this class of change
   behind its own governance action, and any frozen-tree wiring needs an ADR-002 exception.
   Deferred to §2.8.
6. **Do nothing; keep the collapsed `None` convention.** Rejected: it is the source of every
   §1.3 finding, and it makes "you never configured this" indistinguishable from "the
   provider is down" for the operator of a real-money-bound trading platform.

---

## 5. `DEGRADED` — Deferred, Not Rejected

A follow-up ADR may introduce a `DEGRADED` status, or a distinct staleness/partial-result
signal, if it supplies a precise, unambiguous definition that is reconciled with ADR-010
Amendment 1's rule that a valid within-TTL cached value is **not** a failure state and must
never influence a refresh-due / TTL decision. Until such a definition exists, v1 consumers
treat a stale-but-valid read as `HEALTHY` and rely on the verbatim persisted-timestamp rule
(ADR-055 §2.6) to keep staleness visible.

---

## 6. Relationship to Existing ADRs

- **ADR-002.** Preserved, unchanged. This ADR authorizes no move, import change, refactor,
  or file change inside `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level
  `ledger/`, or `.github/workflows/*.yml`, and creates no exception to their protection.
  Category A is confined to non-frozen `applications/` code; every frozen-tree correction is
  Category B.
- **ADR-010.** Not modified or reopened. ADR-010's FRED-specific failure-state semantics and
  its (A) persisted-state / (B) observational-metadata split remain exactly as accepted.
  This ADR occupies the "separate decision" ADR-010 §Non-Goals 6 named, for the contract
  layer only, and does not change how `bot/db/macro_cache.py` behaves.
- **ADR-015.** Consistent. This ADR keeps integration-health ownership out of
  `sentinel_engine/` for the same directional-isolation reason ADR-015 §6 states, and
  follows ADR-015's pattern of fixing a contract and a bounded scope while leaving
  downstream work to future governance.
- **ADR-044.** Satisfied. The contract is assigned to a tracked, authoritative location
  (`applications/platform/` + this ADR), not a `docs/architecture/*` draft.
- **ADR-047 / ADR-048 / ADR-049 / ADR-050 / ADR-051.** This ADR stays on the advisory side
  of the boundary those ADRs drew. It introduces no independent veto and no execution-
  blocking behavior; §2.8 routes any future enforcing use through its own ADR, to be
  reconciled with these.
- **ADR-054 / ADR-055.** Cited as motivating examples (their adapters' collapsed-`None`
  failure behavior). Not reopened, not reinterpreted. Their read-only, paper-only,
  consumer-only guarantees are untouched; Category A §3.3 explicitly keeps the read paths
  read-only and adds no provider, endpoint, credential, or write.
- **ADR-056 / ADR-060.** Not reopened or modified. Referenced only for the credential-
  hygiene restatement in §2.9.
- **ADR-058.** This ADR follows the D2/D4 model: it is a **proposal** until it is tracked on
  the authoritative default branch with `Status: Accepted`, landed under the applicable
  write/merge controls. The `Accepted By` line, when added, is metadata, not the source of
  authority.

---

## 7. Evidence / Rationale

- `bot/db/macro_cache.py:24-27, 40-47, 89, 98` — the FRED-only `REASON_*` halt-reason enum
  and its persistence, all failure modes collapsed to `REASON_DATA_UNAVAILABLE`.
- `bot/trust_ledger/data_quality.py:1-9, 15, 22-39` — `data_quality_events` writer;
  `{HEALTHY, DEGRADED, DOWN}`; docstring confirms "nothing wrote to it" historically and
  that it is an operational log, not a decision record; no reader exists in the repository.
- `applications/trading_intelligence/adapters/alpaca_paper_source.py:102-165` — every
  failure path (`no key/secret`, non-paper base URL, SDK import failure, network error,
  malformed response) returns `None`; no reason is retained.
- `applications/trading_intelligence/adapters/alpaca_news_source.py`,
  `alpaca_paper_orders_source.py`, `trades_db_snapshot.py`, `live_price_source.py`,
  `legacy_capital_source.py`, `legacy_regime_source.py`, `legacy_position_source.py`,
  `legacy_candidate_screening_source.py`, `legacy_risk_state_source.py` — same collapsed-
  `None` contract, stated in each module docstring.
- `applications/trading_intelligence/ui/decision_center/screen.py:49-56` — `ReadStatus{OK,
  ERROR}`; its own comment scopes it to "a read that could not be completed," 2-state, for
  the projection read path only.
- `applications/trading_intelligence/contracts/read_error.py` — `TradingIntelligenceReadError`,
  the only typed read-failure boundary in the product, sentinel_engine read path only.
- `applications/platform/` (identity, entitlements, registry, navigation, shell) — contains
  no integration/provider abstraction; `applications/wealth_intelligence/` has no adapters
  directory.
- `dashboard/data.py:73-80` (`safe_query` → `default` on any exception), `:174-199`
  (`_current_prices` → `{symbol: 0.0}` on empty or exception; `:195` per-symbol `0.0`).
- `bot/strategy/sentiment.py:104-105` (`return []` when `NEWSAPI_KEY` unset), `:133-138`
  (`return []` on HTTP 426).
- `bot/main.py:179-197` — `get_account()` failure or `portfolio_value <= 0` aborts the whole
  cycle (exits included); the `:191-192` comment concedes it cannot distinguish an auth
  failure from a connection failure.
- `bot/execution/alpaca_client.py` — `call_with_retry` (429/502/503 + network, bounded
  retries); the only integration with structured transient-error handling, still surfacing
  nothing typed to callers. Cited as context for §3 Category B item 6.
- `docs/decisions/ADR-010-fred-macro-failure-handling.md` §Non-Goals 6 — defers a universal
  external-data failure policy to a separate decision.
- `docs/decisions/ADR-002-bot-runtime-protection.md` §Decision — the frozen set and
  "Permitted in this area: read-only investigation and additive documentation (analysis
  docs, ADRs, architecture-boundary docs)."
- `docs/decisions/ADR-047-...advisory-boundary.md` §Decision 3 — "No Independent Veto";
  ADR-048–ADR-051 the parallel rulings for Rules 2–5.
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` (hierarchy; conflict-resolution rule) and
  ADR-044 §2 — a contract must be tracked and occupy an authoritative role to bind.

---

## 8. Acceptance Criteria

This ADR may be considered Accepted only when the architecture owner has confirmed, in
writing (or the ADR is landed under ADR-058 D2, which is the operative test):

1. Ratification of §2.1 — the generalized Integration Health contract is a platform-level
   concern owned by `applications/platform/`, not `sentinel_engine/` and not any single
   product.
2. Ratification of the v1 normative status vocabulary (§2.3) and classification mapping
   (§2.4), with `DEGRADED` excluded from v1.
3. Ratification of §2.5 — the four-way distinction is mandatory and a provider failure must
   never become fabricated/defaulted financial data.
4. Ratification that capability health in this ADR's scope is **advisory / UI-only** (§2.7)
   and that all enforcement is deferred to a separate ADR reconciled with ADR-047–ADR-051
   and ADR-002 (§2.8).
5. Ratification of the Category A / Category B split (§3) — specifically that no frozen-tree
   change and no trade-blocking logic is authorized here.
6. Confirmation that this ADR creates no ADR-002 exception, reopens no other ADR, and
   authorizes no credential, workflow, deployment, schema, or `sentinel_engine/` change.

Acceptance authorizes only the Category A scope in §3, and only as advisory / UI-only work
inside non-frozen `applications/` code. It does not itself perform any implementation, does
not register this contract in `docs/DOCUMENT_INDEX.md` /
`docs/platform/AARA_ARCHITECTURE_AUTHORITY.md` / `docs/DOCUMENT_GOVERNANCE_MATRIX.md` (see
§9), and does not correct `docs/EXTERNAL_SERVICES.md`.

---

## 9. Follow-On Actions (Not Authorized by This ADR)

- Register this ADR and the `applications/platform/` integration-health area in
  `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s document/area roles and in
  `docs/DOCUMENT_GOVERNANCE_MATRIX.md`, per `docs/DOCUMENT_INDEX.md` §5.
- Correct the stale `docs/EXTERNAL_SERVICES.md` "Outage Handling" row for FRED, which still
  says "no VIX halt (allows buys)" and contradicts ADR-010's accepted decision to block BUY
  when macro state is unavailable.
- A dated addendum to `docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md` §5–7 recording the
  external providers as Trading Intelligence runtime inputs (already flagged as follow-up by
  ADR-054 and ADR-055).
- A separate ADR, if desired, promoting capability health from advisory to enforcing (§2.8),
  and a separate ADR-002 exception for any correction of the §1.3 behaviors that live in the
  frozen tree.

---

## 10. Consequences

**Positive:**

- Gives the platform one citable answer to "what does it mean for an integration to be
  healthy, and who owns that definition," replacing three incompatible partial mechanisms.
- Lets a product — and an operator — tell `NOT_CONFIGURED` from `AUTH_FAILED` from
  `UNAVAILABLE` from `API_ERROR`, which no code in the repository can do today without
  reading exception strings.
- Makes "a provider failure must never render as `$0.00` or an empty table" a binding rule
  rather than an aspiration, for the layers this ADR's Category A scope covers.
- Introduces no new control surface, no enforcement, and no frozen-tree change — the
  smallest decision that closes the ambiguity.
- Keeps `sentinel_engine/` provider-agnostic (ADR-015) and every adapter where ADR-002 /
  ADR-054 / ADR-055 require it.

**Negative / Limitation:**

- The most user-visible dangerous behaviors (`dashboard/data.py`, `bot/strategy/sentiment.py`,
  `bot/main.py`) are in the frozen tree and are **not** fixed by anything this ADR
  authorizes — they remain Category B until a separate ADR-002 exception addresses them.
- Two products exist but only Trading Intelligence has an adapter layer to conform today;
  Wealth Intelligence and any future product inherit the contract but exercise it only when
  they gain external integrations.
- `data_quality_events` stays write-only and reader-less; aligning it is Category B.
- `DEGRADED` / staleness remains unmodelled in v1; stale-but-valid reads report `HEALTHY`
  and depend on timestamp display for honesty until a future ADR defines the signal.
- Advisory-only means an unhealthy required integration still cannot *block* a broker-
  dependent operation; that is deliberate here and deferred to §2.8.

---

## Acceptance

*(Completed only when this ADR is landed under ADR-058 D2. Left as a stub while `Proposed`.
Per ADR-058 D2, authority follows from this document being tracked on the authoritative
default branch with `Status: Accepted`, landed under the applicable write / merge controls;
an `Accepted By` string, if later added, is metadata only and is not the source of
authority. Per ADR-058 D4, authoring or committing this file with `Status: Proposed`
records a proposal only.)*

**Status:** Accepted
