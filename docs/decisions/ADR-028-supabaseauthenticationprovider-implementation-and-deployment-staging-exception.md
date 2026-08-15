# ADR-028: SupabaseAuthenticationProvider Implementation and Deployment Staging Exception

**Status:** Accepted
**Date:** 2026-08-15
**Decision Type:** Implementation Authorization (fulfills ADR-027 §7 item 1) + Narrow ADR-002
Exception (deployment workflow staging only)
**Related ADRs:** ADR-027 (selected Supabase Auth but explicitly withheld build authorization —
this ADR is that named future follow-on), ADR-002 (`.github/workflows/*.yml` protection — this
ADR carves out a narrow exception for exactly two already-existing files), ADR-023 (precedent for
`.github/workflows/` exceptions; created the two files this ADR now narrowly reopens), ADR-017/
ADR-018 (precedent that modifying an already-existing workflow file requires its own explicit
exception, not implied by whatever ADR originally created it)

---

## 1. Context

ADR-027 selected Supabase Auth as AARA's initial authentication provider but explicitly withheld
authorization to build it: §3 states *"Implementation of a concrete Supabase-backed
`IdentityProvider`/`AuthenticationProvider` adapter... This ADR authorizes the selection, not the
build."* §7 named this as Deferred Decision #1, "requiring its own future, separately-scoped
work." This ADR is that work.

A read-only audit (this session) established the exact current state:

- `applications/platform/identity/authentication_provider.py` defines `AuthenticationProvider(ABC)`
  with one method, `get_current_user() -> Optional[User]`; `user.py` defines
  `User(user_id, display_name)`. Neither has changed since ADR-027.
- **`applications/platform/` is not staged by either product's deployment workflow today.**
  Neither `deploy_trading_intelligence.yml` nor `deploy_wealth_intelligence.yml` references
  `applications/platform` in any `shutil.copytree` call — confirmed by direct inspection of both
  files. A concrete adapter built under `applications/platform/identity/` would exist in the
  GitHub repository and pass tests, but would not reach either live HuggingFace Space without a
  deployment-workflow change.
- `applications/platform/identity/` has zero internal dependency on any other
  `applications/platform/` submodule (`entitlements/`, `registry/`, `navigation/`, `workspace/`,
  `shell/`) — confirmed via direct grep of its two source files. Staging `identity/` alone (plus
  the required package initializers, named exactly in §2.2 below) is sufficient; the rest of
  `applications/platform/` does not need to be staged for this work.
- `.github/workflows/*.yml` remains frozen in its entirety by ADR-002. ADR-023's exception,
  which created both `deploy_trading_intelligence.yml` and `deploy_wealth_intelligence.yml`,
  explicitly states it "covers new file creation only" — it does not grant an ongoing license to
  modify the files it created. Per the precedent ADR-023 itself cites (ADR-017, ADR-018 — each
  required its own explicit exception for a single-line change to an already-existing workflow
  file), modifying either of these two files now requires this ADR's own explicit authorization,
  not an inherited one.

## 2. Decision

This ADR authorizes exactly three things, and no more:

1. Concrete `SupabaseAuthenticationProvider` implementation.
2. Narrow ADR-002 exception for the two named deployment workflow files.
3. Exactly one pinned Supabase Python SDK dependency added to the two named product
   requirements files, subject to the stated dry-run verification.

### 2.1 Adapter implementation

A concrete `SupabaseAuthenticationProvider` implementing the existing, unmodified
`AuthenticationProvider` interface, in `applications/platform/identity/`. Scope, per the prior
audit's "smallest possible implementation" finding: constructor-injected with an
already-established Supabase session/client; translates it into `User(user_id, display_name)`
via `get_current_user()`. No login flow, no token refresh, no MFA, no session-acquisition
mechanism — those remain deferred exactly as ADR-027 §7 already stated.

### 2.2 Deployment staging exception (ADR-002)

A narrow exception to ADR-002's `.github/workflows/*.yml` freeze, scoped to exactly:

- **File:** `.github/workflows/deploy_trading_intelligence.yml`
- **File:** `.github/workflows/deploy_wealth_intelligence.yml`

Each file's staging step may add exactly the following, confirmed against the current, actual
state of both files' staging blocks:

1. `applications/__init__.py` — **already staged by both files today** (confirmed:
   `shutil.copy("applications/__init__.py", staging / "applications" / "__init__.py")` exists in
   both). No change required for this piece.
2. `applications/platform/__init__.py` — **not currently staged by either file. Must be added**
   (e.g. via `shutil.copy`), required for `applications.platform` to be a valid importable
   package in the staged tree.
3. `applications/platform/identity/` — **not currently staged by either file. Must be added** via
   one new `shutil.copytree` call, inserted immediately after the existing product-package copy
   (current lines 79-85 of `deploy_trading_intelligence.yml`; current lines 78-84 of
   `deploy_wealth_intelligence.yml`).

**No other `applications/platform/` subpackage may be staged by this authorization** —
`entitlements/`, `registry/`, `navigation/`, `workspace/`, and `shell/` remain unstaged; only
`identity/` (item 3) plus its two required initializers (items 1-2) are in scope. No other line
in either file may change. No other file under `.github/workflows/` is reopened by this ADR —
all 8 files named in ADR-023's original scope (`ci.yml`, `deploy_ui.yml`, `keepalive.yml`,
`premarket.yml`, `retrain.yml`, `secret-scan.yml`, `trade.yml`, `watchdog.yml`) remain exactly as
frozen as before.

### 2.3 Dependency addition (not ADR-002-gated, named for completeness)

**Exactly one** Supabase Python SDK package — the specific package the adapter's import statement
actually requires, no more — may be added to `requirements_trading_intelligence.txt` and
`requirements_wealth_intelligence.txt`, subject to:

- An **explicit, exact version pin** (`package==X.Y.Z`), not an unbounded or minimum-only
  constraint.
- A **dry-run dependency-resolution verification** performed before the pin is chosen, following
  the same discipline both files already document for their existing pins (`gradio`,
  `huggingface_hub`, `starlette`) — confirming the pinned version resolves cleanly against the
  rest of each file's existing constraints, not assumed compatible.

No other package, transitive or otherwise, is separately authorized by this ADR beyond what the
chosen Supabase SDK's own dependency resolution requires.

## 3. Explicit Non-Authorization

This ADR does not authorize:

- Any login/session-acquisition flow, token refresh, or MFA implementation.
- Any change to `sentinel_engine/` — the `principal_id` ledger field remains its own,
  separately-scoped future ADR, exactly as ADR-027 §3/§7 already stated. Unchanged by this ADR.
- Any change to `database/`, `ledger/`, `bot/`, `dashboard/`, or `scheduler/`.
- Any FastAPI or other API/session-layer code — still deferred per ADR-027 §7 item 4.
- Any change to `applications/platform/identity/authentication_provider.py` or `user.py`
  themselves — the existing interface and `User` shape are sufficient for this slice and remain
  unmodified.
- Any change to `applications/platform/entitlements/`, `registry/`, `navigation/`, `workspace/`,
  or `shell/` — out of scope; not staged, not touched.
- Any creation of `shared/identity/` or any equivalent shared package — ADR-027's prohibition on
  this remains fully in force and is not reopened or revisited by this ADR.
- Any change to `ci.yml`, `deploy_ui.yml`, `keepalive.yml`, `premarket.yml`, `retrain.yml`,
  `secret-scan.yml`, `trade.yml`, or `watchdog.yml`.
- **Wiring the adapter into `bootstrap.py`.** This is explicitly not authorized by this ADR —
  regardless of `bootstrap.py` not being an ADR-002-protected path, this ADR's authorization does
  not extend to it. Wiring the adapter into either product's composition root requires its own
  future authorization, following this repository's established convention of naming deferred
  work explicitly rather than treating "not protected" as "implicitly permitted."
- Real Supabase credentials, a live Supabase project, or any network call to Supabase — this ADR
  authorizes code that *can* be configured with real credentials later; it does not create or
  require any.

## 4. ADR-002 Compliance (adapted from the Lifting This Protection checklist)

Per ADR-002 §"Lifting This Protection," adapted to this narrow, non-bot-runtime scope (items 3
and 6 of the original checklist — "8 workflow YAML files," "both CLI and scheduler HTTP paths" —
concern `bot/`'s live trading-trigger paths specifically and do not apply here, since neither
deploy workflow touched by this ADR is a trading-trigger path):

1. **Named modules:** exactly the two files and the exact staging additions named in §2.2 above.
   No other file.
2. **Isolated branch/worktree** for implementation, not directly on `main`.
3. **Full regression pass** before and after — both products' existing test suites
   (`applications/trading_intelligence`, `applications/platform`), plus a deployment-verification
   step confirming both Spaces still build and boot successfully with the newly staged
   `applications/platform/identity/` package present. **This verification is a boot check
   only** — it confirms the Space starts and serves its existing Gradio UI with the new package
   importable, nothing more. It does not authorize, require, or involve live Supabase
   authentication, a real Supabase project, or any network call to Supabase, consistent with §3's
   prohibition.
4. **Rollback plan**, stated here, before implementation begins, covering all three artifacts
   §2 authorizes: (a) delete the new `SupabaseAuthenticationProvider` implementation file; (b)
   remove the single pinned Supabase SDK dependency line from both
   `requirements_trading_intelligence.txt` and `requirements_wealth_intelligence.txt`; (c)
   revert the staging additions in both workflow files. None of these three actions touches
   `bot/`, `database/`, or any persistent state — no data-level rollback is required.
5. Not applicable: ADR-002's "two known trading-trigger paths" criterion concerns `bot/`'s
   `trade.yml`/`watchdog.yml` entry points specifically; neither is touched by this ADR.

## 5. Consequences

**Positive:**

- Closes the gap identified in the prior audit: without this ADR, any future adapter would exist
  in the repository but never reach a live Space.
- Scoped narrowly enough that neither of ADR-002's actual trading-runtime risk factors (the two
  live trading-trigger paths) are anywhere near this change.

**Negative / Open Risk:**

- This ADR still does not complete the identity story: `bootstrap.py` wiring (explicitly not
  authorized, §3), the `sentinel_engine` `principal_id` field, real credential provisioning,
  session acquisition, and API/authorization enforcement all remain open, each requiring its own
  future work.
- A deploy-workflow change carries some inherent risk of a Space-boot regression; the rollback
  plan (§4.4) and required full regression pass (§4.3) are the mitigations.

## 6. Status

**Accepted.** This ADR authorizes only what is stated in §2 — acceptance does not
retroactively authorize `bootstrap.py` wiring, real credential use, or any item listed in §3.
