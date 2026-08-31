# ADR-062: Deploy Trading Intelligence — Platform Integrations Staging Exception

**Status:** Accepted
**Date Proposed:** 2026-08-31
**Decision Type:** Narrow ADR-002 Exception (deployment workflow staging only) — Incident Remediation
**Related ADRs:** ADR-002 (`.github/workflows/*.yml` protection this ADR carves one
further narrow exception into), ADR-023 (created `deploy_trading_intelligence.yml`, the
file this ADR modifies; its Forbidden list requires each new line to have its own
exception), ADR-028 §2.2 (established the *first* staging exception to this file —
`applications/platform/identity/` only — and named `entitlements/`, `registry/`,
`navigation/`, `workspace/`, and `shell/` as reserved, separately-scoped future work),
ADR-039 (the direct structural precedent: the *identical* incident class — live Space
`RUNTIME_ERROR` from a `bootstrap.py` module-scope import of an unstaged
`applications/platform/` subpackage — fixed by additive `shutil.copytree` calls in this
same file; this ADR follows ADR-039 §2/§3/§4/§5/§7 line for line, staging one package
instead of four), ADR-056 §2.1 (added the `config.py` staging line — a *different*
additive staging line in the same file; unchanged and not reopened here), ADR-060 (added
the `env:` lines and the `add_space_secret` sync block — again a *different* additive
change in the same file; unchanged and not reopened here), ADR-061 including Amendment 1
(authorized the Category A / A3+A4 work that introduced the imports this ADR's staging gap
breaks, and — in Amendment 1's "Not authorized by this amendment" list — explicitly
deferred *this exact change* as "a separate future ADR-002 governance item (see §9)";
this ADR is that governance item), ADR-058 (D2/D4 ratification model this ADR follows),
ADR-017/ADR-018 (precedent that modifying an already-existing workflow file requires its
own explicit exception, not implied by whatever ADR originally created it)

---

## 1. Context / Problem

**Production incident, live now.** The deployed Trading Intelligence HuggingFace Space
(`ksri77/aara-trading-intelligence`) is in `RUNTIME_ERROR` and crash-looping on startup.
`HfApi().get_space_runtime(...)` returns `stage: RUNTIME_ERROR`; the Space run log shows,
on every restart:

```
Exit code: 1. Reason: Traceback (most recent call last):
  File "/home/user/app/app.py", line 26, in <module>
    from applications.trading_intelligence.bootstrap import build_trading_intelligence_app
  File "/home/user/app/applications/trading_intelligence/bootstrap.py", line 55, in <module>
    from applications.trading_intelligence.adapters.alpaca_news_source import (
  File "/home/user/app/applications/trading_intelligence/adapters/alpaca_news_source.py", line 67, in <module>
    from applications.platform.integrations import (
ModuleNotFoundError: No module named 'applications.platform.integrations'
```

### 1.1 Root cause (read-only audit, this session)

- **The import was introduced by ADR-061 Category A.** Commit `922bbe9` ("Implement
  ADR-061 integration health contract") made the Trading Intelligence adapters carry
  `IntegrationHealth` / `ReadResult` (ADR-061 §3 Category A item 3). Direct inspection of
  the staged tree (`applications/trading_intelligence/`) confirms **eleven** module-scope
  imports of the package:
  - all ten adapters — `alpaca_news_source.py:67`, `alpaca_paper_orders_source.py:83`,
    `alpaca_paper_source.py:87`, `legacy_candidate_screening_source.py:55`,
    `legacy_capital_source.py:47`, `legacy_position_source.py:52`,
    `legacy_regime_source.py:48`, `legacy_risk_state_source.py:54`,
    `live_price_source.py:54`, `trades_db_snapshot.py:97`;
  - `applications/trading_intelligence/ui/integration_health_view.py:24` (ADR-061 A4);
  - `applications/trading_intelligence/ui/{morning_brief,portfolio_intelligence,risk_intelligence}/screen.py`.

  `bootstrap.py:55` imports `alpaca_news_source` at module load, so the very first line
  of `app.py` (`from applications.trading_intelligence.bootstrap import
  build_trading_intelligence_app`) reaches the unstaged package and the process exits 1
  before Gradio ever starts.

- **`deploy_trading_intelligence.yml` does not stage `applications/platform/integrations/`.**
  The staging step currently copies `applications/__init__.py`,
  `applications/platform/__init__.py`, and — via `shutil.copytree` —
  `applications/platform/{identity, navigation, registry, workspaces, entitlements}`
  (ADR-028 §2.2 for `identity/`; ADR-039 §2 for the other four). `shell/` and
  `integrations/` are the two `applications/platform/` subpackages not staged.

- **This gap was known and deliberately deferred.** ADR-061 Amendment 1, under *"Not
  authorized by this amendment"*, states verbatim:

  > Any `.github/workflows/*.yml` change — §3 Category B item 1 stands. **Staging
  > `applications/platform/integrations/` into the deployed Space remains a separate
  > future ADR-002 governance item (see §9).**

  ADR-061 §3 Category B item 1 lists `.github/workflows/*.yml` among the paths "Not
  authorized by this ADR", each requiring "its own ADR-002 exception". This ADR is that
  separate governance item — the exact analog of ADR-039 being ADR-028 §3's named
  follow-on for the packages ADR-028 reserved.

- **This is a governance-process gap, not a code defect.** ADR-061 Category A + Amendment 1
  authorized the adapter and rendering changes; those changes are correct, tested
  (`applications/trading_intelligence/` = 938 passing locally), and land cleanly wherever
  every `applications/platform/` package exists (local dev, CI). The deploy workflow's
  staging scope is the only thing that did not keep pace, and ADR-061 Amendment 1
  explicitly routed that to a separate ADR — this one. This ADR does not retroactively
  re-review, amend, reopen, or reinterpret ADR-061's own authorization.

### 1.2 Import-graph trace of `applications/platform/integrations/` (confirmed by direct inspection)

The package is exactly four source files plus a `tests/` directory:

- `applications/platform/integrations/__init__.py` — imports only from
  `applications.platform.integrations.{capability, classification, health}` (its own
  submodules).
- `applications/platform/integrations/health.py` — `dataclasses`, `datetime`, `enum`,
  `typing` (stdlib) only.
- `applications/platform/integrations/classification.py` — `concurrent.futures`, `json`,
  `socket`, `typing` (stdlib) + `applications.platform.integrations.health` (same
  package). `socket` is imported for `isinstance` checks against exception types; it
  opens no connection.
- `applications/platform/integrations/capability.py` — `dataclasses`, `enum`, `typing`
  (stdlib) + `applications.platform.integrations.health` (same package).

No file under `integrations/` imports `identity/`, `navigation/`, `registry/`,
`workspaces/`, `entitlements/`, `shell/`, `sentinel_engine`, `bot`, `dashboard`,
`scheduler`, `database`, `ledger`, or any third-party library (each module's docstring
asserts this; grep confirms it). **Staging this one package closes the entire gap** — no
fifth subpackage, no `__init__` shim, and no new dependency is transitively required.
`applications/platform/__init__.py` is already staged, so a bare `shutil.copytree` makes
`integrations/` a valid importable package under it — the same mechanic ADR-039 §2 relied
on for its four packages.

---

## 2. Decision

A **narrow exception to ADR-002's `.github/workflows/*.yml` freeze**, scoped to exactly
`.github/workflows/deploy_trading_intelligence.yml`, comprising **one** additive
`shutil.copytree` call and nothing else.

### 2.1 Exact authorization (workflow staging change)

Add **one** `shutil.copytree` call to the staging step of
`.github/workflows/deploy_trading_intelligence.yml`, immediately after the existing
`applications/platform/entitlements` copytree (current lines 126–131, closing `)` at line
131) and before the `# Shared Sentinel Intelligence Engine` comment / `sentinel_engine/`
copytree (current line 133–137):

```python
          shutil.copytree(
              "applications/platform/integrations",
              staging / "applications" / "platform" / "integrations",
              ignore=skip_tests_and_cache,
          )
```

An accompanying one-line comment naming this ADR and the reason (mirroring the existing
`# ADR-028 …` and `# ADR-039 …` comments) is authorized as part of this change, e.g.:

```python
          # ADR-062: applications/platform/integrations/ -- the ADR-061 IntegrationHealth
          # contract, imported at module scope by bootstrap.py's adapter chain. Self-
          # contained (stdlib + intra-package only); no fifth subpackage required.
```

`skip_tests_and_cache` is the workflow's already-defined
`shutil.ignore_patterns("__pycache__", "tests")`, so `integrations/tests/` and
`integrations/__pycache__/` are excluded exactly as they are for every other
`copytree`'d package. The four files that reach the Space are precisely
`applications/platform/integrations/{__init__.py, health.py, classification.py, capability.py}`.

### 2.2 Why one package closes the whole gap

Per the §1.2 import-graph trace: `integrations/` depends only on the Python standard
library and its own submodules. Unlike ADR-039's case (where `navigation/` chained into
`entitlements/`, `registry/`, and `workspaces/`), there is no transitive `applications/`
dependency here. Staging `integrations/` alone makes every one of the eleven module-scope
importers in §1.1 resolvable at Space runtime.

### 2.3 Scope

This ADR authorizes exactly the single `shutil.copytree` block in §2.1 (plus its
one-line ADR-referencing comment), in exactly the one named file, at exactly the one
named location. Acceptance authorizes nothing else and does not itself perform the edit,
the verification, or any deploy.

---

## 3. Explicit Non-Authorization

This ADR does **not**:

1. **Authorize staging any `applications/platform/` subpackage other than
   `integrations/`.** `shell/` in particular remains unstaged, exactly as ADR-028 §3 and
   ADR-039 §3 left it — nothing currently imports it. Any future need to stage `shell/`
   (or any other subpackage) requires its own separate exception on this same template.
2. **Authorize any other line change in `deploy_trading_intelligence.yml`** — the trigger
   `paths`, the Python/Gradio version pins, the Space README metadata block, the
   `applications/__init__.py` / `applications/platform/__init__.py` / `identity/` /
   `navigation/` / `registry/` / `workspaces/` / `entitlements/` staging (ADR-028 §2.2,
   ADR-039 §2), the `sentinel_engine/` and `brand/logos/` staging, `main.py`→`app.py`,
   the `requirements_trading_intelligence.txt`→`requirements.txt` copy, the
   `Deploy to HuggingFace Spaces` step's `env:` block, the ADR-056 §2.1 `config.py`
   staging line, and the ADR-060 §2.2 `add_space_secret` sync block all remain **exactly
   as they are**.
3. **Authorize any change to `config.py` staging.** That is ADR-056 §2.1, already
   Accepted; this ADR neither modifies, extends, nor reopens it.
4. **Authorize any Space-secret synchronization change.** That is ADR-060 §2.1/§2.2,
   already Accepted; this ADR neither modifies, extends, nor reopens it.
5. **Authorize any `requirements_trading_intelligence.txt` change** (or any other
   `requirements*.txt` change), including adding `python-dotenv`. Whether `config.py`'s
   `from dotenv import load_dotenv` needs an explicit Space dependency is a separate
   matter, outside this ADR, and is not resolved here.
6. **Authorize any change to `deploy_wealth_intelligence.yml`, `deploy_ui.yml`,
   `ci.yml`, `keepalive.yml`, `premarket.yml`, `retrain.yml`, `secret-scan.yml`,
   `trade.yml`, `watchdog.yml`, or any other workflow.** Wealth Intelligence's
   `bootstrap.py` does not import `applications.platform.integrations` and has no
   equivalent staging gap.
7. **Authorize any change to Python source** — `bootstrap.py`, any adapter,
   `applications/platform/integrations/` itself, or any ADR-061 implementation file. The
   implementation is correct and unchanged; this ADR fixes only what is *deployed*.
8. **Amend, reopen, reinterpret, or broaden ADR-061 or its Amendment 1.** ADR-061
   remains `Accepted` and unmodified; its Category A is not broadened; every Category B
   deferral and every §2.7/§2.8 advisory-only limit stays binding (see §7).
9. **Amend, reopen, or reinterpret ADR-002, ADR-023, ADR-028, ADR-039, ADR-056, or
   ADR-060.**
10. **Enable any enforcement, gating, veto, blocking, capability-resolver wiring, or
    trade-affecting behavior.** Staging the contract package makes the *advisory*
    `IntegrationHealth` types importable at Space runtime and nothing more.
11. **Introduce any new dependency, provider, endpoint, credential, network call, or
    secret**, or modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level
    `ledger/`, `sentinel_engine/`, or `config.py`'s contents.
12. **Deploy anything, or trigger a deploy, by itself.**

---

## 4. ADR-002 Compliance (per the ADR-028 §4 / ADR-039 §4 / ADR-056 §6 / ADR-060 §6 precedent for this file)

1. **Named file, named lines only:** exactly
   `.github/workflows/deploy_trading_intelligence.yml`; exactly the one
   `shutil.copytree` block in §2.1 (plus its one-line comment), inserted at the one
   named location. No other file, no other line.
2. **Isolated branch/worktree** for implementation, not directly on `main`.
3. **Verification before merge:** see §6. In summary — YAML parse; a local replication of
   the staged tree that includes `applications/platform/integrations/` and proves
   `from applications.trading_intelligence.bootstrap import build_trading_intelligence_app;
   build_trading_intelligence_app()` succeeds against *only* the staged files; the
   `applications/trading_intelligence/` and `applications/platform/` test suites re-run as
   a regression check (no Python source changes, so both already pass);
   `deploy_wealth_intelligence.yml` confirmed byte-identical.
4. **Rollback plan, stated before implementation:** §5.
5. **Trading-trigger-path criterion:** not applicable — this file deploys a Gradio Space
   with no relationship to `bot/`'s CLI or watchdog-mediated trading-trigger paths (the
   same finding ADR-028 §4.5 / ADR-039 §4.5 / ADR-056 §6.5 / ADR-060 §6.5 already made
   for this exact file).

---

## 5. Rollback Plan (stated before implementation, per ADR-002 item 5)

1. **Revert the workflow change.** Delete the single `shutil.copytree` block (and its
   one-line comment) added by §2.1, restoring
   `.github/workflows/deploy_trading_intelligence.yml` to its post-ADR-060 content. The
   change is purely additive; reverting is a clean delete.
2. **No other action is required.** No Space secret, no data, no schema, no persistent
   state, and no `applications/` code is touched by this ADR, so rollback carries no
   data-level or credential-level risk. The staged Space tree simply no longer contains
   `applications/platform/integrations/` on the next deploy.
3. **Note explicitly:** reverting *this* change after it has fixed the live outage would
   restore the `ModuleNotFoundError` crash. This rollback plan describes undoing this
   specific change if it independently causes a *new* problem — not a recommended
   response to the current outage.

---

## 6. Verification / Acceptance Criteria

**Pre-merge (implementation branch):**

- `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy_trading_intelligence.yml'))"` parses without error.
- Replicate the staged tree in a temp directory using the same copy pattern the workflow
  uses — `applications/__init__.py`, `applications/platform/__init__.py`,
  `applications/platform/{identity, navigation, registry, workspaces, entitlements,
  integrations}`, `applications/trading_intelligence/`, `sentinel_engine/`, `config.py`,
  and `main.py`→`app.py` — then, with `sys.path` pointed at that directory alone, confirm
  `python -c "from applications.trading_intelligence.bootstrap import
  build_trading_intelligence_app; build_trading_intelligence_app()"` succeeds. This proves
  the fix closes the actual gap, not assumed from the §1.2 trace alone.
- `applications/trading_intelligence/` (incl. `ui/tests/`) and `applications/platform/`
  test suites pass (regression check; this ADR changes no Python source).
- `git diff` for the implementation commit is exactly the one `shutil.copytree` block
  (plus its comment) in the one file; `deploy_wealth_intelligence.yml` and every other
  workflow are byte-identical.

**Post-deploy (live Space):**

- `HfApi().get_space_runtime("ksri77/aara-trading-intelligence").stage` transitions to
  `RUNNING` (from `RUNTIME_ERROR`).
- `HfApi().list_repo_files("ksri77/aara-trading-intelligence", repo_type="space")` lists
  `applications/platform/integrations/__init__.py`, `.../health.py`,
  `.../classification.py`, `.../capability.py`.
- The Space run log no longer contains
  `ModuleNotFoundError: No module named 'applications.platform.integrations'`; the app
  reaches Gradio startup and serves the six-screen UI.
- The `deploy_trading_intelligence.yml` run triggered by the implementation commit
  concludes `success`, and its Space commit adds exactly the four `integrations/` files.

**Acceptance of this ADR** (per ADR-058 D2/D4) is separate from all of the above: it is
the ratification that the §2.1 authorization is granted on the terms stated in §2–§5. It
does not perform the edit, run the verification, or deploy.

---

## 7. Relationship to ADR-061 (and Amendment 1)

- **This ADR is the governance item ADR-061 Amendment 1 named.** Amendment 1's "Not
  authorized by this amendment" list defers "Staging `applications/platform/integrations/`
  into the deployed Space" to "a separate future ADR-002 governance item (see §9)". This
  ADR is that item, on the narrowest possible terms — one `shutil.copytree`, one file.
- **No numbered section of ADR-061 is altered.** §2.1–§2.9, §3 Category A items 1–7, §3
  Category B items 1–10, §4–§10, §8 Acceptance Criteria, the `## Acceptance` block, and
  Amendment 1 itself are all unchanged. ADR-061's `Status:` remains `Accepted`.
- **ADR-061 Category A is not broadened.** ADR-061 authorized *building* the platform
  `IntegrationHealth` contract and *importing* it from the Trading Intelligence adapters
  and screens (items 1, 3, 4). This ADR only makes that already-authorized, already-built,
  already-imported package *present in the deployed artifact*. It adds no new contract, no
  new consumer, and no new coupling.
- **Every ADR-061 Category B deferral and every advisory-only limit stays binding.**
  ADR-061 §2.7/§2.8 (advisory / UI-only; enforcement deferred to its own ADR), §3
  Category B items 1–10, and Amendment 1's own "Not authorized" list all remain in force.
  Staging the contract module enables none of the deferred behaviors — the module is
  inert value types and a pure classification helper.
- **Structural precedent is ADR-039.** ADR-039 fixed the identical incident class (live
  Space `RUNTIME_ERROR` from a `bootstrap.py` module-scope import of an unstaged
  `applications/platform/` subpackage) by adding `shutil.copytree` calls to this same
  file, and was itself the named follow-on to ADR-028 §3's reserved packages. This ADR is
  the same move for the one package ADR-061 introduced, and follows ADR-039's §2/§3/§4/§5
  structure. ADR-039's four packages and this ADR's one are disjoint; together with
  `identity/` (ADR-028) they leave only `shell/` unstaged, which nothing imports.
- **ADR-056 and ADR-060 are adjacent but independent.** They each added a *different*
  additive change to the same workflow file (`config.py` staging; `env:` lines +
  `add_space_secret`). This ADR does not touch, extend, or depend on either; it also does
  not, by itself, make real data appear (that additionally needs the bot publishing a
  current `trades.db`, `config.py` importable at runtime per ADR-056, and the synced
  `HF_TOKEN` per ADR-060 — all outside this ADR's scope).

---

## 8. Security Implications

- **No credential, secret, token, endpoint, or network client is added.**
  `applications/platform/integrations/` is inert contract code: frozen dataclasses
  (`IntegrationHealth`, `ReadResult`), an `Enum` (`IntegrationStatus`), an advisory
  `CapabilityResolver`, and a pure exception/HTTP-status classification helper. Its
  `classification.py` imports `socket` only for `isinstance` type checks and never opens
  a connection.
- **No credential-leakage vector is introduced.** Per ADR-061 §2.9 (which this package
  already implements) the classification helper "never copies an exception message or a
  config value into `detail`" — it records only exception class names and caller-supplied
  setting *names*. Staging the module changes nothing about that.
- **No new attack surface.** The four files are already public in the repository and
  already imported by the Space's application code; this change only makes the deployed
  artifact match the source tree it was built from. No new dependency is pulled into the
  Space image.
- **No enforcement or control-plane change.** The module cannot block, gate, veto, or
  alter any operation (ADR-061 §2.7/§2.8); it is consumed only by advisory UI rendering.
- **Corrective, not expansive.** The Space is currently *down*; this exception restores
  a previously-working deployment to a working state. It does not enable any capability
  the Space did not have before commit `922bbe9`.

---

## 9. Consequences

**Positive:**

- Closes the exact gap causing the live outage with the narrowest possible mechanism:
  one additive `shutil.copytree`, one file — the same pattern and precedent ADR-028 §2.2
  and ADR-039 §2 already established for this file.
- Requires zero change to any already-Accepted ADR's authorization, including ADR-061's:
  the defect is in what gets deployed, not in what was authorized to be built. ADR-061
  Amendment 1 anticipated and explicitly routed this to a dedicated ADR — this is it.
- Leaves only `shell/` unstaged among `applications/platform/` subpackages, and only
  because nothing imports it — the narrowest slice that closes the incident.

**Negative / Open risk:**

- **The Space stays down until this ADR is accepted and its one-line workflow change is
  implemented, verified per §6, and pushed.** This ADR is the fix *proposal*; per
  ADR-002's `.github/workflows/*.yml` protection, no one may push the workflow edit
  without the acceptance step this document is awaiting.
- **Real trades.db / Alpaca data is not restored by this ADR alone.** Booting the Space
  is necessary but not sufficient; the data path additionally depends on ADR-056
  (`config.py` staged — done), ADR-060 (`HF_TOKEN` synced — done), the bot publishing a
  current `trades.db` (verified healthy), and `config.py`'s `dotenv` import resolving at
  Space runtime (a separate, still-open question outside this ADR — see §3 item 5).
- **This is the third incident traceable to this file's staging scope lagging a
  `bootstrap.py` import change** (after ADR-028 §2.2's original `identity/` finding and
  ADR-039's four-package finding). ADR-039 §6 already observed that
  `deploy_trading_intelligence.yml`'s staging scope should be checked as part of any
  future ADR that adds a cross-package `bootstrap.py` import; formalizing that check is
  not authorized or attempted here, but the pattern is now well-established enough to
  warrant a follow-on.

---

## Acceptance

*(Completed only when this ADR is landed under ADR-058 D2. Left as a stub while
`Proposed`. Per ADR-058 D2, authority follows from this document being tracked on the
authoritative default branch with `Status: Accepted`, landed under the applicable
write / merge controls; an `Accepted By` string, if later added, is metadata only and is
not the source of authority. Per ADR-058 D4, authoring or committing this file with
`Status: Proposed` records a proposal only.)*

Acceptance ratifies the single `shutil.copytree` block in §2.1 (plus its one-line
ADR-referencing comment) in the one named file
`.github/workflows/deploy_trading_intelligence.yml`, at the one named location, on the
terms in §2–§5. Per §3, §5, and §6 it authorizes no other workflow change, no
`requirements*.txt` change, no Python-source change, no `config.py`-staging or
Space-secret change, no broader `applications/platform/` staging, and no change to
ADR-002, ADR-023, ADR-028, ADR-039, ADR-056, ADR-060, or ADR-061 (including Amendment 1).
It creates no credential, performs no deployment, and triggers no deploy. Implementing
the workflow edit (on an isolated branch, with the §6 verification) and any resulting
Space state remain subsequent operational actions this acceptance does not itself
perform.

**Status:** Accepted
