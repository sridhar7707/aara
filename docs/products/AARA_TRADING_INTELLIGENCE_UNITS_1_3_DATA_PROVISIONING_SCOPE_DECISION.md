# AARA Trading Intelligence — Units 1–3 Production Data Provisioning Scope Decision

**Status:** Scope decision. Documentation only. No code, UI, workflow, database,
or secret change is created by this document. `applications/trading_intelligence/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/` untouched — confirmed via `git status` before
and after.

**Date:** 2026-08-27

**Authority (referenced, not replaced):**
`docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` (frozen screen-level
spec), `docs/products/AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`,
`docs/products/AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md`,
`docs/platform/TRADING_INTELLIGENCE_BOUNDARY.md`, ADR-002. This document does not
re-decide anything those establish — it records one product-scope clarification
they do not yet state explicitly.

---

## 1. Purpose

The Morning Brief and Portfolio Intelligence screens (this product's Units 1–3)
are already product-approved in
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` §2 and §4. The *required
information* for these screens — portfolio snapshot, market regime, candidate
screening summary, overnight holdings news, positions, capital, and allocation —
is named there; the shipped app surfaces the paper-account data via
explicitly-labeled "Alpaca Paper Account" / "Recent Orders" sub-sections the
frozen spec does not itself enumerate — which is precisely the gap this decision
records. What that document does not yet state in one place is the
**data-source and provisioning decision** behind them: that Trading Intelligence
is permitted to **read the user's existing Alpaca *paper* account** to populate
those already-approved sections. This document records that decision.

This is a data-source/provisioning decision, **not a new UI feature**. No screen,
section, layout, or interaction defined in
`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` is added, removed, or changed by
this document.

## 2. Decision

Trading Intelligence **may read, on a read-only basis**, the following from the
user's existing Alpaca **paper** account, solely to populate the already-approved
Units 1–3 sections:

- Alpaca paper **account** information (equity, cash, buying power, portfolio
  value).
- Alpaca paper **positions** (open positions and their market values / unrealised
  P&L).
- Alpaca paper **recent orders** (open orders and recently-closed order history,
  as broker-side observation).
- Alpaca **news / market-data** headlines relevant to current holdings, consumed
  as **evidence/source material only** for Morning Brief's Overnight Holdings
  News section.

"Read the user's Alpaca paper account state" is the entire scope. It is
explicitly distinct from, and does not grant, any capability to **execute
trades**.

## 3. Explicit Limits

This decision does **not** authorize, and Units 1–3 must never introduce:

- Autonomous order submission of any kind.
- Order cancellation.
- Order replacement or modification.
- Position closing initiated by Trading Intelligence.
- Funds transfer, withdrawal, deposit, or any account-money-movement capability.
- Any connection to a **live** (non-paper) Alpaca account or endpoint.
- Any use of the read data as a trading authority — the news/market-data channel
  in particular is evidence only; it never scores, ranks, or infers an action.

Trading Intelligence remains, after this decision, a **read-only observer** of
the paper account. It gains no execution authority. The product's non-goals in
`AARA_TRADING_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` §3 (no autonomous trading,
no auto-execution, no replacing human approval) are unchanged and reinforced
here.

## 4. Relationship to the Frozen UI Specification

`AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md` remains the authoritative
screen-level spec and is not edited by this document. Its §2 "Current data
source (real, verified)" column currently cites `dashboard/components/*` for
these sections; the shipped Trading Intelligence application instead reads its
own read-only adapters (`dashboard/` is ADR-002-protected and not importable
from this product). Reconciling that documentation drift — a dated addendum to
the UI specification and to `TRADING_INTELLIGENCE_BOUNDARY.md` §5–§7 recording
the actual adapter-based data paths — is a **separate follow-up**, noted here but
not performed by this scope decision.

## 5. Fallback Behavior Is Unchanged

When a data source is unavailable (no credentials, no network, no
`trades.db`, API error), the existing UI behavior stands: each section shows its
current honest "unavailable" / illustrative-fallback message. That fallback
remains a valid, intended state — not a defect — exactly as it is today. This
decision only establishes that, **when the approved source is available**, the
section is expected to render the real read-only data rather than the fallback.

## 6. What This Decision Does Not Cover

- **How** the Alpaca dependency is architecturally admitted into the product —
  that is an architecture decision (see ADR-054).
- **How** the deployed Space obtains `trades.db` — see ADR-055.
- **How** deployment is changed to make the above real (workflow staging,
  credential provisioning) — see ADR-056.
- Any Sentinel-ledger ownership question (ADR-004) — untouched; none of Units
  1–3 read the hash-chained Trust Ledger event tables.

Implementation of any of the above must not begin until ADR-054, ADR-055, and
ADR-056 have been reviewed and Accepted.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, or
`database/` was created or modified. No UI component, workflow, requirements
file, or secret was created or modified. No ADR was resolved. No ownership
boundary was changed. This document only reads and cites existing code and prior
documentation.
