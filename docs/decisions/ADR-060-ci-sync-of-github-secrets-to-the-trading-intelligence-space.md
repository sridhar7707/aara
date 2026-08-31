# ADR-060 — Narrow ADR-002 Exception: CI Syncs Named GitHub Repository Secrets to the Trading Intelligence Space

**Status:** Accepted
**Date Proposed:** 2026-08-31
**Date Accepted:** 2026-08-31
**Decision Type:** Narrow ADR-002 Exception (deployment workflow code only) — credential-propagation mechanism, no new credential
**Related ADRs:** ADR-002 (`.github/workflows/*.yml` frozen — this ADR carves
one further narrow exception into `deploy_trading_intelligence.yml`), ADR-023
(created that workflow; its Forbidden list names secret-adding as out of its
scope — this ADR is the separate authorization), ADR-028 §2.2 / ADR-039 §2 /
ADR-056 §2.1 (the established one-ADR-per-line template for this exact file),
ADR-054 (admits the Alpaca **paper** read-only provider whose credentials this
syncs), ADR-055 §5.5 (explicitly left "creating or setting an `HF_TOKEN` secret
for a private dataset" out of its own scope, pending a separate authorization —
this ADR is that authorization), ADR-056 §2.1 (stages `config.py`; a hard
prerequisite for the synced values to be readable at Space runtime), ADR-056
§2.2 (provisioned the same two Alpaca Space secrets as a *manual* maintainer
step — this ADR supersedes that mechanism with CI sync, not the credentials
themselves), ADR-058 (D2/D4 ratification model this ADR follows)

---

## 1. Context

Real data in the deployed Trading Intelligence Space
(`ksri77/aara-trading-intelligence`) currently requires three credentials to be
present in the **Space runtime environment**:

- `ALPACA_KEY`, `ALPACA_SECRET` — the **paper** keys ADR-054's three read-only
  Alpaca adapters (`alpaca_paper_source.py`, `alpaca_paper_orders_source.py`,
  `alpaca_news_source.py`) read via `from config import ...`.
- `HF_TOKEN` — required by `adapters/trades_db_snapshot.py::fetch_trades_db_snapshot`
  (ADR-055) because the published dataset `ksri77/ai-trading-bot-db` is
  **private** (`bot/monitor/sync_db.py` creates it `private=True`).

All three already exist as **GitHub repository secrets** (created 2026-06-09;
`gh secret list` confirms `ALPACA_KEY`, `ALPACA_SECRET`, `HF_TOKEN`). They are
used today by `trade.yml` and others (`ALPACA_*`) and by this workflow's own
`env:` block (`HF_TOKEN`).

GitHub Actions secrets and HuggingFace Space secrets are **two isolated stores
on two platforms**. A GitHub secret is injected only into a running workflow
job; the long-lived Space container on HuggingFace infrastructure has no channel
to read it. So each of the three credentials otherwise has to be maintained in
**two places** — edited in GitHub *and* re-entered by hand in the Space's
Settings → Variables and secrets. ADR-056 §2.2 accepted that manual duplication
for the two Alpaca keys; this ADR removes it.

`.github/workflows/deploy_trading_intelligence.yml` (created under ADR-023,
extended under ADR-028 §2.2, ADR-039, and ADR-056 §2.1) currently passes only
`HF_TOKEN` and `HF_SPACE_ID_TRADING_INTELLIGENCE` into its deploy job's `env:`
block, and performs no Space-secret writes. Per ADR-023's Forbidden list
(*"adding any GitHub secret"*, and by extension any credential-provisioning
step) and the ADR-017/018/028/039/056 precedent that **each new line in this
file needs its own explicit exception**, the change below is not covered by any
existing authorization. This ADR is that authorization.

**This ADR creates no credential.** All three GitHub repository secrets already
exist. The change propagates existing values from one runtime (GitHub Actions)
to a second (the Space), so the operator maintains them in exactly one place.

---

## 2. Decision

A **narrow exception to ADR-002's `.github/workflows/*.yml` freeze**, scoped to
exactly `.github/workflows/deploy_trading_intelligence.yml`, comprising two
additive changes and nothing else.

### 2.1 `env:` block — three added entries (existing repo secrets)

Add to the `Deploy to HuggingFace Spaces` step's `env:` block:

```yaml
          ALPACA_KEY:    ${{ secrets.ALPACA_KEY }}
          ALPACA_SECRET: ${{ secrets.ALPACA_SECRET }}
```

(`HF_TOKEN` is already present and is reused as-is.) No other `env:` entry is
added, removed, or changed. `ALPACA_BASE_URL` is **not** added — see §4.

### 2.2 Space-secret sync — one added block

After the existing `api.upload_folder(...)` / `api.upload_file(...)` calls, add
one block that pushes the three named values into the Trading Intelligence
Space's own encrypted secret store via `HfApi.add_space_secret`:

```python
          for _name in ("ALPACA_KEY", "ALPACA_SECRET", "HF_TOKEN"):
              _val = os.environ.get(_name, "")
              if _val:
                  api.add_space_secret(repo_id=space_id, key=_name, value=_val)
                  print(f"synced Space secret: {_name}")
              else:
                  print(f"::warning::{_name} not set in CI env — Space secret not synced; "
                        f"that section stays on its unavailable fallback")
```

- **Idempotent.** `add_space_secret` overwrites; running it on every deploy just
  re-mirrors the current GitHub value. No versioning, no history kept by this
  code.
- **Fail-soft.** A missing GitHub secret produces a `::warning::` and the deploy
  still succeeds; the corresponding Space section stays on its existing
  honest-unavailable fallback. It does **not** hard-fail the deploy.
- **No value is ever written to the staged tree, printed in full, committed, or
  logged.** `add_space_secret` transmits over HTTPS to HF's write-only secret
  API; GitHub masks the values in Actions logs; HF does not render them back.

### 2.3 Credential character is unchanged

- `ALPACA_KEY` / `ALPACA_SECRET` are **paper** keys — the same ones the bot's
  paper runtime and `trade.yml` use. ADR-054's mandatory two-layer paper
  enforcement in the adapters (hard-coded `paper=True` **and** the `"paper"`
  base-URL substring check) is untouched and must not be read as relaxed.
- `HF_TOKEN` is a read token for a private **dataset**; the snapshot adapter is
  consumer-only (ADR-055 §2.3 — no `upload_file` / `create_commit` / write of
  any kind).

### 2.4 Relationship to ADR-056 §2.2

ADR-056 §2.2 scoped the two Alpaca Space secrets as a manual maintainer step.
This ADR **replaces that mechanism** with CI sync for the same two keys and
adds `HF_TOKEN`. It does not change ADR-056 §2.1 (the `config.py` staging line),
which remains a hard prerequisite: without `config.py` on the Space,
`from config import ...` still raises `ImportError` and the synced env vars are
never read.

---

## 3. Why CI sync (not the alternatives)

1. **CI sync of existing GitHub secrets (selected).** One source of truth
   (GitHub); the Space copy is a re-pushed mirror the operator never edits;
   reuses `add_space_secret`, a first-class `huggingface_hub` API; no secret
   value in the repo or the staged tree.
2. **Keep the manual two-place model (ADR-056 §2.2).** Rejected: duplicated
   maintenance, drift risk on rotation, and it does not cover `HF_TOKEN` at all.
3. **Bake the values into a file in the staged upload.** Rejected outright: puts
   plaintext credentials into the Space's own git repo and history.
4. **Have the Space fetch the credentials at boot from a remote store.**
   Rejected: needs a *bootstrap* credential to authenticate that fetch —
   chicken-and-egg, strictly more secrets, not fewer.
5. **Rely on HuggingFace's auto-injected Space `HF_TOKEN`.** Partially viable
   for `HF_TOKEN` only (and worth confirming on the Space independently), but
   does nothing for the two Alpaca keys, so a single mechanism covering all
   three is preferred.

---

## 4. Explicit Non-Authorization

This ADR authorizes exactly §2.1 (two `env:` lines) and §2.2 (one sync block) in
one named file. It does **not**:

1. Authorize any other line change in `deploy_trading_intelligence.yml` —
   triggers, `paths`, Python/Gradio pins, existing staging steps/comments, the
   README metadata block, `main.py`→`app.py`, `requirements` copy, or the
   ADR-056 §2.1 `config.py` line are all unchanged.
2. Authorize any change to `deploy_wealth_intelligence.yml`, `deploy_ui.yml`,
   `ci.yml`, `keepalive.yml`, `premarket.yml`, `retrain.yml`,
   `secret-scan.yml`, `trade.yml`, `watchdog.yml`, or any other workflow.
3. Authorize adding, introducing, or syncing `ALPACA_BASE_URL` (or any
   base-URL override) as a GitHub or Space secret or `env:` entry. `config.py`'s
   `https://paper-api.alpaca.markets` default stands (ADR-056 §2.2 / §4.4
   reasoning: a settable base URL is a way to point at a non-paper endpoint).
4. **Create** any GitHub secret. All three named secrets already exist; this ADR
   only reads them.
5. Authorize any **live** Alpaca credential, endpoint, or account, or weaken
   ADR-054's paper-only adapter enforcement.
6. Authorize `fetch_trades_db_snapshot` or any adapter to write to, upload to,
   or commit against any HuggingFace repo (ADR-055 §2.3 / §5.1 stand).
7. Authorize any change to `applications/trading_intelligence/` adapter,
   `bootstrap.py`, `config.py`, or any other Python source.
8. Authorize any order submission, cancellation, replacement, position close, or
   funds movement — none is reachable from the code these credentials serve.
9. Modify `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`,
   `sentinel_engine/`, or `config.py`'s contents.
10. Deploy anything, or trigger a deploy, by itself.
11. Amend, reopen, or reinterpret ADR-002, ADR-023, ADR-028, ADR-039, ADR-054,
    or ADR-055 beyond answering the §5.5 question ADR-055 explicitly left open.
12. Address Decision Center's empty state (ADR-004) or Performance & Learning
    (no adapter wired) — out of scope.

---

## 5. Rollback Plan (stated before implementation, per ADR-002 item 5)

Precise, three parts, in order:

1. **Revert the workflow change.** Delete the two `env:` lines (§2.1) and the
   one sync block (§2.2) from `deploy_trading_intelligence.yml`, restoring it to
   its post-ADR-056 content. Additive change; reverting is a clean delete.
2. **Delete the Space secrets.** Remove `ALPACA_KEY`, `ALPACA_SECRET`, and
   `HF_TOKEN` from the Trading Intelligence Space's Settings → Variables and
   secrets. The GitHub repository secrets of the same name are **left
   untouched** — they predate this ADR and are used elsewhere.
3. **Fallback re-engages automatically.** With (1) and (2) done, the next deploy
   ships no sync; `config.py`'s `os.getenv(NAME, "")` returns `""`; the Alpaca
   adapters and `fetch_trades_db_snapshot` return `None`; every affected section
   returns to its honest-unavailable fallback — the exact state before this ADR.
   No `applications/` code change is needed; the fallback is already shipped.

No `bot/`, `database/`, `ledger/`, or persistent trading state is touched, so
rollback carries no data-level risk.

---

## 6. ADR-002 Compliance (per the ADR-028 §4 / ADR-039 §4 / ADR-056 §6 precedent for this file)

1. **Named file, named lines:** exactly
   `.github/workflows/deploy_trading_intelligence.yml`; exactly two added `env:`
   lines and one added post-upload sync block. No other file, no other line.
2. **Isolated branch/worktree** for implementation, not directly on `main`.
3. **Verification before merge:**
   - `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy_trading_intelligence.yml'))"`.
   - Replicate the staged tree locally with `config.py` present and confirm
     `python -c "from applications.trading_intelligence.bootstrap import build_trading_intelligence_app; build_trading_intelligence_app()"` still builds (this ADR changes no Python source).
   - Run `applications/trading_intelligence/tests/` and
     `applications/trading_intelligence/ui/tests/` (both green; no source change expected).
   - Confirm `deploy_wealth_intelligence.yml` byte-identical before and after.
   - Post-deploy: confirm the Space boots and serves its Gradio UI, and that
     `ALPACA_KEY` / `ALPACA_SECRET` / `HF_TOKEN` now appear in the Space's
     Settings → Variables and secrets.
4. **Rollback plan:** §5 above, written before implementation.
5. **Trading-trigger-path criterion:** not applicable — this file deploys a
   Gradio Space with no relationship to `bot/`'s CLI or watchdog
   trading-trigger paths (same finding as ADR-028 §4.5 / ADR-039 §4.5 /
   ADR-056 §6.5 for this file).

---

## 7. Relationship to Existing ADRs

- **ADR-002:** preserved. One further narrow, named, additive exception to the
  workflow freeze, with a stated rollback — the ADR-028/039/056 pattern.
- **ADR-054:** unaffected. Paper-only adapter enforcement is untouched; this ADR
  only delivers the paper keys ADR-054's adapters already expect.
- **ADR-055:** §5.5 explicitly declined to authorize an `HF_TOKEN` secret "for a
  private dataset" and pointed to a separate future authorization. This ADR is
  that authorization, on the narrowest terms (sync of the existing repo secret,
  consumer-only use per ADR-055 §2.3). No other part of ADR-055 is reopened.
- **ADR-056:** §2.1 (`config.py` staging) stands and is a prerequisite. §2.2's
  manual-provisioning mechanism for the two Alpaca Space secrets is superseded
  by §2.2 here (CI sync); the credentials and their paper character are
  unchanged.
- **ADR-058:** this ADR follows the D2/D4 model — it is a **proposal** until it
  is tracked on the authoritative default branch with `Status: Accepted`, landed
  under the applicable write/merge controls. The `Accepted By` line is metadata,
  not the source of authority.

---

## 8. Consequences

**Positive:**

- One source of truth for all three credentials (GitHub); the Space copy is a
  CI-managed mirror the operator never hand-edits, eliminating rotation drift.
- Closes ADR-055 §5.5's open `HF_TOKEN` question on minimal terms.
- Replaces ADR-056 §2.2's manual step; no plaintext secret in the repo, the
  staged tree, or any log.

**Negative / Limitation:**

- The Space's secret store now holds a copy of each value; rotating a key still
  means the Space is briefly stale until the next deploy runs (mitigated:
  `workflow_dispatch` re-run, or any push to the deployed paths, re-syncs).
- Adds an external dependency on `HfApi.add_space_secret` remaining stable in
  `huggingface_hub>=0.20.0` (it is a long-standing public method).
- Does not itself make data appear — the bot must still be publishing a current
  `trades.db` to `ksri77/ai-trading-bot-db`, and `config.py` must be staged
  (ADR-056 §2.1).

---

## Acceptance

*(Completed only when this ADR is landed under ADR-058 D2. Left as a stub while
`Proposed`. Per ADR-058 D2, authority follows from this document being tracked
on the authoritative default branch with `Status: Accepted`, landed under the
applicable write / merge controls; the `Accepted By` string is metadata only.)*

**Status:** Accepted
**Date Accepted:** 2026-08-31
**Accepted By:** Architecture Owner

Prerequisite satisfied: ADR-054, ADR-055, and ADR-056 are Accepted (see
§Related ADRs and §7); ADR-056 §2.1's `config.py` staging remains a required
prerequisite for the synced values to be read at Space runtime. Acceptance
ratifies §2.1 (the two `env:` lines) and §2.2 (the one post-upload
`add_space_secret` sync block) in the single named file
`.github/workflows/deploy_trading_intelligence.yml`, and answers the `HF_TOKEN`
question ADR-055 §5.5 left open, on the narrow terms stated in §2.3 and §7. Per
§4, §5, and §6 it authorizes no other workflow change, creates no credential,
performs no secret sync itself, and triggers no deployment. Implementing the
workflow edit (on an isolated branch, with the §6.3 verification) and any
resulting Space-secret state remain subsequent operational actions.
