# AARA Workspace Entry Architecture

**Status:** Design proposal. Documentation only. No code was created or
modified. `applications/trading_intelligence/`, `applications/platform/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/` untouched, confirmed via `git status`
before and after. No ADR was resolved.

**Authority:** `AARA_TRADING_INTELLIGENCE_DEMO_RUNTIME_DESIGN.md`,
`AARA_NAVIGATION_MODEL_ARCHITECTURE.md`, `AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md`,
`ADR-005-platform-shell-model.md`. Verified directly: no `resolver`,
`WorkspaceEntry`, `EntryPoint`, or equivalent concept exists anywhere in
`applications/` today — this document starts from a clean slate, not from
partially-built code.

---

## 1. Current State

Two real, independently-tested facts, and the gap between them, stated
exactly as the authority documents already found:

- **`NavigationBuilder` creates `NavigationItem`.**
  (`applications/platform/navigation/navigation_builder.py`) — composes
  `AuthenticationProvider` + `EntitlementChecker` + `ProductRegistry` +
  `WorkspaceRegistry` into a `NavigationModel` whose `items` are
  `NavigationItem`s (`product_id`, `workspace_id`, `label`, `order`,
  `visibility`). Proven, for Trading Intelligence specifically, by
  `applications/platform/tests/test_trading_intelligence_product_integration.py`.
- **`DecisionCenterController` creates `DecisionCenterScreen`.**
  (`applications/trading_intelligence/ui/decision_center/controller.py`) —
  `load_screen()` produces a `DecisionCenterScreen` from a
  `DecisionQueryService`. Fully real and tested, unrelated to navigation in
  any way.
- **No object currently connects the two.** Verified directly: nothing in
  this codebase takes a `NavigationItem` (or its `workspace_id`) and uses it
  to decide to construct a `DecisionCenterController`. Every existing test
  that produces a `DecisionCenterScreen` constructs the controller directly,
  with no reference to navigation at all. This is the same gap
  `AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 2
  and `AARA_TRADING_INTELLIGENCE_DEMO_RUNTIME_DESIGN.md` Section 3 both
  already named — restated here as this document's specific subject, not a
  new discovery.

## 2. Workspace Entry Flow

**Target, not current behavior:**

```
User selects NavigationItem
        |
        v
Workspace entry resolver
        |
        v
Trading Intelligence Decision Center
        |
        v
DecisionCenterController
```

Mapped against Section 1's real pieces:

- **User selects `NavigationItem`** — the output of `NavigationBuilder`,
  already real; "selects" is a UI interaction that has no implementation
  anywhere (no rendering layer exists at all, per
  `AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 5).
- **Workspace entry resolver** — does not exist. This is the object Section
  1 found missing, named explicitly here for the first time. Its job, if
  built, would be narrow: given a `workspace_id`, produce whatever that
  workspace's product needs to construct its screen — nothing more.
- **Trading Intelligence Decision Center** — the product-owned destination;
  real (`applications/trading_intelligence/ui/decision_center/`).
- **`DecisionCenterController`** — real, unchanged, the same object Section
  1 already described.

## 3. Ownership

Restated from `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Sections 3-4 and
`AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 3,
applied specifically to workspace entry — not a new boundary:

**Platform owns:**
- Navigation — composing `NavigationModel` (already real).
- Workspace discovery — knowing a `workspace_id` exists and which product
  it belongs to (`WorkspaceRegistry`, already real).

**Product owns:**
- Workspace behavior — what happens once inside the workspace.
- Controllers — `DecisionCenterController` and any future equivalent.
- Screens — `DecisionCenterScreen` and any future equivalent.

**The boundary consequence this document adds, not previously stated this
precisely:** `AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 4 already
forbids the shell from knowing "trading logic... Sentinel internals," and
states the shell "routes to a product's workspace; it does not call into
that product's services directly." A workspace entry resolver, if it
imported `DecisionCenterController` directly to construct one, would
violate that rule outright — it would be platform code holding a live
dependency on product-internal service/adapter wiring. Whatever eventually
connects `NavigationItem` to `DecisionCenterController` must therefore be
either **product-owned** (Trading Intelligence supplies its own
entry-point callable; the platform never imports the controller) or an
**inversion-of-control registration** (the product registers a
constructor function with the platform at startup, so the platform holds
only a callable, never a class import). Both keep the boundary intact;
directly importing the controller from platform code does not. This
document does not choose between the two — Section 4 addresses whether
either is needed yet at all.

## 4. Is a Workspace Entry Registry/Factory Needed?

**Decision: not yet — but for a different, more precise reason than the
Composition Design document's rejected "application coordinator," worth
distinguishing rather than repeating that conclusion unexamined.**

The composer rejected in
`AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md` Section 4 was
about **choosing among multiple products/workspaces** — routing logic with
nothing real to route among yet. A workspace entry resolver is a narrower,
structurally different concern: **not** routing logic, but the
inversion-of-control point Section 3 just identified as eventually
*required*, not merely convenient, once real (non-test) code needs to go
from a `NavigationItem` to a constructed screen without violating the
shell's own boundary rule.

**Still not needed now, for three reasons specific to this narrower
question:**

1. **No real caller exists yet.** Nothing outside tests ever holds a
   `NavigationItem` and needs to act on it — there is no running
   application, no rendering layer, no real user session. A resolver with
   no real caller is unverifiable except against more fakes.
2. **Tests don't need it and shouldn't use it as a substitute for testing
   it.** The established pattern throughout this codebase (`ADR-005`-cited
   precedent; `test_trading_intelligence_registration.py`;
   `test_trading_intelligence_product_integration.py`) is that integration
   tests may cross ownership boundaries directly — a test may import both
   `NavigationBuilder` and `DecisionCenterController` in the same file to
   prove they compose, without that being a production boundary violation.
   Section 5's milestone uses exactly this allowance; it does not need a
   resolver to exist first.
3. **Building it now would mean guessing its shape with one data point.**
   With exactly one product and one workspace registered anywhere (Decision
   Center), a registration mechanism's real design questions — static list
   vs. dynamic self-registration (`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`
   Section 7's already-open question, same unresolved question here) —
   can't be answered from a single example.

**Revisit when:** a second workspace or product needs the same connection
(Portfolio, Risk, or Wealth Intelligence, per
`AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md`'s excluded-capabilities
list), or when any real, non-test code — not just a test — needs to perform
this lookup, whichever comes first.

## 5. First Implementation Milestone

**The smallest code change required — a test, not a new production class,**
matching Section 4's conclusion that no resolver is needed yet: extend
`applications/platform/tests/test_trading_intelligence_product_integration.py`
(or add an adjacent test in the same file), taking the `NavigationModel`
it already builds, locating its Decision Center `NavigationItem`, and using
that as the basis to directly construct a `DecisionCenterController` backed
by `mock_data.build_mock_screen()` — then asserting the resulting
`DecisionCenterScreen` is correct.

This is the same milestone `AARA_TRADING_INTELLIGENCE_DEMO_RUNTIME_DESIGN.md`
Section 5 already recommended, confirmed still correct and unchanged by this
document's deeper look at the ownership question: because the test is
integration-test code (Section 4, reason 2), it may import both
`NavigationBuilder` and `DecisionCenterController` directly, proving the
full "selects `NavigationItem` → working `DecisionCenterScreen`" path
end-to-end with zero new production code — no resolver, no registry, no
application coordinator, and none of this task's excluded items (no UI
framework, no authentication, `ADR-004` untouched, no coordinator,
`dashboard/` untouched).

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `applications/platform/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, or any other protected
path was created or modified. No ADR was resolved. This document only reads
and cites existing code and prior documentation.
