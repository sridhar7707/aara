# AARA Product Navigation Architecture

**Status:** Design concept — Phase 3 (Product Development Planning), item 2 of 4.
Documentation only. No application code, `dashboard/`, `bot/`, `scheduler/`,
workflow, `database/`, or `ledger/` file was touched. No authentication,
authorization, schema, or migration was created.

**Authoritative inputs:** `AARA_PLATFORM_USER_EXPERIENCE.md`,
`AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`, `AARA_ARCHITECTURE_AUTHORITY.md`,
ADR-001 through ADR-004.

**Verification note:** where this document's requested nav labels didn't match
anything found in the actual codebase, that's flagged explicitly rather than
presented as if it already existed — checked directly against
`dashboard/components/*.py` and `sentinel/frontend/workspaces/*.py` (both
read-only lookups; neither was modified).

---

## 1. AARA Platform Shell

Extends `AARA_PLATFORM_USER_EXPERIENCE.md`'s shell/switcher/workspace model with
a navigation-specific view:

- **Global navigation** — persistent across all workspaces: platform shell chrome
  (product switcher, account/identity menu concept), never workspace-specific
  logic. No business logic lives at this layer, matching the same separation
  principle already established for `sentinel_engine` vs. products.
- **Product switcher concept** — unchanged from `AARA_PLATFORM_USER_EXPERIENCE.md`
  Section 2: renders only the workspaces a user's role entitles them to.
- **Workspace model** — each product (Trading Intelligence, Wealth Intelligence,
  Platform Admin) owns its own internal navigation once entered; the shell does
  not reach into a workspace's internal structure.
- **Future multi-product expansion** — unchanged from `AARA_PLATFORM_USER_EXPERIENCE.md`
  Section 7: new products add a switcher entry and a workspace, without needing
  shell changes beyond that.

## 2. User Role Visibility Model (Design Only)

| Role | Sees | Entitlement concept |
|---|---|---|
| Trading Intelligence User | Trading Intelligence workspace only | Single-product entitlement |
| Wealth Intelligence User | Wealth Intelligence workspace only | Single-product entitlement |
| AARA Super User / Platform Administrator | Trading Intelligence + Wealth Intelligence + Platform Admin | Multi-product + admin entitlement |

Matches ADR-003's three roles exactly — no new role invented here.

**Explicitly deferred until ADR-003 implementation** (not designed further by this
document):
- How an entitlement is actually checked at request/render time.
- Where entitlement data is stored (ADR-003: "No database schema yet").
- What happens when a user has zero entitlements (empty state — not designed).
- Any session/token/login mechanism (ADR-003: "No authentication implementation
  yet").

## 3. Trading Intelligence Navigation

Mapped against the real current file list in `dashboard/components/` (read-only
lookup, not modified):

| Requested nav item | Current `dashboard/` capability | Future AARA shell integration |
|---|---|---|
| Morning Brief | `brief.py`, `executive_summary.py` | Same content, reachable inside the Trading Intelligence workspace instead of standalone |
| Decision Center | `decision.py`, `decision_bar.py`, `decision_quality.py`, `pending_approvals.py`, `thesis.py`, `counterfactual.py`, `loss_explanation.py` | Same, consolidated under one nav entry rather than separate tabs |
| Portfolio | `portfolio.py`, `capital.py`, `rebalance.py` | Same |
| Performance | `attribution.py`, `weekly_summary.py`, `trust_scorecard.py`, `signal_history.py`, `timeline.py`, `recommendation_history.py` | Same |
| Investor Evolution | **No current equivalent found.** Closest adjacent concept is `timeline.py`, but nothing in `dashboard/components/` matches this label or an "evolution" framing. | Not designed here — see Open Decisions |
| Settings | `settings.py` | Same |

**Not itemized above** but present in `dashboard/components/` today:
`overview.py`, `risk.py`, `signals.py`, `market_mood.py`, `news.py`,
`symbol_detail.py`, `simulator.py`, `ai_panel.py`, `models.py`,
`phase2_preview.py`, `_ledger_analytics.py`. These likely distribute across the
categories above (e.g. `risk.py`/`signals.py` under Portfolio or their own
category) but this document does not force a precise 1:1 mapping for all ~30
components — doing so would be inventing categorization not requested.

**Current vs. future, stated plainly:** every item in the "current" column is
*today's* `dashboard/` — protected under ADR-002, unmodified by this document.
The "future" column describes reaching the same functionality through the AARA
shell later; it is not a redesign commitment or a timeline.

## 4. Wealth Intelligence Navigation

Mapped against `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s actual defined
screens (Section 10 of that document):

| Requested nav item | Existing product architecture equivalent |
|---|---|
| Overview | Wealth Home |
| Allocation | Wealth Map (visualizes accounts/asset groups/relationships) — `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s Wealth X-Ray capability also covers asset-allocation analysis |
| Goals | **No existing screen.** `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md` mentions "long-term wealth goals" as a user-profile attribute and "financial milestones" under Wealth Memory, but has no dedicated Goals screen or capability. Flagging rather than inventing one — see Open Decisions. |
| Insights | Insight Detail |
| Financial intelligence capabilities | Wealth X-Ray, Monthly Wealth Review (the two analytical capabilities in the existing product architecture) |

No new Wealth Intelligence feature is introduced by this table — where a
requested label has no existing counterpart (Goals), that's stated, not
papered over.

## 5. Admin / Governance Navigation

Checked against `sentinel/frontend/workspaces/` (real files, read-only lookup):
`chain_of_custody.py`, `decision_history.py`, `decision_quality.py`,
`decision_review.py`, `evidence_explorer.py`, `governance_review.py`,
`governance_status.py`, `portfolio_health.py`, `tax_intelligence.py`.

| Requested nav item | Grounding found |
|---|---|
| Decision Audit | Matches `decision_history.py`, `decision_review.py`, `decision_quality.py`, `chain_of_custody.py`, `evidence_explorer.py`, `governance_review.py`, `governance_status.py` — strong existing basis |
| AI Mission Control | **No existing workspace or component found under this name**, in `sentinel/frontend/` or `dashboard/components/`. |
| Model Analytics | No exact match; `dashboard/components/models.py` exists in the *current Trading Intelligence* surface (not `sentinel/frontend/`), so this may already exist under a different product, not as an admin capability. |
| Data Pipeline | **No existing workspace or component found under this name.** |
| Experiments/Feature Flags | No exact match; `dashboard/components/phase2_preview.py` exists in the current Trading Intelligence surface and may be adjacent, but it's not an admin/governance file today. |
| System Administration | **No existing workspace or component found under this name.** |

**Also present in `sentinel/frontend/workspaces/` but not in the requested
list:** `portfolio_health.py`, `tax_intelligence.py` — existing workspaces this
document doesn't have a requested nav label to attach to.

This section deliberately does not invent replacements for the unbacked items —
see Open Decisions.

## 6. Navigation Principles

- **Product isolation** — no product's navigation reaches into another's
  internals. Trading Intelligence and Wealth Intelligence workspaces don't
  reference each other's components.
- **Entitlement-based visibility** — what a user sees is a function of role
  (Section 2), not a client-side toggle; the actual enforcement mechanism is
  ADR-003's deferred implementation, not designed here.
- **Governance-first design** — Admin/Governance navigation surfaces decision
  audit and evidence trails as first-class, not as an afterthought bolted onto a
  product workspace, matching `ARCHITECTURE_FREEZE_STATUS.md`'s frozen "Decision
  as Primary Domain Object" principle.
- **No direct coupling between products** — matches `TRADING_INTELLIGENCE_BOUNDARY.md`'s
  Migration Principles: any shared capability flows through `sentinel_engine`, never
  product-to-product directly.
- **Multi-product scalability** — the shell/switcher/workspace pattern (Section 1)
  is the same pattern for 2 products or 6; adding a product should not require
  redesigning navigation for the existing ones.

## 7. Current State vs. Future State

**Current:**

```
dashboard/ (protected, ADR-002)
 |
 +-- ~30 components, single Gradio app, no product switcher, no shell
 |
sentinel/frontend/workspaces/ (separate, existing)
 |
 +-- chain_of_custody, decision_history, decision_quality, decision_review,
     evidence_explorer, governance_review, governance_status, portfolio_health,
     tax_intelligence
```

Two separate, unconnected surfaces today — no shell unifies them.

**Future (target, not built, not scheduled):**

```
AARA Platform Shell
 |
 +-- Product Switcher (entitlement-filtered, per ADR-003 once implemented)
 |
 +-- Trading Intelligence Workspace
 +-- Wealth Intelligence Workspace
 +-- Platform Admin / Governance Workspace
```

## 8. Open Decisions

Listed, not solved:

- Does "Investor Evolution" correspond to a planned Trading Intelligence
  capability, or is it a new feature that hasn't been scoped yet?
- Does "Goals" get added as a new Wealth Intelligence screen (a product-architecture
  change, out of scope for this document), or was it shorthand for existing
  Wealth Memory/user-profile concepts?
- Do "AI Mission Control," "Data Pipeline," and "System Administration" get built
  as new admin capabilities, or were they intended as relabelings of existing
  `sentinel/frontend/workspaces/` files (e.g. `governance_status` →
  "System Administration")?
- How does entitlement checking actually gate workspace visibility at runtime —
  no mechanism exists (ADR-003 deferred)?
- Where does the AARA Platform Shell actually get built — a new codebase, or an
  evolution of `dashboard/` in place? This is exactly the question Phase 3 item 4
  (Dashboard Separation Strategy Refinement) hasn't started yet.
- Should "Performance" remain a distinct Trading Intelligence nav item, or fold
  into Portfolio, given no single existing component is named exactly
  "performance"?

## Feature Discovery vs. Feature Invention Principle

- Navigation entries must be grounded in existing product requirements,
  architecture documents, or implemented capabilities.
- Missing screens/components (e.g. "Investor Evolution," "Goals," "AI Mission
  Control," "Data Pipeline," "System Administration" above) are recorded as
  product decisions, not created by assumption.
- Future capabilities require product requirements before appearing as
  committed navigation items.
- This prevents the platform from accumulating speculative UI surfaces.
