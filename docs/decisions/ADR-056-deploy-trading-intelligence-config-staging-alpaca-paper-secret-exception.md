# ADR-056 — Narrow ADR-002 Exception: Stage `config.py` and Provision Alpaca Paper Credentials for the Trading Intelligence Space

**Status:** Accepted
**Date Proposed:** 2026-08-27
**Date Accepted:** 2026-08-27
**Decision Type:** Narrow ADR-002 Exception (deployment workflow staging only) + named operational credential-provisioning step
**Related ADRs:** ADR-002 (`.github/workflows/*.yml` frozen — this ADR carves one
narrow exception into `deploy_trading_intelligence.yml`), ADR-023 (created
`deploy_trading_intelligence.yml`; its Forbidden list names `config.py` and
secret-adding as out of its scope — this ADR is the separate authorization),
ADR-028 §2.2 / ADR-039 §2 (the established template: each new staging line in
this file needs its own explicit ADR), ADR-017 / ADR-018 (precedent that a
single-line change to an existing workflow file needs its own exception),
ADR-054 (admits the Alpaca paper read-only provider this staging serves),
ADR-055 (the sibling `trades.db` snapshot decision — only relevant here if its
download is placed at deploy time)

---

## 1. Context

`ADR-054` (Proposed) admits Alpaca's paper API as a read-only data provider for
Units 1–3. `ADR-054` alone changes nothing in the deployed HuggingFace Space:
the three Alpaca adapters read `ALPACA_KEY` / `ALPACA_SECRET` /
`ALPACA_BASE_URL` via `try: from config import ... / except ImportError:` with
empty-string fallback, and in the deployed Space today **`config.py` is not
staged** and **no Alpaca Space secret exists**, so all three adapters return
`None` and the sections stay on their honest-unavailable fallback.

`.github/workflows/deploy_trading_intelligence.yml` (created under ADR-023,
extended once under ADR-028 §2.2 and once under ADR-039) currently stages
`applications/`, `applications/platform/{identity,navigation,registry,workspaces,entitlements}/`,
`sentinel_engine/`, `brand/logos/`, `main.py`→`app.py`, and
`requirements_trading_intelligence.txt`. It does **not** stage `config.py`, and
its deploy job's `env:` block passes only `HF_TOKEN` and
`HF_SPACE_ID_TRADING_INTELLIGENCE`.

Per ADR-023's own Forbidden list — *"Any change to … `config.py` …"* and
*"adding any GitHub secret"* — and per the ADR-017/018/028/039 precedent that
each new line in this file needs its own explicit exception, neither the
`config.py` staging line nor the credential provisioning is covered by any
existing authorization. This ADR is that authorization.

**`config.py` content review (performed this session, required before staging a
file verbatim):**

- `config.py` imports only `os` and `dotenv`. **Zero import of anything under
  `bot/`**, `dashboard/`, `scheduler/`, `database/`, `ledger/`, or
  `sentinel_engine/`. It is a leaf constants/environment module.
- Every secret it names is read via `os.getenv(NAME, "")` — `ALPACA_KEY`,
  `ALPACA_SECRET`, `TELEGRAM_TOKEN`, `HF_TOKEN`, `FRED_API_KEY`, `NEWSAPI_KEY`,
  `REDDIT_CLIENT_ID/SECRET`, `FINNHUB_API_KEY`. **No secret value is hard-coded
  in the file.** Staging it verbatim therefore commits/exposes **no
  credential** — only module code, the trading-universe lists (`STOCKS`,
  `ETFS`, `SECTOR_MAP`), and numeric trading-parameter defaults
  (`MAX_POSITION_PCT`, `STOP_LOSS_PCT`, `XGB_MIN_CONFIDENCE`, etc.), all of
  which are already in the public repository.
- `ALPACA_BASE_URL` defaults to `https://paper-api.alpaca.markets` — contains
  the substring `"paper"`, so ADR-054's `_is_paper_environment()` gate passes on
  the default with no `ALPACA_BASE_URL` secret set.

## 2. Decision

A **narrow exception to ADR-002's `.github/workflows/*.yml` freeze**, scoped to
exactly `.github/workflows/deploy_trading_intelligence.yml`, plus a **named
operational credential step** that this ADR gates but does not itself perform.

### 2.1 Workflow staging change (ADR-002 exception)

Add **one** staging step to `deploy_trading_intelligence.yml` that copies the
top-level `config.py` **verbatim** into the staged Space root, so
`from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL` resolves at
Space runtime instead of hitting the `ImportError` fallback. The copy is
byte-for-byte; the file is not rewritten, filtered, or templated.

Nothing else in the file changes — not the trigger `paths`, the Python/Gradio
pins, the existing `copytree`/`copy` steps or their comments, the
`applications/platform/*` staging, the `sentinel_engine/`/`brand/logos/`
staging, `main.py`→`app.py`, `requirements_trading_intelligence.txt`, the README
metadata block, or the `env:` block's existing entries.

### 2.2 Credential provisioning (named operational step, gated by this ADR, not performed by it)

Once §2.1 is merged, the existing **paper** Alpaca credentials already held as
GitHub repository secrets —

- `ALPACA_KEY`
- `ALPACA_SECRET`

— are to be added as **HuggingFace Space secrets** on the Trading Intelligence
Space, so `config.py`'s `os.getenv` calls resolve them at Space runtime.

- These are **paper** credentials. They are the same credentials the bot's
  paper runtime uses; they authenticate only against Alpaca's paper
  environment.
- `ALPACA_BASE_URL` is **not** added as a secret. `config.py`'s default
  (`https://paper-api.alpaca.markets`) is correct and keeps ADR-054's
  `"paper"` substring gate satisfied. Introducing it as a settable secret would
  create a way to point the value elsewhere and is therefore deliberately
  excluded.
- Consistent with ADR-023 / ADR-028 §3 ("this ADR authorizes workflow code
  only, not … adding any GitHub secret" / "it does not create or require
  [credentials]"), the **act of setting the HuggingFace Space secrets is an
  operational step performed by the maintainer**, gated on this ADR's
  acceptance. This ADR authorizes and scopes it; it does not execute it, and
  acceptance of this ADR is not itself the provisioning.

### 2.3 Paper-only enforcement is unchanged

ADR-054's mandatory two-layer paper enforcement in the adapters (hard-coded
`paper=True` **and** the `"paper"` base-URL substring check) stays exactly as
built. This ADR does not touch adapter code and must not be read as relaxing it.
With real credentials present, an adapter that somehow saw a non-paper
`ALPACA_BASE_URL` would still return `None`, not proceed.

## 3. Why staging `config.py` is not "Trading Intelligence takes on the bot runtime configuration as a dependency"

- `config.py` is a **leaf module**: `import os` + `from dotenv import load_dotenv`
  and nothing else. Importing it pulls in **no `bot/` code**, no execution path,
  no scheduler, no database layer. It cannot be a vector into the bot runtime
  because it imports none of it.
- The Trading Intelligence adapters already import **only three names** from it
  (`ALPACA_KEY`, `ALPACA_SECRET`, `ALPACA_BASE_URL`), behind a `try/except
  ImportError`. Staging the file changes *where those three names resolve from*
  (real values vs. `""`); it does not create a new structural coupling — the
  `from config import` line already exists in the shipped adapters.
- The other constants in `config.py` (universe lists, risk parameters) are
  inert data already public in the repo. Trading Intelligence does not read
  them and gains nothing operational by their presence in the staged tree.
- `config.py` is top-level and is **not** an ADR-002-protected path (ADR-002's
  protected set is `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
  `database/`, top-level `ledger/`). The only ADR-002 surface this ADR touches
  is the **workflow file** that does the staging — hence this narrow exception,
  and nothing wider.

## 4. Explicit Non-Authorization

This ADR authorizes exactly §2.1 (one staging line, one named file) and scopes
§2.2 (the operational secret step). It does **not**:

1. Authorize any other line change in `deploy_trading_intelligence.yml` —
   triggers, version pins, existing staging steps/comments, `env:` entries,
   README metadata all unchanged.
2. Authorize any change to `deploy_wealth_intelligence.yml`, `deploy_ui.yml`,
   `ci.yml`, `keepalive.yml`, `premarket.yml`, `retrain.yml`,
   `secret-scan.yml`, `trade.yml`, or `watchdog.yml`.
3. Authorize staging any file other than `config.py` — no `bot/`, `dashboard/`,
   `database/`, `scheduler/`, `ledger/`, `requirements*.txt`, `.env`, or other
   top-level module is staged by this ADR.
4. Authorize adding, introducing, or setting `ALPACA_BASE_URL` (or any Alpaca
   base-URL override) as a GitHub or HuggingFace secret or environment variable.
5. Authorize any **live** Alpaca credential, endpoint, or account.
6. Weaken, remove, or make configurable ADR-054's paper-only adapter
   enforcement.
7. Authorize any change to `applications/trading_intelligence/` adapter or
   bootstrap code.
8. Authorize any order submission, cancellation, replacement, position close, or
   funds movement — none of that is reachable from the code this staging serves
   (ADR-054), and this ADR adds no such capability.
9. Authorize a `trades.db` pull step in this workflow — if ADR-055's download is
   placed at deploy time rather than Space runtime, that staging line is a
   **separate** addition still requiring its own explicit authorization (it may
   be folded into this ADR only by an explicit amendment naming it).
10. Modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
    `sentinel_engine/`, or `config.py`'s **contents**.
11. Deploy anything, or trigger a deploy, by itself.
12. Amend, reopen, or reinterpret ADR-002, ADR-023, ADR-028, or ADR-039.

## 5. Rollback Plan (stated before implementation, per ADR-002 item 5)

Precise, three parts, in order:

1. **Revert the workflow change.** Delete the single `config.py` staging step
   from `deploy_trading_intelligence.yml`, restoring it to its exact
   pre-ADR-056 content (ADR-039-era staging set). This is an additive one-step
   change; reverting it is a clean one-line delete.
2. **Remove the two HuggingFace Space secrets.** Delete `ALPACA_KEY` and
   `ALPACA_SECRET` from the Trading Intelligence Space settings. The GitHub
   repository secrets of the same name are **left untouched** — they predate
   this ADR and are used by `trade.yml` and others.
3. **Restore previous staging behavior.** With (1) reverted, the next deploy
   ships without `config.py`; the adapters' `except ImportError` path re-engages;
   `get_account()` / `get_positions()` / `get_recent_orders()` /
   `get_overnight_holdings_news()` return `None`; and each section returns to its
   honest-unavailable fallback — the exact state before this ADR. No
   `applications/` code change is needed for the rollback because the fallback
   is already in the shipped code.

No `bot/`, `database/`, `ledger/`, or persistent trading state is touched by
anything this ADR authorizes, so rollback carries no data-level risk.

## 6. ADR-002 Compliance (adapted from "Lifting This Protection", per ADR-028 §4 / ADR-039 §4 precedent for this same file)

1. **Named file, named line:** exactly `.github/workflows/deploy_trading_intelligence.yml`,
   exactly one added `config.py` staging step, at the staging block. No other
   file, no other line.
2. **Isolated branch/worktree** for implementation, not directly on `main`.
3. **Verification before merge:** replicate the staged tree locally with
   `config.py` present and confirm
   `python -c "from applications.trading_intelligence.bootstrap import build_application; build_application()"`
   still imports and builds; run
   `applications/trading_intelligence/tests/` and
   `applications/trading_intelligence/ui/tests/` (both already green; this ADR
   changes no Python source). Post-deploy: confirm the Space boots and serves
   its existing Gradio UI (boot check only). Confirm
   `deploy_wealth_intelligence.yml` is byte-identical before and after.
4. **Rollback plan:** §5 above, written before implementation.
5. **Trading-trigger-path criterion:** not applicable — this file deploys a
   Gradio Space with no relationship to `bot/`'s CLI or watchdog trading-trigger
   paths (same finding as ADR-028 §4.5 / ADR-039 §4.5 for this file).

## 7. Relationship to Existing ADRs

**ADR-002:** One narrow exception, `deploy_trading_intelligence.yml` only, one
additive `config.py` staging line. Every other ADR-002 protection — all other
workflow files, `bot/`, `dashboard/`, `scheduler/`, `database/`, `ledger/` —
remains in force unchanged.

**ADR-023:** This ADR provides exactly the authorization ADR-023's Forbidden
list said it did not grant (`config.py`, secrets). ADR-023's other constraints
are unaffected.

**ADR-028 / ADR-039:** Same file, same template, same compliance structure. This
ADR does not reopen, extend, or restate their `applications/platform/*` staging
authorizations.

**ADR-054:** This ADR is the deployment half of ADR-054's intent. It authorizes
no capability ADR-054 does not already scope; if ADR-054 is not Accepted, this
ADR has nothing to serve and should not be implemented.

**ADR-055:** Independent. This ADR does **not** stage a `trades.db` pull. If
ADR-055's download is later placed at deploy time, that is a separate staging
line needing its own authorization.

## 8. ADR-002 Safety Statement

This ADR modifies exactly one line region of one workflow file and provisions
two **paper** credentials as Space secrets via a named operational step it does
not itself execute. It does not modify `bot/`, `dashboard/`, `scheduler/`,
`database/`, top-level `ledger/`, `sentinel_engine/`, any other workflow file,
any adapter, `config.py`'s contents, or any requirements file. It authorizes no
live endpoint, no order operation, and no autonomous execution. It performs no
deployment. All ADR-002 protections not named in §2.1 remain exactly as in
force.

## 9. Acceptance Criteria

Accepted only when the architecture owner confirms in writing:
- That ADR-054 is Accepted (this ADR serves it and should not precede it).
- Ratification of the one-line `config.py` verbatim staging change and the
  scoped provisioning of `ALPACA_KEY` / `ALPACA_SECRET` (paper) as Space
  secrets, with `ALPACA_BASE_URL` deliberately excluded.
- That acceptance authorizes the workflow edit and names the operational secret
  step, but does not itself edit the workflow, set any secret, or deploy.

## 10. Status

**Accepted — 2026-08-27.**

## Acceptance

**Status:** Accepted
**Date Accepted:** 2026-08-27
**Accepted By:** Architecture Owner

Prerequisite satisfied: ADR-054 is Accepted (see §9). Acceptance ratifies §2.1
(the one `config.py` staging line) and scopes §2.2 (the operational secret step);
per §4, §5, and §8 it authorizes no other workflow change, performs no secret
provisioning, and triggers no deployment. The workflow edit and the Space-secret
provisioning remain subsequent operational actions.
