# ADR-054 — Trading Intelligence: Alpaca Paper API as a Read-Only External Data Provider

**Status:** Accepted
**Date Proposed:** 2026-08-27
**Date Accepted:** 2026-08-27
**Decision Type:** Architecture / Governance — External Data-Provider Admission (read-only)
**Related ADRs:** ADR-002 (bot runtime protection — `bot/execution/` order paths
frozen; unaffected), ADR-023 (workflow-file exception precedent — not extended
here), ADR-026 (prior Alpaca-SDK call-shape defect in `bot/` — unrelated),
ADR-035 (HuggingFace `trades.db` pull hazard — referenced by the sibling
ADR-055), ADR-004 (Sentinel-ledger ownership — deferred, untouched)

---

## 1. Context

Trading Intelligence's Portfolio Intelligence and Morning Brief screens (Units
1–3) are product-approved
(`docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` §2/§4;
`docs/products/AARA_TRADING_INTELLIGENCE_UNITS_1_3_DATA_PROVISIONING_SCOPE_DECISION.md`).
Four read-only adapters have already been built and tested for them:

- `applications/trading_intelligence/adapters/alpaca_paper_source.py`
  (`AlpacaPaperSource`) — account + open positions.
- `applications/trading_intelligence/adapters/alpaca_paper_orders_source.py`
  (`AlpacaPaperOrdersSource`) — open + recently-closed order history.
- `applications/trading_intelligence/adapters/alpaca_news_source.py`
  (`AlpacaNewsSource`) — holdings-relevant news headlines (evidence only).
- (`live_price_source.py` — yfinance prices; a prior, market-data-only external
  dependency, authorized inline per "the user's 2026-08-26 decision"; cited here
  only as precedent for the pattern, not re-authorized.)

Each of the three Alpaca adapters states in its own module docstring that it is a
**new dependency class** — an external broker API rather than a local `trades.db`
table — and that this is *"NOT authorized by silent extension of any prior
precedent"* (`alpaca_paper_source.py:6-9`, `alpaca_paper_orders_source.py:4-7`,
`alpaca_news_source.py:5-7`). This ADR is the missing explicit authorization.

Verified properties of the adapters as built (direct inspection this session):

- **Read-only.** Only GET operations are issued: `TradingClient.get_account()`,
  `get_all_positions()`, `get_orders(filter=...)`, `NewsClient.get_news()`. No
  adapter calls `submit_order`, `cancel_order`, `replace_order`,
  `close_position`, `close_all_positions`, `get_account_activities`, or
  `get_portfolio_history`. Regression-lock tests assert this
  (`tests/test_alpaca_paper_source.py`, `tests/test_alpaca_paper_orders_source.py`,
  `tests/test_alpaca_news_source.py`).
- **Paper-only, two independent layers.** (1) `TradingClient(..., paper=True)` is
  hard-coded, never inferred from configuration. (2) `ALPACA_BASE_URL` is checked
  for the literal substring `"paper"` before any client is built; if absent the
  adapter returns `None` (safe-unavailable) rather than proceeding. The News API
  has no paper/live distinction, so only credential presence gates it; it still
  places/cancels nothing.
- **No import of protected code.** No adapter imports `bot.execution.alpaca_client`
  (which also implements order submission) or anything under `bot/`, `dashboard/`,
  `scheduler/`, `database/`, `ledger/`. Each instantiates its own independent
  `alpaca-py` client — the product's standing "duplicate the primitive, never
  import the protected package" convention.
- **Fail-closed.** On missing `config.py`, missing credentials, SDK import
  failure, network/API error, or a malformed provider row, every method returns
  `None` and the caller falls back to the existing honest-unavailable UI section.
  A successful read that matched nothing returns an empty snapshot — a real
  "connected, nothing to report" result, distinct from `None`.
- **Credential source.** `ALPACA_KEY` / `ALPACA_SECRET` / `ALPACA_BASE_URL` are
  read from the top-level `config` module via `try: from config import ... /
  except ImportError:` with empty-string fallback (`config.py` is top-level, not
  under `bot/`, and is not itself ADR-002-protected). In the deployed HF Space
  today `config.py` is not staged and no Alpaca Space secret exists, so all three
  adapters return `None` there — the documented, safe steady state until ADR-056.

## 2. Decision

**Alpaca is admitted as an authorized read-only external data provider for
Trading Intelligence, paper environment only.**

Specifically:

1. Trading Intelligence may call Alpaca **paper** account, positions, and orders
   endpoints as **GET/read operations only**, to populate the already-approved
   Units 1–3 sections.
2. Trading Intelligence may call Alpaca's **news / market-data** endpoint, and
   the result is **evidence/source material only** — never a score, ranking,
   conviction signal, or action input.
3. The paper-only enforcement described in §1 (hard-coded `paper=True` **and**
   the `"paper"` base-URL substring check) is **mandatory** and may not be
   weakened, removed, or made configurable.
4. The adapters must **fail closed**: any unavailability of credentials, network,
   SDK, or a well-formed response yields `None` and the existing UI fallback.
5. Credentials must be supplied **only** from deployment secrets / environment
   configuration (`config.py` reading `os.getenv`). Credential **values** must
   never be committed to the repository, logged, or placed in any exception
   message or return value.
6. The existing adapter boundary is unchanged: no import of `bot/`, `dashboard/`,
   `scheduler/`, `database/`, `ledger/`; each adapter keeps its own independent
   client.

**This ADR grants Trading Intelligence no order-execution authority of any
kind.** Admitting a read path to the paper account is explicitly *not* admitting
a write/execute path.

## 3. Alternatives Considered

1. **Admit Alpaca paper API as a read-only provider (selected).** Matches the
   adapters as already built and tested; smallest addition that makes Units 1–3
   real; every unsafe operation is excluded by construction and locked by tests.
2. **Inline "boundary decision (recorded)" docstring only, no ADR** (the pattern
   used for the SQLite `legacy_*` adapters and `live_price_source.py`). Rejected:
   the adapters' own docstrings state this dependency class is *not* covered by
   that precedent, and an external broker API touching the *account* (not just
   market data) is a durable architectural dependency that belongs in a citable,
   binding record.
3. **Import `bot.execution.alpaca_client` and reuse its client.** Rejected:
   `bot/` is ADR-002-protected, and that module also implements
   `buy()/sell()/sell_market()` — order-submission surface that must never be
   reachable from a read-only adapter.
4. **Do nothing; leave Units 1–3 permanently on the unavailable fallback.**
   Rejected: contradicts the product-approved intent
   (`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` §7;
   `...UNITS_1_3_DATA_PROVISIONING_SCOPE_DECISION.md` §5) that the fallback is an
   operational state, not the steady state.

## 4. Consequences

**Positive:**
- Gives Units 1–3 a citable architectural basis to read real paper-account data.
- Every dangerous Alpaca operation is now explicitly out of scope *and*
  test-locked — future code review can treat any `submit_order`/`cancel_order`/
  `replace_order`/live-endpoint reference in this product as a defect, not a
  design choice.
- No change to `bot/`, its execution paths, or ADR-002's protected set.

**Negative / Limitation:**
- Real data still does not appear in the deployed Space from this ADR alone —
  `config.py` staging and Space-secret provisioning are separate and are gated by
  ADR-056.
- Introduces an external-service runtime dependency (Alpaca availability) into
  the product; mitigated entirely by the fail-closed contract.
- `TRADING_INTELLIGENCE_BOUNDARY.md` §5–§7 does not yet list an external broker
  API among TI's dependencies; a dated addendum there is required follow-up (not
  performed by this ADR).

## 5. Non-Authorization / Scope Boundary

This ADR authorizes **only** §2. It explicitly does **not**:

1. Authorize any order submission, creation, or placement.
2. Authorize any order cancellation.
3. Authorize any order replacement or modification.
4. Authorize any position closing, liquidation, or `close_all_positions`.
5. Authorize any funds transfer, withdrawal, deposit, or journal.
6. Authorize any connection to a live (non-paper) Alpaca account or endpoint.
7. Authorize `get_account_activities`, `get_portfolio_history`, or any Alpaca
   endpoint beyond account / positions / orders (GET) and news.
8. Authorize using news/market data as a trading signal, score, or action input.
9. Weaken, remove, or make configurable the hard-coded `paper=True` or the
   `"paper"` base-URL substring check.
10. Authorize importing `bot/`, `dashboard/`, `scheduler/`, `database/`, or
    top-level `ledger/` from any adapter.
11. Authorize any change to `.github/workflows/*.yml` (including
    `deploy_trading_intelligence.yml`) — that is ADR-056's separate scope.
12. Authorize creating, provisioning, or setting any GitHub or HuggingFace
    secret.
13. Authorize staging `config.py` (or any other file) into the deployed Space.
14. Modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
    or `sentinel_engine/`.
15. Select or affect ADR-004 Option A/B/C, or touch the "ADR-004/Q1" question
    about reading hash-chained Trust Ledger event tables.
16. Amend, reopen, or reinterpret ADR-002, ADR-023, ADR-026, or ADR-035.
17. Add, remove, or re-pin any dependency in any requirements file.

## 6. Relationship to Existing ADRs

**ADR-002:** Unaffected. No protected path is modified. `bot/execution/`'s order
paths remain frozen and are not imported. This ADR concerns a new, independent
read-only adapter set under `applications/trading_intelligence/`, which ADR-002
does not restrict.

**ADR-023:** Not extended. ADR-023 authorized *new* workflow-file creation for
product deployment; it explicitly forbids `config.py` staging and secret
additions. This ADR authorizes neither — those are ADR-056's scope.

**ADR-026:** Unrelated. ADR-026 fixed an `alpaca-py` call-shape defect inside
`bot/_main_market.py`; this ADR adds no code to `bot/` and does not touch that
fix.

**ADR-035:** Referenced only via the sibling ADR-055 (HuggingFace `trades.db`
pull). This ADR's Alpaca adapters open no database and are unrelated to that
hazard.

**ADR-004:** Fully deferred and unaffected. None of the Alpaca adapters read any
`sentinel_engine` ledger or any hash-chained Trust Ledger event table.

## 7. Evidence / Rationale

- `applications/trading_intelligence/adapters/alpaca_paper_source.py` — GET-only
  account/positions; hard-coded `paper=True`; `_is_paper_environment()` substring
  gate; fail-closed `None`.
- `applications/trading_intelligence/adapters/alpaca_paper_orders_source.py` —
  GET `/orders` only; explicit non-call list for `submit/cancel/replace/close_*`;
  `_CLOSED_WINDOW_DAYS = 14`, `_PER_CALL_CAP = 50`; deterministic newest-first
  ordering; `truncated` flag.
- `applications/trading_intelligence/adapters/alpaca_news_source.py` — single GET
  `NewsClient.get_news`; "News is SOURCE / EVIDENCE data only … not a second
  decision authority."
- `applications/trading_intelligence/adapters/live_price_source.py:11-13` —
  precedent that a read-only external live dependency for a Units-1–3 section was
  authorized by an explicit user decision, recorded (inline) — establishing the
  bar this ADR raises to a formal record for the broker-account class.
- `applications/trading_intelligence/bootstrap.py` — `_with_alpaca_paper_data()`,
  `_with_alpaca_orders_data()`, `_build_morning_brief_ui()` wiring: every adapter
  return of `None` leaves the screen on its illustrative/unavailable path.
- `config.py:6-9` — `ALPACA_KEY`/`ALPACA_SECRET` = `os.getenv(..., "")`;
  `ALPACA_BASE_URL` defaults to `https://paper-api.alpaca.markets` (contains
  `"paper"`).
- `docs/products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` §3 — product
  non-goals (no autonomous trading / auto-execution).

## 8. ADR-002 Safety Statement

This ADR does not modify `bot/`, `dashboard/`, `scheduler/`, `database/`,
top-level `ledger/`, `sentinel_engine/`, or any `.github/workflows/*.yml` file.
It does not import any of those packages from any adapter. It authorizes no order
submission, cancellation, replacement, or position closing; no live Alpaca
endpoint; no funds movement; and no autonomous execution path. It creates,
provisions, and modifies no secret. ADR-002 remains exactly as in force as
before this ADR.

## 9. Rollback

This ADR authorizes an architectural admission, not a deployment, ledger, or
protected-path change; reversing it carries no data-level risk:

- Remove/revert the Alpaca read-only provider adapters and their `bootstrap.py`
  wiring introduced under this decision.
- Portfolio Intelligence, and the Morning Brief overnight-holdings-news section,
  return to their existing fallback / data-unavailable behavior.
- No ledger, trading, execution, workflow, secret, or ADR-002-protected-set
  change is implied by this rollback.

## 10. Acceptance Criteria

This ADR may be considered Accepted only when the architecture owner has
confirmed, in writing:
- Ratification of §2 (Alpaca admitted as a read-only, paper-only provider with
  the mandatory enforcement and fail-closed contract), or an explicit rejection
  with reasoning.
- That acceptance authorizes no code change, no workflow change, no secret
  provisioning, and no deployment by itself — implementation remains gated behind
  ADR-056 and behind this ADR's own Non-Authorization list.

## 11. Status

**Accepted — 2026-08-27.**

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-27
**Accepted By:** Architecture Owner

Acceptance ratifies §2 only. Per §10 and the Non-Authorization list (§5), it
authorizes no code, workflow, secret, or deployment change; implementation
remains gated behind ADR-056.
