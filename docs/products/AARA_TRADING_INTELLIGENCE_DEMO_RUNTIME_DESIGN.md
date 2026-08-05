# AARA Trading Intelligence — Demo Runtime Design

**Status:** Design proposal. Documentation only. No code or runtime file was
created. `applications/trading_intelligence/`, `sentinel_engine/`, `ledger/`,
`bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`
untouched, confirmed via `git status` before and after. No ADR was resolved.

**Authority:** `AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md`,
`AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md`,
`AARA_PLATFORM_SHELL_ARCHITECTURE.md`, `ADR-005-platform-shell-model.md`.
Since the last of these was written, one real milestone landed —
`applications/platform/tests/test_trading_intelligence_product_integration.py`
— proving the real `TRADING_INTELLIGENCE_PRODUCT` composes through
`NavigationBuilder` for the first time. This document accounts for that;
it does not treat the Composition Design document's gap list as still fully
open where it no longer is.

---

## 1. Demo Objective

Show a complete AARA Trading Intelligence experience using controlled
test/demo data — but "complete experience" needs one precise qualifier,
consistent with every prior document in this series, not softened here: no
rendering layer exists or is chosen
(`AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 5),
so "complete" means **a complete, provably-correct data/service chain** —
from a demo identity through to a fully populated `DecisionCenterScreen` —
verifiable by running tests, not a browser-visible demo. This document
defines the smallest such chain that uses zero production infrastructure.

## 2. Current Available Components

Each verified real and tested, current status re-checked directly for this
document (258 tests passing across `applications/platform/tests` (99),
`applications/trading_intelligence/tests` (49),
`applications/trading_intelligence/ui/tests` (28), `sentinel_engine/tests`
(82)):

- **`TRADING_INTELLIGENCE_PRODUCT`** (`applications/trading_intelligence/product.py`)
  — the real product descriptor. As of the most recent milestone, proven
  registrable with `ProductRegistry` **and** discoverable through
  `NavigationBuilder` using the real descriptor, not a synthetic stand-in.
- **Workspace registration** — `Workspace`/`WorkspaceRegistry`
  (`applications/platform/workspaces/`). A Decision Center `Workspace` value
  (`workspace_id="trading_intelligence.decision_center"`) now exists as a
  proven, reusable test pattern (`test_trading_intelligence_product_integration.py`,
  `test_navigation_builder.py`) — still not committed as production data
  anywhere, only ever constructed inside tests.
- **`NavigationBuilder`** (`applications/platform/navigation/navigation_builder.py`)
  — real, composes `AuthenticationProvider` + `EntitlementChecker` +
  `ProductRegistry` + `WorkspaceRegistry` into a `NavigationModel`. Now
  specifically proven, for the first time, to surface a Decision Center
  `NavigationItem` for an entitled user of the real
  `TRADING_INTELLIGENCE_PRODUCT`.
- **`DecisionQueryService`** (`applications/trading_intelligence/services/decision_query_service.py`)
  — real, wraps a `DecisionSource`.
- **`DecisionCenterController`** (`applications/trading_intelligence/ui/decision_center/controller.py`)
  — real, fully service-backed, structurally proven to never depend on
  `mock_data.py`.
- **`DecisionCenterScreen`** (`applications/trading_intelligence/ui/decision_center/screen.py`)
  — real, framework-independent, the terminal output of this whole chain.

## 3. Demo Runtime Flow

```
Demo User
    |
    v
Fake AuthenticationProvider
    |
    v
Fake EntitlementChecker
    |
    v
Platform Navigation
    |
    v
Decision Center
    |
    v
Mock/Synthetic Decision Data
```

Annotated against real, tested code — two proven segments with one
precisely-located gap between them, not a fully connected pipeline:

- **Demo User → Fake AuthenticationProvider → Fake EntitlementChecker →
  Platform Navigation — proven, real.** `User(user_id, display_name)`
  returned by a `_FakeAuthenticationProvider`; entitlement checked per
  product by a `_FakeEntitlementChecker`; `NavigationBuilder.build()`
  composes both into a `NavigationModel` containing a Decision Center
  `NavigationItem` for an entitled demo user. This entire segment is exactly
  what `test_trading_intelligence_product_integration.py` now verifies,
  using the real `TRADING_INTELLIGENCE_PRODUCT`.
- **Platform Navigation → Decision Center — the one missing link, stated
  precisely, not glossed over.** Nothing in this codebase takes a resolved
  `NavigationItem` (or the `NavigationModel` it came from) and uses it to
  decide to construct a `DecisionCenterController`. This is the same gap
  `AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 2
  already identified, and it remains true even after the most recent
  milestone — that milestone proved navigation *discovers* Decision Center;
  it did not connect that discovery to actually building the controller.
  Section 5 names closing this specific gap as the next milestone.
- **Decision Center → Mock/Synthetic Decision Data — proven, real, two
  interchangeable options.** `mock_data.build_mock_screen()`
  (`applications/trading_intelligence/ui/decision_center/mock_data.py`),
  standalone, no service wiring needed; or the full real-service chain fed
  by test data —
  `InMemoryProjectionRepository` (`applications/trading_intelligence/tests/fakes.py`)
  → `SentinelProjectionDecisionSource` → `DecisionQueryService` →
  `DecisionCenterController.load_screen()`. Both already exist; neither is
  proposed or built by this document.

## 4. Explicit Exclusions

Each excluded for a specific, already-established reason — not a blanket
"out of scope":

- **Real authentication** — `AuthenticationProvider` has zero concrete
  implementations; `ADR-003` explicitly gates implementation until product
  boundaries stabilize.
- **Real ledger** — `ProjectionRepository` has zero concrete
  implementations; `ADR-004` defers the backend choice until Phase 1A's
  validation window completes. Not resolved by this document.
- **Broker connection** — not proposed anywhere in this document series;
  `bot/execution/` is protected and has no relationship to this demo scope.
- **Database** — no `database/`-backed component appears anywhere in
  Section 3's flow; `database/` remains protected and untouched.
- **Dashboard migration** — `dashboard/` remains protected, real, and
  entirely separate from this chain; this demo has no dependency on it and
  proposes no migration toward or away from it.
- **Evidence/Risk/Governance implementation** — established at length
  across three prior documents in this series: no `sentinel_engine` risk
  contract exists at all; Evidence's cardinality question is unresolved;
  `Approval`'s shape doesn't match the real governance audit data. None
  belongs in the smallest truthful demo.

## 5. Smallest Future Implementation Milestone

**Close the one gap Section 3 names precisely:** a new test (not production
code — matching the discipline the most recent milestone already
established) that takes a `NavigationModel` produced by `NavigationBuilder`
for an entitled demo user, locates its Decision Center `NavigationItem`,
and uses that as the basis for constructing a `DecisionCenterController`
backed by demo data (`mock_data.build_mock_screen()` is the simplest
choice — no additional fakes needed) — then asserts the resulting
`DecisionCenterScreen` is correct.

This would complete, for the first time, an unbroken, tested chain from
"a demo user is entitled to Trading Intelligence" all the way to "a correct
Decision Center screen exists" — the full Section 3 flow, proven end-to-end
in one test, with zero new production classes (same constraint the previous
milestone honored: no application coordinator, no new abstraction — just a
test proving the pieces that already exist compose correctly one link
further than they do today).

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No runtime file was created. No ADR was resolved. This document
only reads and cites existing code and prior documentation.
