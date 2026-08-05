# AARA Trading Intelligence — Application Composition Design

**Status:** Design proposal. Documentation only. No code, UI framework, or
authentication was created. `applications/trading_intelligence/`,
`sentinel_engine/`, `ledger/`, `bot/`, `dashboard/`, `scheduler/`,
`.github/workflows/`, `database/` untouched, confirmed via `git status`
before and after. `ADR-004` is not resolved by this document.

**Authority:** `AARA_TRADING_INTELLIGENCE_MVP_SCOPE_DECISION.md`,
`AARA_TRADING_INTELLIGENCE_DECISION_CENTER_CAPABILITY_MODEL.md`,
`AARA_PLATFORM_SHELL_ARCHITECTURE.md`,
`AARA_NAVIGATION_MODEL_ARCHITECTURE.md`,
`AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md`,
`ADR-005-platform-shell-model.md`. Two of these authority documents are
partially stale relative to real code verified directly for this document —
noted precisely where it matters, not silently corrected or silently
repeated.

---

## 1. Current Implemented Building Blocks

### Platform

- **Product descriptor** — `Product`
  (`applications/platform/registry/product_registry.py`): `product_id`,
  `name`, `entitlement_required`, `description`, `status`. **Correction to
  `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md` Section 2**, which describes
  the real dataclass as having "`product_id`, `name` only" — verified
  directly, that is no longer accurate; the module's own docstring calls
  itself "a minimal extension" of that document's proposal.
  `ProductRegistry(ABC)` (`register`/`list_products`) has **zero concrete
  implementations**; the only place `.register()` is ever called is a
  test-local `_InMemoryProductRegistry`
  (`applications/platform/tests/test_trading_intelligence_registration.py`).
- **Workspace registration** — `Workspace`
  (`applications/platform/workspaces/workspace.py`): `workspace_id`,
  `product_id`, `display_name`, `visibility`, `description`, `order`.
  `WorkspaceRegistry(ABC)` (`register_workspace`/`list_workspaces(product_id)`)
  — same status as `ProductRegistry`: zero concrete implementations, only
  test-local fakes call it.
- **Navigation model** — `NavigationItem`, `NavigationModel`,
  `NavigationBuilder` (`applications/platform/navigation/`). **Correction to
  `AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 4/5**, which states the
  Navigation Model is "not implemented" and "no builder exists" — verified
  directly, this is now stale: all three exist, are real, and are tested.
  `NavigationBuilder.build()` composes `AuthenticationProvider.get_current_user()`
  → `ProductRegistry.list_products()` (entitlement-filtered via
  `EntitlementChecker.has_access()`) → `WorkspaceRegistry.list_workspaces(product_id)`
  into a `NavigationModel`. Entitlement filtering is product-scoped only —
  `EntitlementChecker.has_access()` takes a `product_id`, not a
  `workspace_id` — so a product's workspaces are all-or-nothing visible
  together, resolving `AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 3's
  open question by construction, not by new decision.
  **Separately, `ShellBuilder` (Phase 4E) still does not call
  `NavigationBuilder` or `WorkspaceRegistry` at all** — confirmed in
  `ADR-005-platform-shell-model.md` and still true: `ShellBuilder`/`ShellModel`
  and `NavigationBuilder`/`NavigationModel` remain two independent, parallel
  pipelines with nothing connecting them.

### Trading Intelligence

All four real and tested end-to-end (77 tests: 49 in
`applications/trading_intelligence/tests`, 28 in
`applications/trading_intelligence/ui/tests`), verified directly:

- **`DecisionQueryService`** (`services/decision_query_service.py`) — wraps a
  `DecisionSource`; `get_decision_view`/`list_decision_views`.
- **`SentinelProjectionDecisionSource`** (`adapters/sentinel_projection_decision_source.py`)
  — a `DecisionSource` implementation wrapping a
  `sentinel_engine.repositories.projection_repository.ProjectionRepository`.
- **`DecisionCenterController`** (`ui/decision_center/controller.py`) — the
  only place in `ui/` permitted to call `DecisionQueryService`;
  `load_decisions`/`load_decision_detail`/`load_screen`.
- **`DecisionCenterScreen`** (`ui/decision_center/screen.py`) — composed of
  `DecisionListArea`/`DecisionDetailArea`, framework-independent dataclasses.

## 2. Target Composition Flow

```
User context
    |
    v
Platform shell
    |
    v
Trading Intelligence product
    |
    v
Decision Center workspace
    |
    v
DecisionCenterController
    |
    v
DecisionCenterScreen
```

Each arrow, annotated against real code rather than presented as if already
connected:

- **User context → Platform shell** — blocked. `AuthenticationProvider.get_current_user()`
  has zero concrete implementations; `NavigationBuilder.build()` returns an
  empty `NavigationModel` (`current_user=None, items=[]`) whenever no user
  is available, which is always, today.
- **Platform shell → Trading Intelligence product** — the platform shell
  step is, concretely, **two disconnected pipelines**, not one (Section 1):
  `ShellBuilder` produces a `ShellModel` with a plain `available_workspaces`
  id list; `NavigationBuilder` produces the richer `NavigationModel`.
  Neither has ever been exercised with `TRADING_INTELLIGENCE_PRODUCT` — the
  real descriptor (`applications/trading_intelligence/product.py`) has never
  been passed to any concrete `ProductRegistry`, only to a test-local fake,
  and never inside the same test as `NavigationBuilder` (verified: the
  `NavigationBuilder` tests use a locally-defined synthetic `Product`, not
  the real `TRADING_INTELLIGENCE_PRODUCT`).
- **Trading Intelligence product → Decision Center workspace** — no real
  `Workspace` value for Decision Center exists anywhere outside test code.
  The closest thing, `Workspace(workspace_id="trading_intelligence.decision_center",
  ...)`, exists only inside
  `applications/platform/tests/test_navigation_builder.py` as an
  illustrative test fixture — never constructed in
  `applications/trading_intelligence/` itself.
- **Decision Center workspace → `DecisionCenterController`** — **this
  connection has never been built or tested at all.** Nothing in this
  codebase takes a resolved `NavigationItem`/`Workspace` and uses it to
  decide to construct a `DecisionCenterController`. Every existing test
  constructs the controller directly, bypassing navigation entirely.
- **`DecisionCenterController` → `DecisionCenterScreen`** — **fully real**,
  the only genuinely complete arrow in this diagram (Section 1).

**Stated plainly:** of six arrows, one is fully real, and the other five
each depend on a piece that is either unimplemented (`AuthenticationProvider`),
disconnected (`ShellBuilder`/`NavigationBuilder`), or never actually
instantiated for Trading Intelligence specifically (`Product`, `Workspace`,
the workspace→controller link). Section 6 identifies the single most
valuable next step among these gaps.

## 3. Application Boundary

Synthesized from `AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md` Section 3,
`AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 3, and
`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Sections 3-4 — consistent across all
three, not re-decided here:

**Belongs in `applications/trading_intelligence/`:**
- Workspace content and screen behavior — `ui/decision_center/` in full
  (`screen.py`, `controller.py`, `mock_data.py`).
- Business logic — `services/`, `adapters/`, `contracts/`, `projections/`
  (product-internal, Trading-Intelligence-specific).
- The product's own descriptor value — `TRADING_INTELLIGENCE_PRODUCT`
  (`product.py`) — the *data*, not the registry that holds it.
- Any future `Workspace` value describing Decision Center, Portfolio, or
  Risk as Trading-Intelligence-owned entries (none exist yet, per Section 2).

**Belongs in `applications/platform/`:**
- Registries — `ProductRegistry`, `WorkspaceRegistry` (the interfaces and
  any future concrete implementation; discovery mechanics, not product
  content).
- Composition — `NavigationBuilder`, `ShellBuilder` (combining registry data
  into navigation/shell state).
- Cross-cutting concerns — `AuthenticationProvider`, `EntitlementChecker`
  (identity and access, not specific to any one product).

**The boundary rule, stated once rather than per-item:** platform code may
know a product exists, its `product_id`, and its registered workspaces —
registry-level knowledge only. Platform code must never import
`applications.trading_intelligence` (or any future product) directly; this
is already a checked fact, not just a stated rule —
`test_product_registry_module_does_not_import_product_internals` and the
equivalent AST-scan pattern used throughout `applications/platform/tests/`.

## 4. MVP Composition Object

**Decision: not needed yet.** A dedicated application coordinator/composer
— something that takes resolved `User`/`NavigationItem` state and decides
which product controller to instantiate — is not designed or built by this
document, and this document concludes one should not be built now, for
three concrete reasons:

1. **Nothing real exists yet for it to compose.** `AuthenticationProvider`
   has zero implementations; without a real user, any composer's actual
   inputs would be synthetic, making its logic untestable against anything
   but more fakes — no different from what `DecisionCenterController`'s own
   tests already do directly.
2. **There is exactly one product and one workspace worth routing to.**
   A composer earns its cost when there's a real choice to make among
   multiple products/workspaces; today there is only Decision Center, real
   and reachable by direct construction. Introducing a composer now would
   be an abstraction with a single caller and a single destination.
3. **`ShellBuilder`/`NavigationBuilder`'s own unresolved relationship (`ADR-005`)
   would need settling first.** A composer sitting downstream of "the
   platform shell" needs to know which of the two pipelines is authoritative
   — building one now would either duplicate that ambiguity or force a
   premature resolution of a question `ADR-005` deliberately left open until
   a real UI consumer exists.

**Revisit when:** a real `AuthenticationProvider` implementation exists, a
second product or a second Trading Intelligence workspace becomes real
enough to route to, or `ADR-005`'s own stated refactoring triggers fire —
the same three conditions `ADR-005` Section 8 already named for unifying
`ShellBuilder`/`NavigationBuilder`, since a composer's design depends
directly on that unification happening first.

## 5. Rendering Boundary

**Current:** dataclass screen models only. `DecisionCenterScreen`/
`DecisionListArea`/`DecisionDetailArea` are plain, frozen, framework-independent
dataclasses (`applications/trading_intelligence/ui/decision_center/screen.py`'s
own docstring: "No rendering framework... testable the same way
`DecisionView`/`DecisionContract` already are"). Nothing renders them to a
screen a user could see — proven by tests, not by a running application.

**Future:** a web/UI rendering layer. Explicitly named as unresolved,
consistent with two prior documents, not decided here:
`AARA_PLATFORM_SHELL_ARCHITECTURE.md` Section 6 ("Frontend framework — no
technology choice made anywhere in this migration for a real (non-mock)
UI") and `AARA_NAVIGATION_MODEL_ARCHITECTURE.md` Section 7 ("Frontend
router," "React implementation," "URL strategy" — all open). This document
does not choose a framework, a router, or a URL strategy.

## 6. First Implementation Milestone Recommendation

**The smallest next coding step, within composition scope only:** write a
new integration test proving `TRADING_INTELLIGENCE_PRODUCT` (the real
descriptor, not a synthetic `Product`) plus a real `Workspace` value for
Decision Center compose correctly through `NavigationBuilder` — closing the
specific, precisely-identified gap from Section 2 ("Trading Intelligence
product → Decision Center workspace" has never been proven, even in tests,
with the real descriptor).

Concretely: a test analogous to
`applications/platform/tests/test_trading_intelligence_registration.py`
(Phase 4D's established pattern — a test-local in-memory registry, the real
product/workspace values, no new production code), extended to also
exercise `NavigationBuilder` and assert the resulting `NavigationModel`
contains a correct `NavigationItem` for Decision Center.

This satisfies every constraint this task states: no UI framework (asserts
on a `NavigationModel` value, nothing rendered); no authentication (uses the
same `_FakeAuthenticationProvider` pattern already established in
`test_navigation_builder.py`); no ledger connection; does not touch
`ADR-004`; adds no Evidence/Risk/Governance functionality. It is strictly
narrower than Section 4's rejected composer — a test proving composition
*works*, not a new production abstraction that *performs* it.

---

## Constraints Confirmed

No file under `applications/trading_intelligence/`, `sentinel_engine/`,
`ledger/`, `bot/`, `dashboard/`, or any other protected path was created or
modified. No UI framework, authentication, or ledger connection was added.
`ADR-004` was not resolved. This document only reads and cites existing
code and prior documentation.
