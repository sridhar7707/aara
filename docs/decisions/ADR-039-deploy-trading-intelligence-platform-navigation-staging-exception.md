# ADR-039: Deploy Trading Intelligence — Platform Navigation/Registry/Workspace/Entitlement Staging Exception

**Status:** Accepted
**Date:** 2026-08-17
**Decision Type:** Narrow ADR-002 Exception (deployment workflow staging only) — Incident Remediation
**Related ADRs:** ADR-002 (`.github/workflows/*.yml` protection this ADR carves a narrow exception
into), ADR-023 (created `deploy_trading_intelligence.yml`, the file this ADR modifies), ADR-028 §2.2
(established the *only* prior staging exception to this file — `applications/platform/identity/`
only — and explicitly named `entitlements/`, `registry/`, `navigation/`, `workspace/`, and `shell/`
as reserved, unstaged, future work; this ADR is that named follow-on for four of the five), ADR-038
(authorized and implemented the `bootstrap.py`/`entitlements.py` changes that introduced the imports
this ADR's staging gap breaks — already merged to `main`; this ADR does not modify or reopen any
part of ADR-038's own authorization), ADR-017/ADR-018 (precedent that modifying an already-existing
workflow file requires its own explicit exception, not implied by whatever ADR originally created it)

---

## 1. Context

**Production incident, this session.** The live Trading Intelligence HuggingFace Space is
crash-looping on startup:

```
ModuleNotFoundError: No module named 'applications.platform.navigation'
  File "/home/user/app/applications/trading_intelligence/bootstrap.py", line 52, in <module>
    from applications.platform.navigation.navigation_builder import NavigationBuilder
```

A read-only audit (this session) traced the exact root cause:

- ADR-038 was accepted and implemented in commit `ff4a68a` (already on `origin/main`; local
  working tree confirmed clean, no divergence from `origin/main`). Its `bootstrap.py` now imports
  `applications.platform.navigation.navigation_builder.NavigationBuilder`,
  `applications.platform.registry.product_registry.{Product,ProductRegistry}`, and
  `applications.platform.workspaces.{workspace.Workspace,workspace_registry.WorkspaceRegistry}` at
  module import time (unconditional top-level imports, not deferred). Its new
  `applications/trading_intelligence/entitlements.py` imports
  `applications.platform.entitlements.entitlement_checker.EntitlementChecker`, also at module import
  time.
- `.github/workflows/deploy_trading_intelligence.yml:87-100` stages **only**
  `applications/platform/identity/`, plus `applications/platform/__init__.py` — this is ADR-028
  §2.2's exact, narrow, already-Accepted scope. Its own comment (lines 87-90) already states this
  explicitly: *"applications/platform/identity/ only (not the rest of applications/platform/)."*
  ADR-028 §3 lists `entitlements/`, `registry/`, `navigation/`, `workspace/`, and `shell/` as
  reserved for exactly this kind of future, separately-scoped follow-on — it does not forbid ever
  staging them, only forbids this ADR's own predecessor from doing so.
- `applications/trading_intelligence/` itself is staged in full via `shutil.copytree` (lines
  81-85) — the new `entitlements.py` file **is** present in the Space. The failure is entirely
  about its *dependency* (`applications.platform.entitlements`), not about itself.
- **Import-graph trace, confirmed by direct inspection, of every module `bootstrap.py`/
  `entitlements.py` newly reach into:**
  - `applications/platform/navigation/navigation_builder.py` imports `entitlements.
    entitlement_checker` (unstaged), `identity.authentication_provider` (already staged, under
    `identity/`), `navigation.navigation_item`, `navigation.navigation_model` (both inside the
    same `navigation/` package), `registry.product_registry` (unstaged), and `workspaces.
    workspace_registry` (unstaged).
  - `applications/platform/registry/product_registry.py` imports only `abc`/`dataclasses`/
    `typing` — no cross-package dependency.
  - `applications/platform/workspaces/workspace_registry.py` imports `workspaces.workspace`
    (same package) only.
  - `applications/platform/entitlements/entitlement_checker.py` imports `identity.user` (already
    staged, under `identity/`) only.
  - **Exactly four subpackages are missing, and staging them closes the entire gap**:
    `navigation/`, `registry/`, `workspaces/`, `entitlements/`. No fifth subpackage is
    transitively required. `shell/` (`ShellBuilder`/`ShellModel`) is not imported by anything
    ADR-038 authorized or implemented — per ADR-038 §1's own finding, `ShellBuilder` is a
    dead-end branch nothing in this codebase consumes — and staging it would be unauthorized
    scope creep this ADR does not take.
- **This is a governance-process gap, not a code defect.** ADR-038 §7 (Verification) required
  `scripts/arch_review.py --diff` and the full local test suite — both pass today, and both did
  before this incident, because every package exists locally. Neither ADR-038's own text nor any
  of the (multiple) acceptance/closeout audits performed against it checked
  `deploy_trading_intelligence.yml`'s staging scope. This ADR closes that specific gap; it is not a
  retroactive re-review of ADR-038's own authorization, which remains correct and unchanged.

## 2. Decision

Extend `.github/workflows/deploy_trading_intelligence.yml`'s existing staging step with exactly
four new `shutil.copytree` calls, immediately after the existing `applications/platform/identity/`
copytree (current lines 96-100) and before the `sentinel_engine/` copytree (current line 104):

```python
shutil.copytree(
    "applications/platform/navigation",
    staging / "applications" / "platform" / "navigation",
    ignore=skip_tests_and_cache,
)
shutil.copytree(
    "applications/platform/registry",
    staging / "applications" / "platform" / "registry",
    ignore=skip_tests_and_cache,
)
shutil.copytree(
    "applications/platform/workspaces",
    staging / "applications" / "platform" / "workspaces",
    ignore=skip_tests_and_cache,
)
shutil.copytree(
    "applications/platform/entitlements",
    staging / "applications" / "platform" / "entitlements",
    ignore=skip_tests_and_cache,
)
```

Each of the four source directories already has its own `__init__.py` (confirmed present:
`applications/platform/navigation/__init__.py`, `.../registry/__init__.py`, `.../workspaces/
__init__.py`, `.../entitlements/__init__.py`), so `shutil.copytree` alone makes each a valid,
importable package under the already-staged `applications/platform/__init__.py` parent — no
additional `shutil.copy` step is required, unlike `applications/platform/__init__.py` itself
(which needed one because `identity/`'s original copytree didn't create the parent package marker).

`shell/` is **not** staged by this authorization — see §1's import-graph finding.

## 3. Explicit Non-Authorization

This ADR authorizes exactly the four `shutil.copytree` additions in §2, in exactly the one named
file. It does not authorize:

- **Staging `applications/platform/shell/`.** Not required by any currently-authorized import;
  remains unstaged, exactly as ADR-028 §3 left it.
- **Any other line change in `deploy_trading_intelligence.yml`** — trigger paths, Python/Gradio
  version pins, the `sentinel_engine/`/`brand/logos/` staging, the `app.py`/`requirements.txt`
  copy steps, and the Space README metadata block all remain exactly as they are.
- **Any change to `deploy_wealth_intelligence.yml`, `deploy_ui.yml`, `ci.yml`, `keepalive.yml`,
  `premarket.yml`, `retrain.yml`, `secret-scan.yml`, or `trade.yml`.** Wealth Intelligence's
  `bootstrap.py` does not import any of these four subpackages (ADR-038 never touched it) and has
  no equivalent staging gap.
- **Any change to `applications/trading_intelligence/bootstrap.py`, `applications/
  trading_intelligence/entitlements.py`, or any other ADR-038 implementation file.** That
  implementation is correct and unchanged; this ADR fixes only what reaches it in deployment.
- **Any change to ADR-002, ADR-023, ADR-028, or ADR-038 themselves.**
- **Any real Supabase credential, live client, or network call.** Unaffected — still governed by
  ADR-028 §3/ADR-029 §3's continuing prohibition.
- **Any new dependency, requirements-file change, or Gradio/Python version change.**

## 4. ADR-002 Compliance (adapted from the Lifting This Protection checklist, per ADR-028 §4's
precedent for this exact file)

1. **Named file, named lines only:** exactly `.github/workflows/deploy_trading_intelligence.yml`,
   exactly the four `copytree` calls in §2, inserted at the one named location. No other file, no
   other line.
2. **Isolated branch/worktree** for implementation, not directly on `main`.
3. **Verification before merge:** replicate the staging step's four new `copytree` calls into a
   local temp directory (the same pattern the workflow itself uses) and confirm
   `python -c "from applications.trading_intelligence.bootstrap import build_application"`
   succeeds against that staged tree with `sys.path` pointed at it alone — proving the fix closes
   the actual gap before it is ever pushed, not assumed from the import-graph trace in §1 alone.
   Full `applications/trading_intelligence/tests/` and `applications/platform/tests/` suites
   re-run as a sanity check (both already pass today; this ADR does not change local behavior at
   all, only deployed behavior).
4. **Rollback plan, stated before implementation begins:** revert the four-`copytree` diff in
   `deploy_trading_intelligence.yml`. This is a workflow-only, additive-staging change — no data,
   schema, or application-code rollback is required. Note explicitly: reverting *this* ADR's change
   after it has fixed the live incident would restore the staging gap and the crash; this rollback
   plan describes undoing this specific change if it independently causes a *new* problem, not a
   recommended response to the current outage.
5. **Trading-trigger-path criterion:** not applicable — this file deploys a Gradio Space with no
   relationship to `bot/`'s CLI or watchdog-mediated trading-trigger paths (same finding ADR-028
   §4.5 already made for this same file).

## 5. Verification

- Local replication of the staged tree (per §4 item 3) confirms `build_application()` importable
  and callable with only the files this ADR stages, `applications/trading_intelligence/`, and
  `sentinel_engine/` present — nothing else.
- Full `applications/trading_intelligence/tests/`, `applications/platform/tests/` suites pass
  (regression check; this ADR does not change any Python source file, only what a separate
  workflow stages).
- Post-deploy: confirm the Space boots and serves its existing Gradio UI — a boot check only, per
  ADR-028 §4.3's own precedent; does not exercise real Supabase authentication or any entitlement
  decision (still inert per ADR-038 §3, unchanged by this ADR).
- Confirm `deploy_wealth_intelligence.yml` is byte-identical before and after — this ADR touches
  one file only.

## 6. Consequences

**Positive:**

- Closes the exact gap causing the live outage, using the narrowest possible mechanism: four
  additive `copytree` calls, one file, matching the same pattern and precedent ADR-028 §2.2 already
  established for `identity/`.
- Completes four of the five subpackages ADR-028 §3 named as reserved future staging work,
  without staging the fifth (`shell/`) that nothing currently needs — the narrowest slice that
  closes the incident, not the broadest one that could.
- Requires zero change to any already-Accepted ADR's authorization, including ADR-038's own —
  the bug was in what gets deployed, not in what was authorized to be built.

**Negative / Open Risk:**

- **The Space remains down until this ADR is accepted and its workflow change is implemented,
  reviewed, and pushed** — this ADR is a fix proposal, not the fix itself; per this repository's
  own `.github/workflows/*.yml` protection, no one may push it without the acceptance step this
  document is awaiting.
- If any import path was missed in §1's trace (verified by direct inspection, not assumed), the
  boot check in §5 would surface it before merge, but this is not a mathematical guarantee absent
  that verification step actually being run.
- This is the second incident in this repository's identity/access chain traceable to a staging
  gap (the first being ADR-028 §2.2's own original finding, before `identity/` was staged) —
  suggests `deploy_trading_intelligence.yml`'s staging scope should be checked as part of any
  future ADR that adds a new cross-package import to `bootstrap.py`, though formalizing that check
  is not itself authorized or attempted by this ADR.

## 7. Status

**Accepted.** This ADR authorizes only the four `shutil.copytree` additions named in §2, in
`.github/workflows/deploy_trading_intelligence.yml` only — acceptance does not retroactively
authorize anything listed in §3, and does not reopen ADR-002, ADR-023, ADR-028, or ADR-038.
Implementation (the actual workflow-file edit, verification per §4, and push) remains a separate,
explicit step this acceptance does not itself perform.
