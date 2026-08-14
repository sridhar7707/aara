# ADR-023: ADR-002 Exception — New Deployment Workflow(s) for AARA Trading/Wealth Intelligence

**Status:** Accepted
**Date:** 2026-08-14

## Scope

Authorizes **creation of new file(s)** under `.github/workflows/` — a path
frozen in its entirety by [ADR-002](ADR-002-bot-runtime-protection.md)
("no moves, no import changes, no refactors, no file changes of any kind")
— for the sole purpose of deploying `applications/trading_intelligence/`
and/or `applications/wealth_intelligence/` to their own Hugging Face
Space(s), independent of `dashboard/`'s existing Space.

This exception covers **new file creation only**. It does not reopen any
of the 8 existing workflow files (`ci.yml`, `deploy_ui.yml`,
`keepalive.yml`, `premarket.yml`, `retrain.yml`, `secret-scan.yml`,
`trade.yml`, `watchdog.yml`) — all remain frozen under ADR-002,
unmodified and unextended by this ADR.

## Reason

A prior read-only audit ("Minimum viable deployment topology for the two
AARA products") established:

- Neither `applications/trading_intelligence/` nor
  `applications/wealth_intelligence/` has any deployment path today.
  `dashboard/` is not a deployment target for either — it is a separate
  brand ("TradeGenius AI"), with its own live production trading
  responsibilities, already ADR-002-protected.
- The smallest deployment architecture that preserves product separation
  requires product-scoped workflow file(s) distinct from `deploy_ui.yml`,
  not a reuse or extension of it.
- Direct precedent already exists for the governance this requires:
  [ADR-017](ADR-017-deploy-analytics-exception.md) and
  [ADR-018](ADR-018-deploy-analytics-gate-exception.md) each required
  their own explicit ADR-002 exception for a single-line change to an
  *already-existing* workflow file. Creating a wholly new file inside the
  same protected directory requires at least the same governance, not
  less.

This ADR exists solely to clear that governance blocker before any
workflow file is written — it authorizes the mechanism, not the
implementation. No workflow file, requirements file, HF Space, or code
change is created by this ADR itself.

## Constraints

**Allowed:**

- Creation of up to two new workflow files under `.github/workflows/` —
  one per product, or one new file containing two independent jobs (the
  audit's Option 1 vs. Option 2 structural choice is **not** decided
  here; it is left to the implementing change).
- Each new workflow file may, for its one named product only:
  - Trigger on changes under that product's own
    `applications/<product>/` directory and/or `sentinel_engine/` (its
    one legitimate shared dependency).
  - Stage that product's own package plus `sentinel_engine/` for upload
    to a Hugging Face Space.
  - Reference a new, product-specific Space-ID secret and `HF_TOKEN`
    (never reusing `dashboard/`'s existing `HF_SPACE_ID`).
  - Reference a new, product-specific requirements file.

**Forbidden:**

- Any change to any of the 8 existing workflow files named in Scope
  above.
- Any change to `dashboard/`, `bot/`, `database/`, `scheduler/`,
  `ledger/`, `config.py`, `requirements.txt`, or `requirements_space.txt`.
- Any change to `applications/trading_intelligence/`,
  `applications/wealth_intelligence/`, `applications/platform/`, or
  `sentinel_engine/` source code — this ADR authorizes deployment
  plumbing only, never product or engine refactoring.
- Actually creating, provisioning, or pushing to any Hugging Face Space,
  or adding any GitHub secret — this ADR authorizes workflow *code*
  only, not the operational act of standing up infrastructure.
- Combining Trading Intelligence's and Wealth Intelligence's deploy
  targets into one Space, or building any shared/platform-shell runtime
  as part of this exception — product separation must be preserved.

## Explicit Non-Decisions

This ADR does not decide:

1. One Space vs. two (the audit's Option 1 vs. Option 2) — left to the
   implementing change.
2. Exact filenames, Space names, or secret names.
3. Which product (Trading Intelligence, Wealth Intelligence, or both) is
   implemented first, or whether both are implemented at all.
4. The Gradio-version compatibility question the audit flagged (Trading
   Intelligence's UI is documented against Gradio 4.44.1; the only
   proven-working HF Space requirements file in this repo pins 5.9.0) —
   the implementing change must resolve this, not this ADR.
5. Requirements-file contents for either product.

## Rollback Plan

Stated before implementation begins, per ADR-002 item 5:

- **If not yet implemented:** no state to unwind — this ADR only lifts a
  restriction; nothing is created by the ADR itself.
- **If a new workflow file is later created under this authorization and
  needs to be rolled back:** delete the new file(s). No other workflow
  file is touched by anything this ADR permits, so no other rollback
  surface exists.
- No `bot/`, `database/`, or `ledger/` state is affected by anything
  this ADR authorizes, so rollback carries no risk to trading data or
  the live write path.

## Validation

- Confirmed via `ls .github/workflows/`: exactly 8 existing files exist
  today, none of which this ADR touches or extends.
- Confirmed via re-read of ADR-002: `.github/workflows/*.yml` is listed
  as a protected path in its entirety; ADR-017 and ADR-018 both required
  their own exception for narrower changes to an already-existing file
  within that same directory, establishing that new-file creation there
  requires no less governance.
- No test-suite impact — this ADR contains no code, no workflow YAML,
  and no application change of any kind.

## Relationship to ADR-002, ADR-017, ADR-018

This ADR supersedes ADR-002's freeze only for the creation of new
file(s) under `.github/workflows/`, scoped exactly as stated in
Constraints above. It does not reopen, modify, or restate ADR-017's or
ADR-018's authorizations — both remain governed solely by their own
ADRs, unaffected and unextended by this one. All ADR-002 protections not
explicitly named here remain in force unchanged, including every one of
the 8 existing workflow files and every other protected path (`bot/`,
`dashboard/`, `scheduler/`, `database/`, `ledger/`).
