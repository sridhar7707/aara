# ADR-063: Add `python-dotenv` to the Trading Intelligence Space Requirements

**Status:** Accepted
**Date Proposed:** 2026-08-31
**Date Accepted:** 2026-08-31
**Decision Type:** Narrow deployment-dependency addition — ADR-062 §3 item 5 follow-through (Incident Remediation)
**Related ADRs:** ADR-062 §3 item 5 / §9 (explicitly deferred *this exact question* — "Whether
`config.py`'s `from dotenv import load_dotenv` needs an explicit Space dependency is a separate
matter, outside this ADR, and is not resolved here" — this ADR is that separate matter), ADR-056
§2.1 (stages `config.py` verbatim into the Space; this ADR makes that staged file importable at
Space runtime and does not otherwise touch it), ADR-060 (synced `ALPACA_KEY` / `ALPACA_SECRET` /
`HF_TOKEN` as Space secrets — the runtime evidence below shows those secrets are present but
unreadable because `config.py` fails to import first), ADR-023 (created
`deploy_trading_intelligence.yml`; `requirements_trading_intelligence.txt` is a deploy input it
copies to the Space as `requirements.txt`), ADR-002 (`requirements_trading_intelligence.txt` is a
top-level file, **not** an ADR-002-protected path — the protected set is `bot/`, `dashboard/`,
`scheduler/`, `.github/workflows/`, `database/`, top-level `ledger/`; same finding ADR-056 §3 made
for `config.py`), ADR-058 (D2/D4 ratification model this ADR follows)

---

## 1. Context / Problem

**Verified after the ADR-062 deploy.** Commit `b454b4d` fixed the Space's
`ModuleNotFoundError: applications.platform.integrations` crash-loop; the Space is now `RUNNING`.
But every data section on Morning Brief, Portfolio Intelligence, and Risk Intelligence renders a
non-`HEALTHY` `IntegrationHealth` fallback — no real trades.db or Alpaca data reaches the UI.

### 1.1 Root cause (read-only deduction, this session)

1. CI **did** sync `ALPACA_KEY` and `ALPACA_SECRET` into the Space secret store — the deploy run
   log for `b454b4d` prints `synced Space secret: ALPACA_KEY` / `synced Space secret: ALPACA_SECRET`
   (ADR-060 §2.2).
2. Yet the live Space renders the Alpaca-backed sections as **`NOT_CONFIGURED`**.
3. `applications/trading_intelligence/adapters/alpaca_paper_source.py:71-84` reads credentials as
   `try: from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL / except ImportError:
   ALPACA_KEY = ""` (…). The adapter reports `NOT_CONFIGURED` "ALPACA_KEY / ALPACA_SECRET not set"
   **only when that import raised** and the empty-string fallback was taken.
4. `config.py`'s only fallible import is its second line, `from dotenv import load_dotenv`
   (module scope, unguarded).
5. `requirements_trading_intelligence.txt` does not list `python-dotenv`, and nothing pulls it in
   transitively — `gradio==4.44.1`, `gradio-client==1.3.0`, plain `uvicorn`, `starlette`,
   `spaces`, `alpaca-py`, `supabase-auth`, `pillow`, `tzdata` were each checked against PyPI
   metadata; none declare it.
6. Therefore, on the Space, `config.py` raises `ModuleNotFoundError: No module named 'dotenv'` at
   import. Every `from config import …` across the product (the three read-only Alpaca adapters
   **and** `adapters/trades_db_snapshot.py::fetch_trades_db_snapshot`, which guards with
   `except Exception:` and returns `NOT_CONFIGURED` "config module is not importable") falls back
   to empty / failed values. The five `legacy_*_source.py` adapters then get no snapshot `db_path`
   and report "trades.db is not present". Every symptom is accounted for.

Independently confirmed: the private dataset `ksri77/ai-trading-bot-db` holds a current
`trades.db` (refreshed 2026-08-31), and the exact `hf_hub_download(...)` call the snapshot adapter
makes **succeeds in ~4 s with a valid token** — so the only thing standing between the deployed
Space and real data is `config.py` importing.

### 1.2 Why this was left open

ADR-062 deliberately did not resolve it — §3 item 5: *"Whether `config.py`'s
`from dotenv import load_dotenv` needs an explicit Space dependency is a separate matter, outside
this ADR."* §9 lists it as an open risk. This ADR is that separate matter, now that runtime
evidence requires it.

---

## 2. Decision

Add **exactly one** dependency line — `python-dotenv` — to
`requirements_trading_intelligence.txt`, with an accompanying explanatory comment in the file's
existing style (mirroring the `alpaca-py` / `tzdata` / `spaces` entries already there).

`python-dotenv` is a pure-Python, zero-dependency package. `config.py` calls `load_dotenv()`
once at import; in the Space there is no `.env` file, so `load_dotenv()` is a no-op and every
value continues to come from `os.getenv(...)` reading the Space's own secret store. Installing the
package only makes the `import` succeed.

### 2.1 Scope

This ADR authorizes exactly the one `python-dotenv` line (plus its comment) in exactly
`requirements_trading_intelligence.txt`. `requirements_trading_intelligence.txt` is in this
workflow's trigger `paths`, so merging this change to `main` triggers a Space rebuild — that is
the intended delivery mechanism and is not a separate authorization.

---

## 3. Explicit Non-Authorization

This ADR does **not**:

1. Authorize any other change to `requirements_trading_intelligence.txt` — no version bump to any
   existing pin, no other new package.
2. Authorize any change to `config.py` (contents or staging), `deploy_trading_intelligence.yml`,
   any adapter, `bootstrap.py`, or any other Python source. `config.py`'s unguarded
   `from dotenv import load_dotenv` is left exactly as it is; this ADR satisfies it rather than
   rewriting it.
3. Authorize any change to `requirements.txt`, `requirements_space.txt`,
   `requirements_wealth_intelligence.txt`, or any other requirements file.
4. Authorize any change to `deploy_wealth_intelligence.yml`, `deploy_ui.yml`, or any other
   workflow, or to `bot/`, `dashboard/`, `scheduler/`, `database/`, top-level `ledger/`, or
   `sentinel_engine/`.
5. Introduce any new credential, endpoint, network call, or Space secret; enable any Alpaca
   live-trading path (ADR-054's two-layer paper enforcement is untouched); or change any
   `IntegrationHealth` / enforcement behavior (ADR-061 §2.7 / §2.8 stand).
6. Amend, reopen, or reinterpret ADR-002, ADR-023, ADR-054, ADR-055, ADR-056, ADR-060, ADR-061,
   or ADR-062.
7. Deploy anything by itself, beyond the rebuild the trigger `paths` cause on merge.

---

## 4. Rollback Plan (stated before implementation, per ADR-002 item 5)

1. **Revert the one line.** Delete `python-dotenv` (and its comment) from
   `requirements_trading_intelligence.txt`, restoring it to its post-ADR-062 content. Purely
   additive; reverting is a clean one-line delete.
2. **No other action.** No secret, data, schema, or `applications/` code is touched. The next
   deploy ships without the package; `config.py` returns to raising `ModuleNotFoundError` at
   import and every section returns to its honest-unavailable fallback — the exact state before
   this ADR.
3. **Note:** reverting after it has restored real data would re-break `config.py`. This plan
   describes undoing the change if it independently causes a *new* problem, not a recommended
   response to the current state.

---

## 5. Verification / Acceptance Criteria

**Pre-merge (implementation branch):**

- `python -m pytest applications/trading_intelligence` passes (regression check; this ADR changes
  no Python source).
- `git diff` for the implementation commit is exactly the one `python-dotenv` line (plus its
  comment) in the one file, plus this ADR.
- `git diff --check` clean.

**Post-deploy (live Space):**

- The `deploy_trading_intelligence.yml` run triggered by the merge concludes `success` and the
  Space build installs `python-dotenv`.
- The Space run log contains no `ModuleNotFoundError: No module named 'dotenv'`.
- Morning Brief (Portfolio Snapshot, Market Mood / Regime, Candidate Screening Summary),
  Portfolio Intelligence, and Risk Intelligence render **real data** — a `HEALTHY`
  `IntegrationHealth` on the trades.db-snapshot-backed and Alpaca-backed sections — instead of the
  current `NOT_CONFIGURED` / "provider could not be reached" fallbacks.
- "Overnight Holdings News" remains on its "no wired data source" state — that section is
  deliberately unwired and is out of scope here.

Per ADR-058 D2, acceptance follows from this document being tracked on `main` with
`Status: Accepted`; it does not itself perform the edit or the deploy.

---

## 6. Consequences

**Positive:**

- Closes the last gap between the (now `RUNNING`) Space and real data, with the narrowest
  mechanism: one dependency line, one file — the same pattern by which `alpaca-py` was added to
  this file to let the Alpaca sections show real data.
- Resolves the question ADR-062 §3 item 5 / §9 explicitly left open, now that runtime evidence
  requires it.
- `config.py` becomes importable in the Space for **all** its consumers at once (the three Alpaca
  adapters and the trades.db snapshot), not one section at a time.

**Negative / Open risk:**

- Adds one more package to the Space image. `python-dotenv` is pure-Python with no dependencies,
  so build-time and resolver risk is minimal.
- `config.py`'s unguarded `from dotenv import load_dotenv` remains a latent fragility for any
  future minimal-image consumer of `config.py`. Hardening that import (`try/except ImportError`)
  is a reasonable future change but is shared-file work with a wider blast radius and is not taken
  here.
- Does not, by itself, guarantee real data if a *different* failure (e.g. Alpaca egress, an
  expired key) also exists — but the §5 post-deploy check will surface that.

---

## Acceptance

*(Per ADR-058 D2, authority follows from this document being tracked on the authoritative default
branch with `Status: Accepted`, landed under the applicable write / merge controls; an
`Accepted By` string is metadata only. Per ADR-058 D4, committing this file with `Status: Proposed`
would record a proposal only.)*

Acceptance ratifies the single `python-dotenv` line (plus its comment) in
`requirements_trading_intelligence.txt`, on the terms in §2–§4. Per §3 it authorizes no other
requirements change, no `config.py` change, no workflow change, no Python-source change, and no
change to ADR-002, ADR-023, ADR-054, ADR-055, ADR-056, ADR-060, ADR-061, or ADR-062. It creates no
credential and performs no deployment beyond the rebuild the workflow trigger `paths` cause on
merge.

**Status:** Accepted
