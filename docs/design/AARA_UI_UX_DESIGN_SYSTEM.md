# AARA UI/UX Design System

**Status:** Design architecture — Phase 3 (Product Development Planning), item 3.
Documentation only. No `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`,
`database/`, `ledger/`, or `sentinel_engine/` file was touched. No React,
components, or implementation code was created — every concrete detail below is
either read directly from real existing files or explicitly marked as
undecided.

**Authoritative inputs:** `AARA_PLATFORM_USER_EXPERIENCE.md`,
`AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`,
`AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`, `AARA_ARCHITECTURE_AUTHORITY.md`,
`ADR-003`.

**Verification note, same discipline as the navigation document:** where this
document references concrete visual tokens or components, they're read from real
files (`dashboard/design_system.py`, `sentinel/frontend/components/`) — read-only,
neither modified. Where no such grounding exists, that's stated, not invented.

---

## 1. Design Principles

- **Evidence over emotion** — every number or recommendation traces to a
  `sentinel_engine.evidence.Evidence` record or its future equivalent; nothing is
  presented as true because it "feels right." Matches `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s
  own framing: "I know why Aara said this" as a named success metric.
- **Explainability first** — matches `SENTINEL_ENGINE_BOUNDARY_AND_API_CONTRACTS.md`'s
  `explain(context)` capability (reinterpreted as conceptual per ADR-001, not a
  package layout, but the principle survives): every surfaced insight should be
  pairable with a plain-language explanation, not just a score.
- **Governance visible** — matches `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md`'s
  Navigation Principle of the same name: decision audit and evidence trails are
  first-class UI, not hidden behind an admin-only afterthought.
- **Human-controlled intelligence** — matches `CLAUDE_AARA_MIGRATION.md`'s
  `recommend(insights)` principle: "Recommendations are not automatic actions...
  the product maintains user control." No UI pattern in this document implies
  autonomous action without a human decision point.

## 2. Platform Shell Design

Extends `AARA_PLATFORM_USER_EXPERIENCE.md` Sections 1-2 with visual/layout intent
(still no implementation):

- **Global navigation** — persistent chrome: product switcher + account/identity
  menu concept. Carries no product-specific styling of its own; visually neutral
  so it doesn't bias toward whichever workspace is active.
- **Product switcher** — entitlement-filtered per ADR-003's role table (unchanged
  from the navigation document). Visually: a small, consistently-placed control,
  not a full page — switching products should feel like changing a tab, not
  leaving the platform.
- **Workspace layout** — each workspace (Trading Intelligence, Wealth
  Intelligence, Platform Admin) owns its internal layout; the shell only provides
  the frame around it.
- **User role visibility** — unchanged from ADR-003/navigation document: what
  renders in the shell is a function of role, not a client-side preference.

## 3. Component System

Grounded in real, existing component files — `sentinel/frontend/components/`
already has a governance-oriented component set that maps closely to what was
requested:

| Requested component | Existing grounding | Notes |
|---|---|---|
| Cards | `sentinel/frontend/components/decision_card.py` | General card pattern for a single decision |
| Intelligence panels | No direct file match | Not grounded in an existing component — flagged, not invented in detail |
| Decision cards | `decision_card.py` | Direct match |
| Risk indicators | `risk_governor_badge.py` | Direct match — badge pattern, not a full panel |
| Evidence panels | `evidence_card.py` | Direct match |
| Charts | `dashboard/design_system.py`'s `PLOTLY_LAYOUT` (current Trading Intelligence charting theme) | Only concrete charting reference found; no Sentinel-side chart component exists |
| Status indicators | `governance_badge.py`, `health_score.py` | Two existing patterns, not one |

**Additional existing components not requested but present:**
`approval_controls.py`, `audit_fingerprint.py`, `chain_timeline.py`,
`model_agreement.py` — relevant to Admin/Governance UX (Section 6), not itemized
in the table above since they weren't asked for by name.

This document does not specify these components' props, markup, or styling — only
that they exist and roughly what purpose their names imply, which is as far as
"component system" can go without writing code.

## 4. Trading Intelligence UX Patterns

Per `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` Section 3: Morning Brief, Decision
Center, Portfolio, Performance, Settings map to real `dashboard/components/`
files today. UX pattern intent, not new screens:

- **Morning Brief** — a single-glance daily summary pattern; today's
  `brief.py`/`executive_summary.py` already establish this shape.
- **Decision Center** — a list-to-detail pattern (list of decisions → decision
  card → evidence/risk detail), consistent with `decision_card.py`/`evidence_card.py`'s
  existing shape in `sentinel/frontend/`, even though today's `dashboard/`
  implements it separately via `decision.py`/`decision_bar.py`/`thesis.py`.
- **Portfolio** — holdings/positions/allocation, using Chart components (Section 3).
- **Performance** — trailing-period and attribution views, using the same chart
  theme as Portfolio for visual consistency.
- **"Investor Evolution"** — not designed here; per the navigation document's
  Open Decisions, no current capability backs this label.

## 5. Wealth Intelligence UX Patterns

Per `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`'s own stated tone —
explicitly **not** the same register as Trading Intelligence's action-colored,
BUY/SELL-driven surface:

- **Calm, not urgent** — `AARA_WEALTH_INTELLIGENCE_PRODUCT_ARCHITECTURE.md`
  Section 7 names "Market Noise Filtering: what can be ignored" as a Monthly
  Wealth Review capability; the UX pattern should reflect that at every screen,
  not just in the monthly review.
- **Discovery-oriented** — Wealth X-Ray's own framing ("Discover what you
  actually own") suggests a reveal/insight pattern (summary → drill-in →
  explanation), similar in shape to Decision Center's list-to-detail pattern but
  without action buttons (Wealth Intelligence has no BUY/SELL — see ADR-003 scope
  and the product architecture's explicit "NOT a trading application").
- **Memory-oriented** — Wealth Chronicle and Wealth Memory (Section 8, Capability
  4) imply a timeline/history pattern, conceptually similar to
  `chain_timeline.py`'s existing pattern in `sentinel/frontend/components/`, though
  no such component currently exists for Wealth Intelligence specifically.

## 6. Admin/Governance UX Patterns

Grounded directly in `sentinel/frontend/components/`'s real files:

- **Decision Audit** — built from `decision_card.py`, `evidence_card.py`,
  `chain_timeline.py`, `audit_fingerprint.py` — a chronological, evidence-linked
  trail, matching `AARA_PRODUCT_NAVIGATION_ARCHITECTURE.md` Section 5's strongest
  grounding.
- **Approvals** — `approval_controls.py` exists but wasn't named in the
  navigation document's requested list; flagging its existence here since it's
  directly relevant to governance UX.
- **Governance status** — `governance_badge.py`, `health_score.py`,
  `risk_governor_badge.py`, `model_agreement.py` — status-indicator-style
  components, not full pages.
- **"AI Mission Control," "Data Pipeline," "System Administration"** — per the
  navigation document's Open Decisions, none of these have existing grounding.
  Not designed further here.

## 7. Typography, Spacing, Layout, Accessibility Principles

**Current, real reference point** (`dashboard/design_system.py`, "TradeGenius
Design System v1.0" — read-only, unmodified):
- Dark theme: `BG #0f1115`, `SURFACE #171a21`, `BORDER #2d3445`
- Exactly 3 text levels (`TEXT1`/`TEXT2`/`TEXT3`) — deliberately capped, per that
  file's own comment
- Exactly 4 font sizes (`FONT_HERO` 36px down to `FONT_LABEL` 11px) — also
  deliberately capped
- Action colors: BUY green, SELL red, TRIM amber, HOLD blue, WATCH purple
- Spacing tokens: `CARD_PADDING` 20px, `CARD_RADIUS` 12px, `SECTION_GAP` 16px

**This document does not decide** whether AARA's platform-wide system adopts
these values, extends them, or diverges — see Open Decisions. It's presented
here as the one concrete, real reference point that exists today, not as a
platform-wide commitment.

**Accessibility** — no accessibility standard is established by this document.
A separate, gitignored draft (`docs/architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md`,
per `AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy: not the project's controlled
source of truth) references WCAG AA and a 320px responsive minimum for the
Sentinel product specifically — noted as an existing reference point to
reconcile with later, not adopted as binding by this document.

## 8. Screen-Level Wireframe Descriptions (Text Only)

No pixel dimensions, no markup — layout intent in prose only:

- **Wealth Home** — top: wealth summary figure (single hero number, matching
  `FONT_HERO`'s current role for portfolio value). Middle: 2-3 status
  cards (structure, health, recent discovery). Bottom: entry points to Wealth
  X-Ray and Wealth Chronicle.
- **Decision Center (Trading Intelligence)** — left or top: scannable list of
  recent decisions (decision cards). Selecting one opens a detail view combining
  an evidence panel and a risk indicator, side by side or stacked depending on
  viewport.
- **Platform Admin — Decision Audit** — a chronological trail (chain timeline)
  with each entry expandable into its evidence card and audit fingerprint; no
  action buttons (governance views are read-only observation, not control
  surfaces, consistent with Design Principle "Human-controlled intelligence"
  living in the product workspaces, not the audit view).

## 9. Current Dashboard Reality vs. Future AARA Experience

**Current (real, protected under ADR-002, unmodified by this document):**
- `dashboard/` — one Gradio app, ~30 components, no product switcher, no shell,
  "TradeGenius Design System v1.0" branding/tokens (Section 7), tightly coupled
  to `bot/` (33 files, per `BOT_DEPENDENCY_MAP.md`).
- `sentinel/frontend/` — a separate, existing component/workspace set
  (governance-oriented), not connected to `dashboard/` today, not connected to
  any shell.

**Future (target, not built, not scheduled):**
- One AARA Platform Shell, entitlement-gated per ADR-003, hosting Trading
  Intelligence (today's `dashboard/` capability, reachable through the shell
  rather than standalone), Wealth Intelligence (net-new), and Platform
  Admin/Governance (today's `sentinel/frontend/` capability, reachable through
  the shell).
- A single design language spanning all three, still undecided (Open Decisions).

## 10. Open Design Decisions

Listed, not solved:

- Does AARA's platform-wide design system adopt `dashboard/design_system.py`'s
  existing tokens (colors, type scale, spacing), extend them, or replace them
  entirely? No decision made here.
- How does Wealth Intelligence's stated "calm, not urgent" tone coexist visually
  with Trading Intelligence's action-colored (BUY green/SELL red) surface in one
  shared component system, without either diluting the other's intent?
- Does the gitignored `docs/architecture/SENTINEL_DESIGN_SYSTEM_FINAL.md` (v2.0,
  frozen per that document's own status, but not authoritative per
  `AARA_ARCHITECTURE_AUTHORITY.md`'s hierarchy) get formally reconciled into this
  platform-wide system, superseded by it, or left as a Sentinel-product-specific
  reference? Not resolved here.
- What accessibility standard is actually adopted platform-wide — the
  Sentinel-specific WCAG AA / 320px reference noted in Section 7, something else,
  or not yet decided?
- "Intelligence panels" (Section 3) has no existing component grounding at all —
  is this a new concept to design, or a mislabeling of an existing pattern
  (decision cards, evidence panels)?
- Where do the four "no existing grounding" Admin/Governance items from the
  navigation document (AI Mission Control, Data Pipeline, System Administration,
  and by extension any visual design for them) get resolved — this document
  inherits that open question rather than closing it.

---

## Explicitly Out of Scope

No React, component code, CSS, design tokens file, or Figma-equivalent asset was
created. No `dashboard/design_system.py` value was changed. This document
describes a target design architecture only.
