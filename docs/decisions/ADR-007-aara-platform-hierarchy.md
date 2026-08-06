# ADR-007: AARA Platform Hierarchy

**Status:** Proposed
**Date:** 2026-08-06

## Context

- The repository was renamed from `ai-trading-bot` to `aara` (GitHub remote
  updated 2026-08-06; see `docs/BACKUP_RECOVERY.md`, `scripts/dashboard.py`).
- Previous branding (`brand/BRAND_MANIFEST.yaml`, `brand/VERSION_LOCK.yaml`,
  frozen 2026-07-30) used **Sentinel Intelligence** / **Sentinel Intelligence
  Platform** as the top-level platform identity — the brand and the
  intelligence engine were the same name, with nothing above it.
- The new direction introduces **AARA Systems** as a parent company/platform
  brand, with Sentinel Intelligence Engine continuing underneath it as the
  intelligence layer rather than the top-level identity. This is consistent
  with `CLAUDE_AARA_MIGRATION.md`, `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`
  (2026-08-04), and `docs/platform/AARA_PLATFORM_ARCHITECTURE.md`, which
  already describe a **nested** company → engine → products structure —
  Sentinel Intelligence Engine as the sole layer between the company brand
  and every product, not a sibling of the products — but this ADR is the
  first decision record to state that hierarchy explicitly and durably.
- This ADR does not itself rename, move, or modify any code, brand file, or
  documentation — it establishes the naming/ownership model those follow-up
  changes must conform to.

## Reconciliation

This ADR clarifies and formalizes the company → engine → products hierarchy
described in `AARA_ARCHITECTURE_AUTHORITY.md` and `AARA_PLATFORM_ARCHITECTURE.md`.
It does not replace ADR-001 Sentinel Engine Structure or alter Sentinel
Intelligence Engine ownership boundaries.

## Decision

**AARA Systems** is the parent platform/company brand and owns multiple
intelligence products. **Sentinel Intelligence Engine** remains an
independent, reusable intelligence platform — it is not renamed, absorbed,
or demoted into being "just" a component of any single AARA product.

### Naming hierarchy

```
AARA Systems
    |
    └── Sentinel Intelligence Engine
           |
           ├── AARA Wealth Intelligence
           ├── AARA Trading Intelligence
           ├── AARA CFO Intelligence (future)
           ├── AARA Tax Intelligence (future)
           └── AARA Estate Intelligence (future)
```

Sentinel Intelligence Engine is the **sole** layer between "AARA Systems"
and every product — products are children of the engine, not siblings of
it, and not direct children of "AARA Systems."

## Boundaries

- **Sentinel Intelligence Engine** = the technology/intelligence layer:
  reasoning, evidence, memory, governance, and the other capabilities
  described in `docs/platform/SENTINEL_ENGINE_*.md` and implemented in
  `sentinel_engine/`. It has no product-specific UI or customer-facing
  identity of its own.
- **AARA products** (`AARA [Product] Intelligence` — AARA Wealth
  Intelligence, AARA Trading Intelligence, and any future AARA product) =
  the customer-facing experiences built on top of, and nested under, the
  engine. Product branding, UI, and go-to-market identity live at this
  layer, not at the engine layer, and not directly under "AARA Systems."

## Why Sentinel Intelligence Engine is preserved as its own identity

- **Reusable across products** — the engine is designed to serve more than
  one AARA product (Wealth Intelligence and Trading Intelligence today,
  per `docs/decisions/ADR-003-aara-identity-and-product-access.md`'s
  multi-product model; more may follow). Folding its identity into one
  product's branding would misrepresent that shared role.
- **Technical moat** — the engine's reasoning/evidence/governance
  capabilities are the differentiated, hard-to-replicate asset. Naming it as
  a first-class platform component, distinct from any single product,
  keeps that value visible rather than hidden inside one product's branding.
- **Governance identity** — the engine's governance/audit model (decision
  logging, evidence trails, approval flows) is meaningful independent of
  which product surfaces it. A shared, stable name lets governance
  documentation, audits, and controls reference one consistent identity
  across products.
- **Avoids coupling the intelligence engine to one product** — if the engine
  were renamed to match a single product (e.g. "AARA Trading Intelligence
  Engine"), extending it to a second product later would require either a
  confusing name or a disruptive rename. Keeping Sentinel Intelligence Engine
  as an independent identity avoids that coupling from the start.

## Migration rules

- **Do not rename the `sentinel_engine` package.** Its module path, import
  name, and internal identity stay as-is.
- **Do not delete existing Sentinel references.** Historical references
  (ADRs, changelogs, dated planning docs) and current architecture docs
  under `docs/platform/SENTINEL_ENGINE_*.md` remain valid and are not to be
  scrubbed or replaced wholesale.
- **Update product-facing branding separately**, as its own scoped change —
  not as part of this ADR, and not by editing frozen `brand/` files without
  the authorization their own freeze header requires. This ADR establishes
  the target hierarchy; it does not authorize any specific rename or brand
  file edit.

## Consequences

- Future platform products must be created as children of **Sentinel
  Intelligence Engine** in the hierarchy above — not as direct siblings of
  the engine, and not as direct children of "AARA Systems." Future work
  introducing or renaming an AARA product must follow this nesting and must
  not rename or restructure `sentinel_engine/` to do so.
- `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s document-roles table and
  `docs/platform/AARA_PLATFORM_ARCHITECTURE.md`'s hierarchy diagrams already
  describe this nested structure and do not require changes as a result of
  this ADR — this ADR formalizes their existing model as a decision record,
  it does not diverge from it.
- This ADR does not modify `bot/`, `dashboard/`, `scheduler/`,
  `.github/workflows/`, `database/`, or `ledger/` — all remain governed by
  `docs/decisions/ADR-002-bot-runtime-protection.md`, unchanged by this
  decision.
- This ADR does not modify `sentinel_engine/`'s structure — that remains
  governed by `docs/decisions/ADR-001-sentinel-engine-structure.md`.
- This ADR does not implement or change the product access/roles model —
  that is `docs/decisions/ADR-003-aara-identity-and-product-access.md`'s
  concern, unaffected by this decision.
- Updating `brand/BRAND_MANIFEST.yaml`, `VERSION_LOCK.yaml`, and related
  frozen brand files to reflect this hierarchy is a separate, future action
  requiring the authorization their freeze status already requires — not
  performed by this ADR.
