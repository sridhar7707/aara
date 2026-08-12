# ADR-013 — Minimal Temporary EvidenceService Wiring for Trust Decisions

**Status:** Accepted  
**Date:** 2026-08-11  
**Decision Type:** Architecture / Governance  
**Related ADRs:** ADR-002, ADR-004, ADR-009, ADR-012

---

## 1. Context

ADR-009 establishes the Sentinel evidence integration for the trust-decision path.

ADR-012 establishes the evidence adapter boundary used to translate model output into Sentinel evidence records.

ADR-009 intentionally separated the evidence call from the question of service construction. Its **EvidenceService Instance / Wiring** section requires a separate governance decision before an `EvidenceService` instance may be obtained, while explicitly prohibiting that future wiring decision from authorizing a new `LedgerRepository` or `ProjectionRepository` implementation.

A repository audit was performed to identify an existing legal wiring path.

The audit established:

1. `EvidenceService` requires both a concrete `LedgerRepository` and a concrete `ProjectionRepository`.
2. `LedgerRepository` requires a concrete `LedgerStore`.
3. `ProjectionRepository` is an abstract repository requiring a concrete implementation.
4. No reusable production in-memory `LedgerStore` / `ProjectionRepository` implementation exists in `sentinel_engine/`.
5. Existing in-memory implementations are independently defined in application bootstraps and tests.
6. Importing those implementations into `sentinel_engine` would violate existing package-boundary rules or require prohibited bootstrap changes.
7. `bot/_main_trust_decisions.py` currently has no `sentinel_engine` import and does not yet perform the ADR-009-authorized evidence call.
8. The existing application composition roots are product-level and are explicitly not available for this temporary trust-decision wiring.
9. No existing Sentinel-wide service-locator, dependency-injection, or process-scoped singleton mechanism exists that can be reused.
10. Therefore, there is no existing legal repository implementation that can satisfy the mandatory `EvidenceService` constructor dependencies.

The repository audit further established that `EvidenceService` exercises only a minimal dependency surface for the authorized trust-decision flow:

- `LedgerRepository.save_event()`, which transitively calls `LedgerStore.append()`;
- `ProjectionRepository.advance_status()`, which transitively calls `get()` and conditionally `save()`;
- `EvidenceService.get_evidence_for_decision()` uses only its own in-process evidence dictionary and does not read either repository.

Consequently, the smallest legal temporary wiring requires a narrowly scoped in-memory `LedgerStore` and `ProjectionRepository` implementation pair.

This creates a direct conflict with ADR-009's forward-looking prohibition on a new repository implementation.

Per `docs/platform/AARA_ARCHITECTURE_AUTHORITY.md`'s conflict-resolution mechanism: "A new document that conflicts with an existing authoritative doc does not silently coexist with it. Write a new ADR under `docs/decisions/` that references both and states which wins and why." This ADR is written to satisfy that requirement explicitly for its conflict with ADR-009, following the same citation precedent set by ADR-011's own "Relationship to AARA_ARCHITECTURE_AUTHORITY.md" section.

---

## 2. Decision

Authorize a **minimal, temporary, non-production, non-durable EvidenceService composition boundary** under:

```text
sentinel_engine/composition/evidence.py
```

The composition boundary shall:

1. construct exactly one process-scoped `EvidenceService` instance;
2. construct exactly one temporary in-memory `LedgerRepository` dependency;
3. construct exactly one temporary in-memory `ProjectionRepository` dependency;
4. retain those dependencies for the lifetime of the process;
5. expose the process-scoped `EvidenceService` through a single composition accessor;
6. be consumed by `bot/_main_trust_decisions.py` only for the ADR-009-authorized evidence integration.

The temporary repositories authorized by this ADR are **new minimal implementations**, not reusable existing platform repositories.

They exist solely because no existing legal reusable implementation satisfies the mandatory `EvidenceService` dependencies.

This ADR does **not** establish these temporary repositories as Sentinel's production repository architecture.

---

## 3. Explicit Resolution of ADR-009 Conflict

This ADR explicitly resolves and narrowly supersedes the following restriction in ADR-009's **EvidenceService Instance / Wiring** section:

> Once such wiring is separately authorized, it does **not** authorize a new persistence architecture, a new database, a new ledger backend, or a new `LedgerRepository`/`ProjectionRepository` implementation.

For the limited purpose of the wiring authorized by this ADR, that restriction is superseded **only to the extent necessary to authorize exactly one temporary in-memory repository implementation pair**:

```text
sentinel_engine/composition/evidence.py

    temporary LedgerStore
        ↓
    LedgerRepository

    temporary ProjectionRepository
```

The exception is limited to:

- one temporary `LedgerStore` implementation;
- one temporary `ProjectionRepository` implementation;
- one process-local `LedgerRepository`;
- one process-local `EvidenceService` dependency set;
- the ADR-009-authorized trust-decision evidence flow.

All other provisions and restrictions of ADR-009 remain in force, unchanged.

In particular, this ADR does **not** supersede ADR-009's restrictions concerning:

- production persistence;
- new databases;
- production ledger backends;
- unrelated repository implementations;
- additional `EvidenceService` consumers;
- decision creation;
- projection seeding;
- expansion of the trust-decision evidence flow;
- any other architecture not explicitly authorized here.

---

## 4. Temporary Repository Implementations

The temporary implementations shall be deliberately minimal.

### 4.1 Temporary LedgerStore

The composition boundary shall contain one concrete `LedgerStore` implementation satisfying the existing abstract contract.

Its required state is:

```text
List[Event]
```

Its required behavior is limited to:

```text
append(event)
read_all()
```

`append()` shall retain events in insertion order.

`read_all()` shall return the retained events without exposing the mutable internal collection.

No additional ledger behavior is authorized.

The implementation shall **not** introduce:

- persistence;
- SQL;
- serialization;
- hash chaining;
- deduplication;
- filtering;
- indexing;
- retention policies;
- recovery;
- external storage;
- production ledger semantics.

The existence of `read_all()` is required because it is part of the existing `LedgerStore` abstract contract, even though the ADR-009 evidence-association path does not call it.

---

### 4.2 Temporary ProjectionRepository

The composition boundary shall contain one concrete `ProjectionRepository` implementation satisfying the existing abstract contract.

Its required state is:

```text
Dict[str, DecisionProjection]
```

Its required behavior is limited to:

```text
get(decision_id)
save(projection)
```

`get()` shall return the projection associated with the supplied decision ID, or `None` when absent.

`save()` shall store or replace the projection using `decision_id` as its key.

The implementation shall **not** override `advance_status()`.

The existing concrete `ProjectionRepository.advance_status()` behavior remains authoritative and shall be inherited unchanged.

No additional projection behavior is authorized.

---

## 5. EvidenceService Dependency Surface

The temporary repositories are authorized only because they satisfy the dependencies actually exercised by the governed evidence flow.

`EvidenceService.associate_evidence()` requires:

```text
LedgerRepository.save_event()
ProjectionRepository.advance_status()
```

The transitive repository operations are:

```text
LedgerStore.append()
ProjectionRepository.get()
ProjectionRepository.save()
```

`EvidenceService.get_evidence_for_decision()` does not use either repository and instead reads its own process-local evidence association state.

No additional repository methods or behaviors are required by this ADR.

---

## 6. EvidenceService Lifetime and Ownership

The `EvidenceService` instance shall have **process-scoped lifetime**.

The composition boundary shall own:

- the temporary `LedgerStore`;
- the `LedgerRepository`;
- the temporary `ProjectionRepository`;
- the `EvidenceService`.

Repeated access through the authorized composition accessor within the same process shall return the same `EvidenceService` instance and therefore the same dependency instances.

This is a composition-lifetime decision.

It does **not** establish a general Sentinel singleton/service-locator pattern.

No other Sentinel service is authorized to be constructed through this composition boundary.

---

## 7. Composition Boundary Scope

The sole purpose of:

```text
sentinel_engine/composition/evidence.py
```

is to construct and expose the `EvidenceService` instance required by the ADR-009 trust-decision evidence flow.

It shall not become a general-purpose Sentinel composition root.

This ADR does not authorize construction of:

- `DecisionService`;
- `GovernanceService`;
- `SentinelEngine`;
- other repositories;
- other services;
- application-level infrastructure;
- product-level dependencies.

No generalized dependency-injection framework or service locator is authorized.

---

## 8. Access from bot/_main_trust_decisions.py

`bot/_main_trust_decisions.py` may obtain the `EvidenceService` only through the authorized composition boundary.

The intended dependency direction remains:

```text
bot/_main_trust_decisions.py
        │
        ▼
sentinel_engine.composition.evidence
        │
        ▼
EvidenceService
        │
        ├── LedgerRepository
        │       └── temporary LedgerStore
        │
        └── ProjectionRepository
                └── temporary in-memory state
```

The dependency direction shall remain:

```text
bot → sentinel_engine
```

The following direction remains prohibited:

```text
sentinel_engine → bot
```

The bot shall not construct:

- `EvidenceService`;
- `LedgerRepository`;
- `ProjectionRepository`;
- `LedgerStore`.

The bot shall not know about the temporary repository implementations.

---

## 9. Application Bootstrap Boundary

This ADR explicitly does **not** authorize modifications to:

```text
applications/trading_intelligence/bootstrap.py
applications/wealth_intelligence/bootstrap.py
applications/*/bootstrap.py
```

The existing application composition roots remain product-level composition roots.

The temporary EvidenceService composition boundary is intentionally separate from them.

The bot shall not reach into an application bootstrap module to obtain `EvidenceService`.

This avoids coupling the trust-decision path to a product-specific composition root.

---

## 10. ADR-004 Boundary

No amendment to ADR-004 is required by this decision.

ADR-004's explicit implementation prohibition is scoped to backend implementation under:

```text
sentinel_engine/ledger/
```

The temporary repository implementations authorized by this ADR are:

- outside `sentinel_engine/ledger/`;
- explicitly non-production;
- explicitly non-durable;
- process-local;
- created solely for temporary EvidenceService wiring.

This ADR does not select ADR-004 Option A, B, or C.

Nothing in this ADR establishes the temporary implementations as the production ledger or persistence architecture.

The production backend decision remains governed by ADR-004.

---

## 11. ADR-012 Boundary

ADR-012 remains unchanged and fully in force.

This ADR does not modify:

```text
sentinel_engine/adapters/evidence_adapter.py
```

It does not modify:

- `to_evidence_records()`;
- evidence translation semantics;
- evidence model contracts;
- adapter boundaries.

The temporary composition consumes the already-governed evidence service path.

No duplicate evidence translation mechanism is authorized.

---

## 12. ADR-002 Boundary

This ADR does not create a general exception to ADR-002.

The already-authorized ADR-009 exception for:

```text
bot/_main_trust_decisions.py
```

remains the governing authorization for the additive trust-decision integration.

This ADR authorizes the corresponding Sentinel-side composition boundary outside ADR-002's protected paths.

No additional protected path is authorized.

No general precedent is established for placing arbitrary infrastructure in protected areas.

---

## 13. Trust-Decision Projection Limitation

The temporary `ProjectionRepository` shall not be seeded with projections for the purpose of making `advance_status()` produce a visible projection update.

ADR-013 does not authorize decision creation.

The ADR-009-authorized bot flow does not construct a `DecisionService` or otherwise create a `DecisionProjection` for the temporary repository.

Consequently, for the currently authorized bot path:

```text
ProjectionRepository.get(decision_id)
```

will normally return:

```text
None
```

and the inherited `advance_status()` method will therefore not execute its `save()` branch.

The `save()` method nevertheless remains correctly implemented because it is part of the existing repository contract and may be exercised by direct repository tests.

This behavior is intentional and shall not be "fixed" by adding projection seeding or decision creation.

Any future requirement to create, seed, persist, or reconcile projections requires separate governance.

---

## 14. Process-Local State Limitation

The temporary repository state is strictly process-local.

Separate OS processes shall have separate instances and separate state.

For example:

```text
CLI process
    └── EvidenceService A
        └── temporary repositories A

Scheduler/HTTP process
    └── EvidenceService B
        └── temporary repositories B
```

State is not shared or reconciled between processes.

This is an intentional consequence of the non-durable temporary architecture and is consistent with the existing ADR-009 limitation concerning process lifecycle.

The temporary repositories shall not be presented as a unified or authoritative Sentinel ledger.

---

## 15. Explicit Non-Decisions

This ADR does **not** decide:

1. the production ledger backend;
2. the production projection repository;
3. durable evidence persistence;
4. database selection;
5. application-wide dependency injection;
6. final application composition architecture;
7. ADR-004 Option A;
8. ADR-004 Option B;
9. ADR-004 Option C;
10. cross-process evidence state;
11. evidence recovery after process termination;
12. decision creation from the bot;
13. projection seeding from the bot;
14. reconciliation between temporary and application-level repositories;
15. any additional EvidenceService consumers.

These remain separately governed.

---

## 16. Future Migration Requirement

The temporary composition boundary is explicitly a migration point.

When the production evidence backend, ledger backend, projection repository, and composition architecture are separately governed, this temporary wiring shall be replaced or migrated.

The migration shall remove the temporary in-memory repository implementations rather than silently promoting them to production infrastructure.

The temporary implementations shall not acquire additional responsibilities in the meantime.

---

## 17. Implementation Constraints

If this ADR is accepted, implementation shall remain limited to the following scope.

### Authorized production-tree additions

```text
sentinel_engine/composition/__init__.py
sentinel_engine/composition/evidence.py
```

and the minimum tests necessary to verify the authorized behavior.

The composition module may contain only:

- the temporary `LedgerStore` implementation;
- the temporary `ProjectionRepository` implementation;
- construction of `LedgerRepository`;
- construction of `EvidenceService`;
- the process-scoped accessor required by the bot.

### Authorized bot change

The existing ADR-009-authorized evidence integration may subsequently be implemented in:

```text
bot/_main_trust_decisions.py
```

No additional bot architectural change is authorized.

### Prohibited changes

Implementation shall not:

- modify `applications/*/bootstrap.py`;
- modify ADR-004;
- modify ADR-009;
- modify ADR-012;
- alter `EvidenceService`;
- alter `LedgerRepository`;
- alter `ProjectionRepository`;
- alter `LedgerStore`;
- introduce production persistence;
- introduce a database;
- introduce a production ledger backend;
- introduce a DI framework;
- introduce a general service locator;
- construct `DecisionService` in `bot/`;
- seed projections;
- create decisions;
- create additional repository implementations;
- expose the temporary repositories as general-purpose infrastructure;
- wire additional consumers to the temporary `EvidenceService`.

Any change outside this scope requires separate governance.

---

## 18. Testing Requirements

Acceptance of this ADR authorizes the following verification scope.

### Composition lifetime

Verify that repeated access through the authorized composition accessor returns the same `EvidenceService` instance within a process.

### Temporary LedgerStore

Verify:

- concrete instantiation;
- `append()` behavior;
- insertion order;
- `read_all()` round trip;
- isolation of returned state from internal mutable state.

### Temporary ProjectionRepository

Verify:

- concrete instantiation;
- `get()` returns `None` for an absent decision;
- `save()` stores a projection;
- `get()` returns the stored projection;
- saving the same decision ID replaces the existing projection.

### EvidenceService integration

Verify that the `EvidenceService` obtained through the composition boundary can execute the ADR-009-authorized `associate_evidence()` flow.

### Import boundary

Extend the existing package-import coverage as necessary so the new production composition module remains free of imports from:

```text
bot
dashboard
scheduler
database
applications
```

No test shall require importing a production repository implementation from an application or test package.

---

## 19. Alternatives Considered

### Option A — Dedicated Sentinel composition module

**Selected.**

Create:

```text
sentinel_engine/composition/evidence.py
```

with the minimum temporary repository implementations and process-scoped `EvidenceService`.

Advantages:

- preserves `bot → sentinel_engine`;
- keeps infrastructure construction outside `bot`;
- avoids application bootstrap coupling;
- does not select ADR-004's production backend;
- makes the temporary exception explicit and bounded;
- provides a clear future migration point.

---

### Option B — Reuse an application composition root

**Rejected.**

Using:

```text
applications/trading_intelligence/bootstrap.py
```

or another application composition root would couple the trust-decision flow to product-level application infrastructure.

ADR-009 explicitly excludes reaching into an existing application composition root for this wiring.

This ADR therefore does not authorize that path.

---

### Option C — Import an existing test fake

**Rejected.**

Existing test fakes are not production composition dependencies.

Importing a test fixture from an application test package into Sentinel production code would create a new and unsupported architectural pattern.

This ADR therefore authorizes a minimal production-tree temporary implementation instead.

---

### Option D — Wait for ADR-004 production composition

**Valid but deferred.**

Waiting would avoid temporary repository implementations, but would also prevent the separately governed ADR-009 evidence integration from obtaining its required service instance.

The architecture owner may reject this ADR and choose to wait for the production composition decision instead.

---

## 20. Consequences

### Positive

- Resolves the ADR-009 wiring conflict explicitly rather than silently.
- Establishes a legally governed path for the existing `EvidenceService`.
- Keeps the exception extremely narrow.
- Preserves dependency direction.
- Avoids modifying application bootstrap modules.
- Avoids selecting a production persistence architecture prematurely.
- Avoids modifying ADR-004.
- Avoids modifying ADR-012.
- Makes the temporary repository behavior precise and testable.
- Establishes a clear migration point.

### Negative

- Introduces two new temporary in-memory repository implementations.
- Creates a third independent in-memory repository state in addition to existing application-level instances.
- State is lost when the process terminates.
- Separate processes have separate state.
- The temporary composition module will eventually be removed or replaced.
- The repository exception must be carefully protected against reuse creep.

### Primary Risk

The primary architectural risk is that temporary infrastructure becomes permanent through incremental reuse.

This ADR therefore deliberately limits:

- location;
- lifetime;
- consumers;
- behavior;
- persistence;
- repository surface;
- construction scope.

Any expansion requires a new governance decision.

---

## 21. Acceptance Criteria

ADR-013 may be considered implemented only when all of the following are true:

- `sentinel_engine/composition/evidence.py` exists only for the authorized composition purpose.
- The temporary `LedgerStore` implements only the existing abstract contract.
- The temporary `ProjectionRepository` implements only the existing abstract contract.
- The temporary repositories use only process-local in-memory state.
- No persistence is introduced.
- `EvidenceService` is process-scoped through the authorized composition boundary.
- The composition boundary owns the service and its temporary dependencies.
- `bot/_main_trust_decisions.py` obtains `EvidenceService` only through that boundary.
- The bot does not construct Sentinel infrastructure directly.
- Dependency direction remains `bot → sentinel_engine`.
- No `sentinel_engine → bot` dependency exists.
- No `applications/*/bootstrap.py` is modified.
- No ADR-004 production option is selected.
- ADR-004 remains unchanged.
- ADR-012 remains unchanged.
- No duplicate evidence adapter path is introduced.
- No decision creation or projection seeding is introduced.
- No additional EvidenceService consumer is wired.
- The temporary repositories are not exposed as general-purpose infrastructure.
- The process-local state limitation is documented and tested.
- The ADR-009 wiring restriction is overridden only within the explicit scope stated in this ADR.
- All other ADR-009 restrictions remain unchanged.

---

## 22. Decision Statement

> **Authorize a minimal, temporary, non-production, non-durable EvidenceService composition boundary at `sentinel_engine/composition/evidence.py`.**
>
> **The boundary shall construct one process-scoped EvidenceService and exactly one temporary in-memory LedgerStore/LedgerRepository pair and one temporary in-memory ProjectionRepository, using only the minimum behavior required by the existing governed EvidenceService and repository contracts.**
>
> **This ADR explicitly supersedes ADR-009 only with respect to ADR-009's prohibition against a new LedgerRepository/ProjectionRepository implementation, and only for this single temporary repository pair and this single EvidenceService wiring path.**
>
> **All other ADR-009 constraints remain in force unchanged.**
>
> **This decision does not select or modify ADR-004's production backend options, does not modify ADR-012, does not modify application composition roots, does not introduce persistence, and does not establish the temporary repositories as production architecture.**
>
> **The temporary wiring shall be replaced or migrated when the production backend and composition architecture are separately governed.**

---

## 23. Status

**Accepted**

**No implementation is authorized until ADR-013 is accepted.**