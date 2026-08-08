# DecisionState Enum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every raw string that represents a decision's lifecycle stage or a human approval verdict with two new, narrowly-scoped enums (`DecisionState`, `ApprovalStatus`), across `sentinel_engine` and its two downstream applications, with zero behavior change.

**Architecture:** Two new `(str, Enum)` types — `sentinel_engine.domain.decision_state.DecisionState` (4 members: `DECISION_CREATED`, `EVIDENCE_ATTACHED`, `GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`) and `sentinel_engine.governance.approval_status.ApprovalStatus` (2 members: `APPROVED`, `REJECTED`) — mirror the existing `EventType(str, Enum)` pattern already used in this codebase (`sentinel_engine/events/event_types.py`). Inheriting from `str` is what makes this a zero-behavior-change refactor: every existing string comparison (`status == "DECISION_CREATED"`), dict key usage, and string method call (`status.replace("_", " ").title()`) keeps working unchanged, because a `(str, Enum)` member *is* a string at runtime. `EventType` and `DecisionState` stay separate types (different concepts: "what happened" vs. "where is this decision now") — no merging, no renaming of `EventType` members.

**Tech Stack:** Python 3.9, dataclasses, `enum.Enum`, pytest.

## Global Constraints

- `DecisionState` has exactly 4 members: `DECISION_CREATED`, `EVIDENCE_ATTACHED`, `GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`. Do not add `CANDIDATE_EVALUATED`, `RISK_EVALUATED`, `DECISION_EXECUTED`, or `DECISION_OUTCOME_RECORDED` — no current service transitions a decision into those states.
- `ApprovalStatus` has exactly 2 members: `APPROVED`, `REJECTED`. It is a separate type from `DecisionState` — never reused for lifecycle stage.
- `EventType` (`sentinel_engine/events/event_types.py`) is not modified, renamed, or merged with either new enum.
- No new workflow logic, no execution/outcome handling, no persistence changes (there is no concrete SQLite/production `ProjectionRepository` or `LedgerStore` yet — only in-memory test/demo doubles — so "no persistence changes" is automatically satisfied as long as no such adapter is introduced).
- No changes to CQRS boundaries: read side (`queries/`, `presentation/`) keeps assembling data only from `LedgerRepository`/`ProjectionRepository`, never through the write-side services.
- `applications/trading_intelligence/ui/` has an enforced boundary test (`test_ui_does_not_import_bot_dashboard_scheduler_or_sentinel_engine_directly` in `applications/trading_intelligence/ui/tests/test_ui_structure.py`) that forbids **any** file under `ui/` — including `mock_data.py` — from importing `sentinel_engine` directly, in any form. `mock_data.py` must obtain `DecisionState` by importing it from `applications.trading_intelligence.projections.decision_view` (which re-exports it as a normal side effect of importing it for its own type hint), never from `sentinel_engine.domain.decision_state` directly. Do not weaken or edit that test.
- `applications/trading_intelligence/contracts/` and `applications/trading_intelligence/projections/` are NOT under that same restriction (confirmed: `test_package_imports.py`'s package-wide scan only forbids `bot`/`dashboard`/`scheduler`/`database`/`ledger`, not `sentinel_engine`) — `decision_contract.py` and `decision_view.py` may import `sentinel_engine.domain.decision_state.DecisionState` directly.
- `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, `ledger/` (top-level) are frozen per the AARA migration protected-paths policy. None of those directories are touched by this plan — `database/services/decision_service.py` and `dashboard/components/decision_quality.py`/`pending_approvals.py` have their own, unrelated `status` strings (legacy pre-AARA bounded context, zero references to `sentinel_engine.projections.DecisionProjection`) and are explicitly out of scope.
- Two pre-existing test-only usages of the excluded value `"DECISION_EXECUTED"` (`sentinel_engine/tests/test_decision_projection.py`, `sentinel_engine/tests/test_projection_repository.py`, plus two more in `applications/trading_intelligence/tests/test_decision_contract.py` and `test_decision_view.py`) exist purely to prove dataclass immutability/overwrite mechanics — they need *some* second valid value, not that specific one. Replace all four with `DecisionState.APPROVAL_RECORDED`.
- `mock_data.py`'s third mock entry (`status="DECISION_EXECUTED"`, NVDA/SELL) has the same problem as the already-approved `QUALIFIED_REJECTION` fix: `DECISION_EXECUTED` is excluded from `DecisionState`. Replace it with `DecisionState.APPROVAL_RECORDED` too (closest real "final" state), by the same reasoning already approved for `QUALIFIED_REJECTION` → `GOVERNANCE_EVALUATED`. Flagged here since the user only explicitly named the `QUALIFIED_REJECTION` swap.
- Deliverable is a single, minimal, focused commit — do not commit per task. Run the full test suite once at the end and commit everything together.

---

## File Map

**New:**
- `sentinel_engine/domain/decision_state.py` — `DecisionState` enum
- `sentinel_engine/tests/test_decision_state.py`
- `sentinel_engine/governance/approval_status.py` — `ApprovalStatus` enum
- `sentinel_engine/tests/test_approval_status.py`

**Modified (production):**
- `sentinel_engine/projections/decision_projection.py`
- `sentinel_engine/governance/approval.py`
- `sentinel_engine/services/decision_service.py`
- `sentinel_engine/services/evidence_service.py`
- `sentinel_engine/services/governance_service.py`
- `sentinel_engine/repositories/projection_repository.py`
- `sentinel_engine/queries/decision_query.py`
- `sentinel_engine/queries/decision_center_query.py`
- `sentinel_engine/queries/morning_brief_query.py`
- `sentinel_engine/presentation/investor_presenter.py`
- `applications/trading_intelligence/contracts/decision_contract.py`
- `applications/trading_intelligence/projections/decision_view.py`
- `applications/trading_intelligence/ui/decision_center/mock_data.py`

**Modified (tests only):** every test file that constructs a `DecisionProjection`/`DecisionContract`/`DecisionView`/`Approval`/`ApprovalSummary`/`ApprovalSummaryRow` with a literal status string, or asserts equality against one. Full list inside each task below.

**Not modified (verified, no code change needed):**
- `sentinel_engine/events/event_types.py` (`EventType` untouched)
- `applications/trading_intelligence/adapters/sentinel_projection_decision_source.py` (passes `projection.status`/now `DecisionState` straight through — already type-correct)
- `applications/trading_intelligence/ui/decision_center/screen.py` and `controller.py` (duck-typed `.replace()`/`.title()` on a `(str, Enum)` value works unchanged)
- `applications/wealth_intelligence/ui/investor_workspace.py` (Gradio row-building code treats status as an opaque string-like value; unaffected by the type change)

---

## Task 1: `DecisionState` enum

**Files:**
- Create: `sentinel_engine/domain/decision_state.py`
- Test: `sentinel_engine/tests/test_decision_state.py`

**Interfaces:**
- Produces: `DecisionState(str, Enum)` with members `DECISION_CREATED`, `EVIDENCE_ATTACHED`, `GOVERNANCE_EVALUATED`, `APPROVAL_RECORDED`, each valued as its own name (e.g. `DecisionState.DECISION_CREATED == "DECISION_CREATED"`), plus classmethod `has_value(value: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# sentinel_engine/tests/test_decision_state.py
"""Tests for sentinel_engine.domain.decision_state."""
from sentinel_engine.domain.decision_state import DecisionState


def test_all_expected_decision_states_exist():
    assert DecisionState.DECISION_CREATED == "DECISION_CREATED"
    assert DecisionState.EVIDENCE_ATTACHED == "EVIDENCE_ATTACHED"
    assert DecisionState.GOVERNANCE_EVALUATED == "GOVERNANCE_EVALUATED"
    assert DecisionState.APPROVAL_RECORDED == "APPROVAL_RECORDED"


def test_decision_state_has_exactly_four_members():
    assert len(list(DecisionState)) == 4


def test_decision_state_members_are_strings():
    for member in DecisionState:
        assert isinstance(member.value, str)


def test_valid_decision_state_string_is_recognized():
    assert DecisionState.has_value("DECISION_CREATED") is True
    assert DecisionState.has_value("EVIDENCE_ATTACHED") is True
    assert DecisionState.has_value("GOVERNANCE_EVALUATED") is True
    assert DecisionState.has_value("APPROVAL_RECORDED") is True


def test_invalid_decision_state_string_is_rejected():
    assert DecisionState.has_value("NOT_A_REAL_STATE") is False


def test_decision_state_excludes_unreachable_event_types():
    """CANDIDATE_EVALUATED, RISK_EVALUATED, DECISION_EXECUTED, and
    DECISION_OUTCOME_RECORDED are declared EventType members but no current
    service transitions a decision into them -- they must stay out of
    DecisionState until a real service path produces them."""
    assert DecisionState.has_value("CANDIDATE_EVALUATED") is False
    assert DecisionState.has_value("RISK_EVALUATED") is False
    assert DecisionState.has_value("DECISION_EXECUTED") is False
    assert DecisionState.has_value("DECISION_OUTCOME_RECORDED") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest sentinel_engine/tests/test_decision_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sentinel_engine.domain.decision_state'`

- [ ] **Step 3: Write the implementation**

```python
# sentinel_engine/domain/decision_state.py
"""Decision lifecycle state: where a decision currently is in its
event-sourced lifecycle, as derived by DecisionProjection.

Distinct from EventType (sentinel_engine.events.event_types): EventType
answers "what happened" (the ledger's event vocabulary); DecisionState
answers "where is this decision now" (the projection's current status).
They are aliased 1:1 today only because every currently-implemented
lifecycle step happens to advance status to its own triggering event's
name -- that is a today-only implementation detail, not a reason to merge
the two types.

Only states a real service currently produces belong here. Do not add
CANDIDATE_EVALUATED, RISK_EVALUATED, DECISION_EXECUTED, or
DECISION_OUTCOME_RECORDED until an actual service path transitions a
decision into one of them.
"""
from enum import Enum


class DecisionState(str, Enum):
    DECISION_CREATED = "DECISION_CREATED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    GOVERNANCE_EVALUATED = "GOVERNANCE_EVALUATED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest sentinel_engine/tests/test_decision_state.py -v`
Expected: 6 passed

---

## Task 2: `ApprovalStatus` enum

**Files:**
- Create: `sentinel_engine/governance/approval_status.py`
- Test: `sentinel_engine/tests/test_approval_status.py`

**Interfaces:**
- Produces: `ApprovalStatus(str, Enum)` with members `APPROVED`, `REJECTED`, plus classmethod `has_value(value: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# sentinel_engine/tests/test_approval_status.py
"""Tests for sentinel_engine.governance.approval_status."""
from sentinel_engine.governance.approval_status import ApprovalStatus


def test_all_expected_approval_statuses_exist():
    assert ApprovalStatus.APPROVED == "APPROVED"
    assert ApprovalStatus.REJECTED == "REJECTED"


def test_approval_status_has_exactly_two_members():
    assert len(list(ApprovalStatus)) == 2


def test_approval_status_members_are_strings():
    for member in ApprovalStatus:
        assert isinstance(member.value, str)


def test_valid_approval_status_string_is_recognized():
    assert ApprovalStatus.has_value("APPROVED") is True
    assert ApprovalStatus.has_value("REJECTED") is True


def test_invalid_approval_status_string_is_rejected():
    assert ApprovalStatus.has_value("PENDING") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest sentinel_engine/tests/test_approval_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sentinel_engine.governance.approval_status'`

- [ ] **Step 3: Write the implementation**

```python
# sentinel_engine/governance/approval_status.py
"""Human/system approval verdict on a decision -- a distinct concept from
DecisionState (sentinel_engine.domain.decision_state): DecisionState
answers "where is this decision in its lifecycle", ApprovalStatus answers
"what was the governance verdict". Never reuse DecisionState for this.
"""
from enum import Enum


class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest sentinel_engine/tests/test_approval_status.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit checkpoint (do not run yet)**

No commit here — this plan lands as a single commit at the end of Task 9.

---

## Task 3: Core domain/projection/repository types

**Files:**
- Modify: `sentinel_engine/projections/decision_projection.py`
- Modify: `sentinel_engine/governance/approval.py`
- Modify: `sentinel_engine/repositories/projection_repository.py`
- Test: `sentinel_engine/tests/test_decision_projection.py`
- Test: `sentinel_engine/tests/test_approval.py`
- Test: `sentinel_engine/tests/test_projection_repository.py`

**Interfaces:**
- Consumes: `DecisionState` from Task 1, `ApprovalStatus` from Task 2.
- Produces: `DecisionProjection.status: DecisionState`; `Approval.status: ApprovalStatus`; `ProjectionRepository.advance_status(decision_id: str, status: DecisionState, updated_at: datetime) -> None`.

- [ ] **Step 1: Update `DecisionProjection`**

```python
# sentinel_engine/projections/decision_projection.py
"""Read-model contract representing a decision's current derived state."""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.domain.decision_state import DecisionState


@dataclass(frozen=True)
class DecisionProjection:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    evidence_reference: str
    risk_reference: str
    updated_at: datetime
```

- [ ] **Step 2: Update `Approval`**

```python
# sentinel_engine/governance/approval.py
"""Domain contract for human/system approval state on a decision."""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.governance.approval_status import ApprovalStatus


@dataclass(frozen=True)
class Approval:
    approval_id: str
    decision_id: str
    status: ApprovalStatus
    approved_by: str
    timestamp: datetime
```

- [ ] **Step 3: Update `ProjectionRepository.advance_status` type hint**

In `sentinel_engine/repositories/projection_repository.py`, change the signature (behavior unchanged — same `replace(existing, status=status, updated_at=updated_at)` body):

```python
    def advance_status(self, decision_id: str, status: DecisionState, updated_at: datetime) -> None:
```

and add the import at the top:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

- [ ] **Step 4: Update `sentinel_engine/tests/test_decision_projection.py`**

```python
# sentinel_engine/tests/test_decision_projection.py
"""Tests for sentinel_engine.projections.decision_projection.DecisionProjection."""
import datetime
import dataclasses

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection


def _make_projection(**overrides):
    defaults = dict(
        decision_id="dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


def test_decision_projection_can_be_created_with_required_fields():
    projection = _make_projection()
    assert projection.decision_id == "dec-001"
    assert projection.symbol == "AAPL"
    assert projection.action == "BUY"
    assert projection.status == DecisionState.DECISION_CREATED
    assert projection.confidence == 0.78
    assert projection.evidence_reference == "evidence-001"
    assert projection.risk_reference == "risk-001"
    assert projection.updated_at == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_decision_projection_is_a_dataclass():
    assert dataclasses.is_dataclass(DecisionProjection)


def test_decision_projection_is_immutable():
    projection = _make_projection()
    with pytest.raises(dataclasses.FrozenInstanceError):
        projection.status = DecisionState.APPROVAL_RECORDED


def test_decision_projection_requires_all_fields():
    with pytest.raises(TypeError):
        DecisionProjection(decision_id="dec-001", symbol="AAPL")
```

- [ ] **Step 5: Update `sentinel_engine/tests/test_approval.py`**

```python
# sentinel_engine/tests/test_approval.py
"""Tests for sentinel_engine.governance.approval.Approval."""
import datetime
import dataclasses

import pytest

from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus


def _make_approval(**overrides):
    defaults = dict(
        approval_id="apr-001",
        decision_id="dec-001",
        status=ApprovalStatus.APPROVED,
        approved_by="risk_officer",
        timestamp=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return Approval(**defaults)


def test_approval_can_be_created_with_required_fields():
    approval = _make_approval()
    assert approval.approval_id == "apr-001"
    assert approval.decision_id == "dec-001"
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approved_by == "risk_officer"
    assert approval.timestamp == datetime.datetime(2026, 8, 4, 12, 0, 0)


def test_approval_is_a_dataclass():
    assert dataclasses.is_dataclass(Approval)


def test_approval_is_immutable():
    approval = _make_approval()
    with pytest.raises(dataclasses.FrozenInstanceError):
        approval.status = ApprovalStatus.REJECTED


def test_approval_requires_all_fields():
    with pytest.raises(TypeError):
        Approval(approval_id="apr-001", decision_id="dec-001")
```

- [ ] **Step 6: Update `sentinel_engine/tests/test_projection_repository.py`**

```python
# sentinel_engine/tests/test_projection_repository.py
"""Tests for sentinel_engine.repositories.projection_repository.ProjectionRepository."""
import datetime

import pytest

from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.projections.decision_projection import DecisionProjection


def _make_projection(decision_id="dec-001", **overrides):
    defaults = dict(
        decision_id=decision_id,
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.78,
        evidence_reference="evidence-001",
        risk_reference="risk-001",
        updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
    )
    defaults.update(overrides)
    return DecisionProjection(**defaults)


class _InMemoryProjectionRepository(ProjectionRepository):
    """Minimal conforming implementation used only to exercise the contract."""

    def __init__(self):
        self._projections = {}

    def save(self, projection):
        self._projections[projection.decision_id] = projection

    def get(self, decision_id):
        return self._projections.get(decision_id)


def test_projection_repository_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ProjectionRepository()


def test_get_returns_none_when_projection_not_found():
    repository = _InMemoryProjectionRepository()

    assert repository.get("missing-decision") is None


def test_save_then_get_returns_the_saved_projection():
    repository = _InMemoryProjectionRepository()
    projection = _make_projection()

    repository.save(projection)

    assert repository.get("dec-001") == projection


def test_save_overwrites_the_projection_for_the_same_decision_id():
    repository = _InMemoryProjectionRepository()
    original = _make_projection(status=DecisionState.DECISION_CREATED)
    updated = _make_projection(status=DecisionState.APPROVAL_RECORDED)

    repository.save(original)
    repository.save(updated)

    assert repository.get("dec-001").status == DecisionState.APPROVAL_RECORDED


def test_incomplete_projection_repository_subclass_cannot_be_instantiated():
    class _Incomplete(ProjectionRepository):
        def save(self, projection):
            pass
        # get deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
```

- [ ] **Step 7: Run all three test files**

Run: `python -m pytest sentinel_engine/tests/test_decision_projection.py sentinel_engine/tests/test_approval.py sentinel_engine/tests/test_projection_repository.py -v`
Expected: all pass

---

## Task 4: Write-side services

**Files:**
- Modify: `sentinel_engine/services/decision_service.py`
- Modify: `sentinel_engine/services/evidence_service.py`
- Modify: `sentinel_engine/services/governance_service.py`
- Test: `sentinel_engine/tests/test_decision_service.py`
- Test: `sentinel_engine/tests/test_evidence_service.py`
- Test: `sentinel_engine/tests/test_governance_service.py`
- Test: `sentinel_engine/tests/test_sentinel_engine.py`
- Test: `sentinel_engine/tests/test_decision_lifecycle_integration.py`

**Interfaces:**
- Consumes: `DecisionState`, `ApprovalStatus` from Tasks 1-2; `DecisionProjection`/`Approval`/`ProjectionRepository.advance_status` from Task 3.
- Produces: no new interfaces -- same method signatures as today, now constructing `DecisionState`/`ApprovalStatus` members instead of `EventType(...).value` strings.

- [ ] **Step 1: Update `decision_service.py`**

In `sentinel_engine/services/decision_service.py`, add the import and change the projection construction:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

```python
        projection = DecisionProjection(
            decision_id=decision.decision_id,
            symbol=decision.symbol,
            action=decision.action,
            status=DecisionState.DECISION_CREATED,
            confidence=decision.confidence,
            evidence_reference=decision.evidence_reference,
            risk_reference=decision.risk_reference,
            updated_at=decision.timestamp,
        )
```

(The `Event(event_type=EventType.DECISION_CREATED, ...)` line above it is unchanged -- `EventType` still names the ledger event.)

- [ ] **Step 2: Update `evidence_service.py`**

Add the import and change the `advance_status` call:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

```python
        self._projection_repository.advance_status(
            decision_id, DecisionState.EVIDENCE_ATTACHED, evidence.collected_at,
        )
```

- [ ] **Step 3: Update `governance_service.py`**

Add the import:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

Change both `advance_status` calls:

```python
        self._projection_repository.advance_status(
            decision_id, DecisionState.GOVERNANCE_EVALUATED, evaluated_at,
        )
```

```python
        self._projection_repository.advance_status(
            approval.decision_id, DecisionState.APPROVAL_RECORDED, approval.timestamp,
        )
```

The `Event(... payload={"status": approval.status, ...})` line in `record_approval` is unchanged in code -- `approval.status` is now an `ApprovalStatus` member (typed via `Approval.status: ApprovalStatus` from Task 3), so the payload dict now legitimately holds a typed value instead of a bare string.

- [ ] **Step 4: Update `sentinel_engine/tests/test_decision_service.py`**

Add import `from sentinel_engine.domain.decision_state import DecisionState`, and change line 88:

```python
    assert projection.status == DecisionState.DECISION_CREATED
```

(replacing `assert projection.status == EventType.DECISION_CREATED.value`; the `EventType` import/usage elsewhere in this file for `event.event_type` assertions is untouched.)

- [ ] **Step 5: Update `sentinel_engine/tests/test_evidence_service.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. In `_make_projection`, change:

```python
        status=DecisionState.DECISION_CREATED,
```

And change the assertion:

```python
    assert projection.status == DecisionState.EVIDENCE_ATTACHED
```

(replacing `status=EventType.DECISION_CREATED.value` and `assert projection.status == EventType.EVIDENCE_ATTACHED.value` respectively.)

- [ ] **Step 6: Update `sentinel_engine/tests/test_governance_service.py`**

Add imports:

```python
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
```

In `_make_approval`, change:

```python
        status=ApprovalStatus.APPROVED,
```

In `_make_projection`, change:

```python
        status=DecisionState.DECISION_CREATED,
```

Change the three status-bearing assertions:

```python
    assert events[0].payload["status"] == ApprovalStatus.APPROVED
```

(line 135, inside `test_record_approval_writes_approval_recorded_event_with_correct_payload`)

```python
    assert projection.status == DecisionState.APPROVAL_RECORDED
```

(line 158, inside `test_record_approval_advances_projection_status_when_projection_exists`)

```python
    assert projection.status == DecisionState.GOVERNANCE_EVALUATED
```

(line 212, inside `test_evaluate_policy_advances_projection_status_when_projection_exists`)

- [ ] **Step 7: Update `sentinel_engine/tests/test_sentinel_engine.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` and `from sentinel_engine.governance.approval_status import ApprovalStatus`. In `_make_approval`, change `status="APPROVED"` to `status=ApprovalStatus.APPROVED`. Change line 113:

```python
    assert projection.status == DecisionState.DECISION_CREATED
```

- [ ] **Step 8: Update `sentinel_engine/tests/test_decision_lifecycle_integration.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` and `from sentinel_engine.governance.approval_status import ApprovalStatus`. Change the `Approval(...)` construction's `status="APPROVED"` to `status=ApprovalStatus.APPROVED`. Change the final assertion:

```python
    assert projection.status == DecisionState.APPROVAL_RECORDED
```

- [ ] **Step 9: Run all affected tests**

Run: `python -m pytest sentinel_engine/tests/test_decision_service.py sentinel_engine/tests/test_evidence_service.py sentinel_engine/tests/test_governance_service.py sentinel_engine/tests/test_sentinel_engine.py sentinel_engine/tests/test_decision_lifecycle_integration.py -v`
Expected: all pass

---

## Task 5: Read-side queries

**Files:**
- Modify: `sentinel_engine/queries/decision_query.py`
- Modify: `sentinel_engine/queries/decision_center_query.py`
- Modify: `sentinel_engine/queries/morning_brief_query.py`
- Test: `sentinel_engine/tests/test_decision_query.py`
- Test: `sentinel_engine/tests/test_decision_center_query.py`
- Test: `sentinel_engine/tests/test_morning_brief_query.py`

**Interfaces:**
- Consumes: `DecisionState`, `ApprovalStatus` (Tasks 1-2), typed `DecisionProjection`/`Approval` (Task 3).
- Produces: `DecisionTimeline.status: DecisionState`; `ApprovalSummary.status: ApprovalStatus`; `DecisionCenterView.lifecycle_status: DecisionState`; `RecentDecisionActivity.status: DecisionState`; `MorningBrief.decisions_by_status: Dict[DecisionState, int]`.

- [ ] **Step 1: Update `decision_query.py`**

Add import:

```python
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
```

Change the two dataclass field types:

```python
@dataclass(frozen=True)
class ApprovalSummary:
    approval_id: str
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime
```

```python
@dataclass(frozen=True)
class DecisionTimeline:
    decision_id: str
    status: DecisionState
    events: List[Event]
    evidence: List[EvidenceSummary]
    governance_evaluations: List[GovernanceEvaluationSummary]
    approvals: List[ApprovalSummary]
```

The construction code (`status=projection.status`, `status=event.payload["status"]`) is unchanged -- both already hold the correctly-typed enum member after Tasks 3-4.

- [ ] **Step 2: Update `decision_center_query.py`**

Add import:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

Change the dataclass field:

```python
@dataclass(frozen=True)
class DecisionCenterView:
    decision_id: str
    lifecycle_status: DecisionState
    symbol: Optional[str]
    action: Optional[str]
    evidence: List[EvidenceSummary]
    governance_evaluations: List[GovernanceEvaluationSummary]
    approvals: List[ApprovalSummary]
    timeline: List[Event]
```

- [ ] **Step 3: Update `morning_brief_query.py`**

Add import:

```python
from sentinel_engine.domain.decision_state import DecisionState
```

Change the module-level tuple and dataclass fields:

```python
_STATUSES_PAST_GOVERNANCE = (
    DecisionState.GOVERNANCE_EVALUATED,
    DecisionState.APPROVAL_RECORDED,
)


@dataclass(frozen=True)
class RecentDecisionActivity:
    decision_id: str
    status: DecisionState
    last_activity_at: datetime


@dataclass(frozen=True)
class MorningBrief:
    total_decisions: int
    decisions_by_status: Dict[DecisionState, int]
    recent_decisions: List[RecentDecisionActivity]
    pending_governance_count: int
    pending_approval_count: int
    latest_activity_timestamp: Optional[datetime]
```

Change the `Dict` import at the top if not already present (it already is: `from typing import Dict, List, Optional`). Change one comparison inside `get_brief()`:

```python
            if status != DecisionState.APPROVAL_RECORDED:
```

(replacing `if status != EventType.APPROVAL_RECORDED.value:`; the `EventType` import at the top of this file becomes unused and must be removed).

- [ ] **Step 4: Update `sentinel_engine/tests/test_decision_query.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` and `from sentinel_engine.governance.approval_status import ApprovalStatus`. In `_make_approval`, change `status="APPROVED"` to `status=ApprovalStatus.APPROVED`. Change:

```python
    assert timeline.status == DecisionState.APPROVAL_RECORDED
```

(line 130) and

```python
    assert timeline.approvals[0].status == ApprovalStatus.APPROVED
```

(line 151). In `test_get_decision_timeline_orders_events_by_created_at_not_append_order`, change the `DecisionProjection(...)` construction's `status=EventType.EVIDENCE_ATTACHED.value` to `status=DecisionState.EVIDENCE_ATTACHED`.

- [ ] **Step 5: Update `sentinel_engine/tests/test_decision_center_query.py`**

Same pattern as Step 4: add both imports, `_make_approval`'s `status=ApprovalStatus.APPROVED`, change line 130 to `assert view.lifecycle_status == DecisionState.APPROVAL_RECORDED`, line 153 to `assert view.approvals[0].status == ApprovalStatus.APPROVED`, and the `DecisionProjection(...)` in `test_get_decision_center_orders_timeline_by_created_at_not_append_order` to `status=DecisionState.EVIDENCE_ATTACHED`.

- [ ] **Step 6: Update `sentinel_engine/tests/test_morning_brief_query.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` and `from sentinel_engine.governance.approval_status import ApprovalStatus`. In `_make_approval`, change `status="APPROVED"` to `status=ApprovalStatus.APPROVED`. Change every `DecisionProjection(..., status=EventType.DECISION_CREATED.value, ...)` construction (two occurrences, in `test_get_brief_orders_recent_activity_by_created_at_not_insertion_order`) to `status=DecisionState.DECISION_CREATED`. Change the three `decisions_by_status` dict-literal assertions:

```python
    assert brief.decisions_by_status == {
        DecisionState.DECISION_CREATED: 1,
        DecisionState.EVIDENCE_ATTACHED: 1,
        DecisionState.GOVERNANCE_EVALUATED: 1,
        DecisionState.APPROVAL_RECORDED: 1,
    }
```

(line 148), 

```python
    assert brief.decisions_by_status == {DecisionState.DECISION_CREATED: 1}
```

(line 252), and

```python
    assert brief.decisions_by_status == {
        DecisionState.DECISION_CREATED: 1,
        DecisionState.APPROVAL_RECORDED: 1,
    }
```

(line 276-279).

- [ ] **Step 7: Run all affected tests**

Run: `python -m pytest sentinel_engine/tests/test_decision_query.py sentinel_engine/tests/test_decision_center_query.py sentinel_engine/tests/test_morning_brief_query.py -v`
Expected: all pass

---

## Task 6: Presentation layer

**Files:**
- Modify: `sentinel_engine/presentation/investor_presenter.py`
- Test: `sentinel_engine/tests/test_investor_presenter.py`

**Interfaces:**
- Consumes: `DecisionState`, `ApprovalStatus` (Tasks 1-2); `MorningBrief`/`DecisionCenterView` (Task 5).
- Produces: `RecentActivityRow.status: DecisionState`; `MorningBriefView.status_summary: Dict[DecisionState, int]`; `ApprovalSummaryRow.status: ApprovalStatus`; `DecisionCenterViewModel.lifecycle_status: DecisionState`.

- [ ] **Step 1: Update `investor_presenter.py`**

Add import:

```python
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
```

Change field types on four dataclasses (construction code is unchanged -- pure passthrough):

```python
@dataclass(frozen=True)
class RecentActivityRow:
    decision_id: str
    status: DecisionState
    last_activity_at: datetime


@dataclass(frozen=True)
class MorningBriefView:
    total_decisions: int
    status_summary: Dict[DecisionState, int]
    recent_activity_rows: List[RecentActivityRow]
```

```python
@dataclass(frozen=True)
class ApprovalSummaryRow:
    approval_id: str
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime
```

```python
@dataclass(frozen=True)
class DecisionCenterViewModel:
    decision_id: str
    lifecycle_status: DecisionState
    symbol: Optional[str]
    action: Optional[str]
    evidence_rows: List[EvidenceRow]
    governance_summary: Optional[GovernanceSummaryRow]
    approval_summary: Optional[ApprovalSummaryRow]
    timeline_rows: List[TimelineRow]
```

- [ ] **Step 2: Update `sentinel_engine/tests/test_investor_presenter.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` and `from sentinel_engine.governance.approval_status import ApprovalStatus`. This file uses hand-rolled fake classes (`_MorningBrief`, `_DecisionCenterView`, etc.) that duck-type the real query-layer objects, so only the literal values passed into them need updating, not their class definitions. Change:

```python
    brief = _MorningBrief(
        total_decisions=3,
        decisions_by_status={DecisionState.DECISION_CREATED: 1, DecisionState.APPROVAL_RECORDED: 2},
        recent_decisions=[_RecentDecisionActivity("dec-001", DecisionState.APPROVAL_RECORDED, now)],
    )
```

(replacing the `"DECISION_CREATED"`/`"APPROVAL_RECORDED"` string literals at lines 101-102), and

```python
    assert view.status_summary == {DecisionState.DECISION_CREATED: 1, DecisionState.APPROVAL_RECORDED: 2}
    assert len(view.recent_activity_rows) == 1
    assert view.recent_activity_rows[0].decision_id == "dec-001"
    assert view.recent_activity_rows[0].status == DecisionState.APPROVAL_RECORDED
```

(lines 112, 115). In `test_get_decision_center_view_passes_decision_id_and_maps_fields`, change:

```python
        lifecycle_status=DecisionState.APPROVAL_RECORDED,
```

(line 127), the `_ApprovalSummary("apr-001", ApprovalStatus.APPROVED, "risk_officer", approved_at)` construction (line 137), and the assertions:

```python
    assert view.lifecycle_status == DecisionState.APPROVAL_RECORDED
```

(line 154) and

```python
    assert view.approval_summary.status == ApprovalStatus.APPROVED
```

(line 171). The `_TimelineEvent("DECISION_CREATED", ...)` calls and `timeline_rows[i].event_type` assertions (lines 140-143, 176-181) stay as plain strings unchanged -- `TimelineRow.event_type` carries `EventType.value` (a plain `str`, per `investor_presenter.py`'s `event.event_type.value`), not `DecisionState`, so it is out of this task's scope.

- [ ] **Step 3: Run the test**

Run: `python -m pytest sentinel_engine/tests/test_investor_presenter.py -v`
Expected: all pass

---

## Task 7: Trading Intelligence contract/projection layer

**Files:**
- Modify: `applications/trading_intelligence/contracts/decision_contract.py`
- Modify: `applications/trading_intelligence/projections/decision_view.py`
- Test: `applications/trading_intelligence/tests/test_decision_contract.py`
- Test: `applications/trading_intelligence/tests/test_decision_view.py`
- Test: `applications/trading_intelligence/tests/test_decision_query_service.py`
- Test: `applications/trading_intelligence/tests/test_sentinel_projection_decision_source.py`

**Interfaces:**
- Consumes: `DecisionState` (Task 1), imported directly from `sentinel_engine.domain.decision_state` (confirmed safe: `applications/trading_intelligence/tests/test_package_imports.py`'s package-wide boundary scan only forbids `bot`/`dashboard`/`scheduler`/`database`/`ledger`, not `sentinel_engine`, for this package).
- Produces: `DecisionContract.status: DecisionState`; `DecisionView.status: DecisionState`; and `decision_view.py` re-exports the `DecisionState` name for Task 8's `mock_data.py` to import from (since `mock_data.py` itself cannot import `sentinel_engine` directly).

- [ ] **Step 1: Update `decision_contract.py`**

```python
# applications/trading_intelligence/contracts/decision_contract.py
"""Trading Intelligence's own decision contract -- the future Trading
Intelligence decision view.

Framework-independent: no bot, dashboard, scheduler, database, or ledger
import. Distinct from sentinel_engine.projections.DecisionProjection -- this
is Trading Intelligence's own contract, not a re-export of Sentinel's, per
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's ownership split
("Trading Intelligence owns: product views"). status is typed against the
shared DecisionState enum (sentinel_engine.domain.decision_state) since that
enum is the canonical vocabulary for "where a decision is in its lifecycle"
across every consumer -- duplicating it here would defeat the point of a
single typed source of truth for lifecycle state.
"""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.domain.decision_state import DecisionState


@dataclass(frozen=True)
class DecisionContract:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    evidence_reference: str
    risk_reference: str
    updated_at: datetime
```

- [ ] **Step 2: Update `decision_view.py`**

```python
# applications/trading_intelligence/projections/decision_view.py
"""Trading Intelligence's decision read model -- no persistence, no database.

Represents the "Trading Intelligence Projection" stage in
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's read flow (Sentinel
Projection -> Reader Contract -> Trading Intelligence Projection -> UI).

Deliberately narrower than DecisionContract: evidence_reference/risk_reference
are internal pointers a decision-list view doesn't display directly (per
AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md, evidence and risk are shown by
separate evidence panels/risk indicators, not embedded in the decision card).

DecisionState is imported (and therefore re-exported) here so that
ui/decision_center/mock_data.py -- which is forbidden from importing
sentinel_engine directly (see applications/trading_intelligence/ui/tests/
test_ui_structure.py) -- can obtain it via this module instead.
"""
from dataclasses import dataclass
from datetime import datetime

from sentinel_engine.domain.decision_state import DecisionState

from applications.trading_intelligence.contracts.decision_contract import DecisionContract


@dataclass(frozen=True)
class DecisionView:
    decision_id: str
    symbol: str
    action: str
    status: DecisionState
    confidence: float
    updated_at: datetime

    @classmethod
    def from_contract(cls, contract: DecisionContract) -> "DecisionView":
        return cls(
            decision_id=contract.decision_id,
            symbol=contract.symbol,
            action=contract.action,
            status=contract.status,
            confidence=contract.confidence,
            updated_at=contract.updated_at,
        )
```

- [ ] **Step 3: Update `applications/trading_intelligence/tests/test_decision_contract.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. In `_make_contract`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. Change the assertion `assert contract.status == DecisionState.DECISION_CREATED` (line 30), and the immutability test's assignment to `contract.status = DecisionState.APPROVAL_RECORDED` (line 44, replacing the excluded `"DECISION_EXECUTED"`).

- [ ] **Step 4: Update `applications/trading_intelligence/tests/test_decision_view.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. In `_make_contract`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. Change the immutability test's assignment `view.status = DecisionState.APPROVAL_RECORDED` (line 33, replacing the excluded `"DECISION_EXECUTED"`), and `assert view.status == DecisionState.DECISION_CREATED` (line 44).

- [ ] **Step 5: Update `applications/trading_intelligence/tests/test_decision_query_service.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. In `_make_contract`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. Change `assert view.status == DecisionState.DECISION_CREATED` (line 63).

- [ ] **Step 6: Update `applications/trading_intelligence/tests/test_sentinel_projection_decision_source.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. In `_make_projection`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. Change `assert result.status == DecisionState.DECISION_CREATED` (line 74).

- [ ] **Step 7: Run all four test files**

Run: `python -m pytest applications/trading_intelligence/tests/test_decision_contract.py applications/trading_intelligence/tests/test_decision_view.py applications/trading_intelligence/tests/test_decision_query_service.py applications/trading_intelligence/tests/test_sentinel_projection_decision_source.py -v`
Expected: all pass

---

## Task 8: Trading Intelligence UI layer (mock data + integration tests)

**Files:**
- Modify: `applications/trading_intelligence/ui/decision_center/mock_data.py`
- Test: `applications/trading_intelligence/ui/tests/test_decision_center_screen.py`
- Test: `applications/trading_intelligence/ui/tests/test_decision_center_controller.py`
- Test: `applications/trading_intelligence/ui/tests/test_decision_center_mock_data.py`
- Test: `applications/trading_intelligence/tests/test_decision_center_integration.py`
- Test: `applications/trading_intelligence/tests/fakes.py` (no change expected -- verify only)
- Test: `applications/platform/tests/test_trading_intelligence_product_integration.py`

**Interfaces:**
- Consumes: `DecisionState` re-exported from `applications.trading_intelligence.projections.decision_view` (Task 7) -- never imported directly from `sentinel_engine` inside anything under `ui/`.

- [ ] **Step 1: Update `mock_data.py`**

```python
# applications/trading_intelligence/ui/decision_center/mock_data.py
"""Mock data provider for Decision Center V1.

No real service wiring, no sentinel_engine/bot/dashboard/database/ledger
import -- hardcoded DecisionView objects only, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md Section 8,
Phase 1 ("Mock UI: hardcoded DecisionView objects, no real service wiring").
Not connected to DecisionQueryService or any Sentinel Engine data.

DecisionState is imported from applications.trading_intelligence.projections.
decision_view (which already depends on it for DecisionView.status), not
from sentinel_engine directly -- this file is forbidden from importing
sentinel_engine by applications/trading_intelligence/ui/tests/
test_ui_structure.py, and importing the enum through decision_view.py
respects that boundary while still using a real, valid lifecycle state
(mock statuses must be DecisionState members now, not arbitrary strings --
see this plan's global constraints for why "QUALIFIED_REJECTION" and
"DECISION_EXECUTED" were replaced).
"""
import datetime
from typing import List

from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionCenterScreen,
    DecisionDetailArea,
    DecisionListArea,
)

_MOCK_DECISIONS = [
    DecisionView(
        decision_id="mock-dec-001",
        symbol="AAPL",
        action="BUY",
        status=DecisionState.DECISION_CREATED,
        confidence=0.82,
        updated_at=datetime.datetime(2026, 8, 4, 9, 35, 0),
    ),
    DecisionView(
        decision_id="mock-dec-002",
        symbol="MSFT",
        action="HOLD",
        status=DecisionState.GOVERNANCE_EVALUATED,
        confidence=0.54,
        updated_at=datetime.datetime(2026, 8, 4, 9, 40, 0),
    ),
    DecisionView(
        decision_id="mock-dec-003",
        symbol="NVDA",
        action="SELL",
        status=DecisionState.APPROVAL_RECORDED,
        confidence=0.91,
        updated_at=datetime.datetime(2026, 8, 4, 10, 15, 0),
    ),
]


def get_mock_decisions() -> List[DecisionView]:
    return list(_MOCK_DECISIONS)


def build_mock_screen() -> DecisionCenterScreen:
    decisions = get_mock_decisions()
    selected = decisions[0] if decisions else None
    return DecisionCenterScreen(
        list_area=DecisionListArea(decisions=decisions),
        detail_area=DecisionDetailArea(decision=selected),
    )
```

- [ ] **Step 2: Update `applications/trading_intelligence/ui/tests/test_decision_center_screen.py`**

Add `from applications.trading_intelligence.projections.decision_view import DecisionState, DecisionView`. In `_make_view`, change the default `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. There is exactly one explicit-override call site to update, in `test_decision_detail_area_formats_status_as_title_case_words`:

```python
def test_decision_detail_area_formats_status_as_title_case_words():
    area = DecisionDetailArea(decision=_make_view(status=DecisionState.DECISION_CREATED))

    assert area.status_display == "Decision Created"
```

(line 64; value unchanged since it was already `DECISION_CREATED`). `status_display` itself needs zero code change since `.replace("_", " ").title()` works identically on a `(str, Enum)` member.

- [ ] **Step 3: Update `applications/trading_intelligence/ui/tests/test_decision_center_controller.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState`. Wait -- this file is under `ui/tests/`, so it is also bound by the "no direct `sentinel_engine` import" rule. Import from the re-export instead:

```python
from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.projections.decision_view import DecisionState
```

In `_make_contract`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`.

- [ ] **Step 4: Update `applications/trading_intelligence/ui/tests/test_decision_center_mock_data.py`**

No status-literal changes needed -- this file only asserts `view.status` is truthy (`assert view.status`) and structural properties, never a literal string. Verify it still passes unchanged; no edit required unless the test run in Step 6 shows otherwise.

- [ ] **Step 5: Update `applications/trading_intelligence/tests/test_decision_center_integration.py`**

This file is NOT under `ui/`, so it already imports `sentinel_engine.projections.decision_projection.DecisionProjection` directly (unchanged) -- add `from sentinel_engine.domain.decision_state import DecisionState` alongside it. In `_make_projection`, change `status="DECISION_CREATED"` to `status=DecisionState.DECISION_CREATED`. In `test_controller_produces_a_correctly_formatted_screen_model_from_real_projection_data`, change the explicit `status="DECISION_CREATED"` override (line 124) to `status=DecisionState.DECISION_CREATED`.

- [ ] **Step 6: Update `applications/platform/tests/test_trading_intelligence_product_integration.py`**

Add `from sentinel_engine.domain.decision_state import DecisionState` near its existing `DecisionProjection` import. Change both `status="DECISION_CREATED"` occurrences (lines 216 and 250) to `status=DecisionState.DECISION_CREATED`. This file already imports `sentinel_engine` and `applications.trading_intelligence` internals directly (confirmed by its own `test_module_does_not_import_forbidden_runtimes` test, which only forbids `bot`/`dashboard`/`scheduler`/`ledger`/`database` -- not `sentinel_engine`), so this is a plain, unrestricted import.

- [ ] **Step 7: Run every file touched in this task**

Run: `python -m pytest applications/trading_intelligence/ui/tests/ applications/trading_intelligence/tests/test_decision_center_integration.py applications/platform/tests/test_trading_intelligence_product_integration.py -v`
Expected: all pass, including the pre-existing `test_ui_structure.py` boundary tests (proving the re-export approach didn't introduce a forbidden import).

---

## Task 9: Full-suite verification and single commit

**Files:** none (verification + commit only).

- [ ] **Step 1: Run the complete affected test surface**

Run:
```
python -m pytest sentinel_engine/ applications/trading_intelligence/ applications/wealth_intelligence/ applications/platform/ -v
```
Expected: 0 failures. Pay particular attention to:
- `applications/wealth_intelligence/ui/tests/test_investor_workspace.py` (uses `sentinel_engine.presentation.investor_presenter` dataclasses directly with string literals in `_make_morning_brief_view`/`_make_decision_center_view` -- these will still pass unmodified because `DecisionState`/`ApprovalStatus` inherit from `str`, so `"APPROVAL_RECORDED" == DecisionState.APPROVAL_RECORDED` is `True` and Gradio row-building code (`str(count)`, list literals) is unaffected. No edits planned for this file; if this run surfaces an unexpected failure here, stop and investigate before proceeding -- it would mean the str-Enum equivalence assumption this whole plan relies on doesn't hold somewhere.
- `sentinel_engine/tests/test_ledger.py`, `test_ledger_repository.py`, `test_event_types.py` -- untouched by this plan; run them as a regression check only.

- [ ] **Step 2: Run ruff/lint if configured**

Run: `ruff check sentinel_engine/ applications/trading_intelligence/ applications/wealth_intelligence/ applications/platform/` (per this repo's `ruff --select F821` regression-test precedent). Fix any unused-import findings (e.g., confirm `EventType` was actually removed from `morning_brief_query.py`'s imports in Task 5, not just unused).

- [ ] **Step 3: Review the full diff**

Run: `git status` and `git diff --stat` to confirm only the files listed in this plan's File Map changed, and that nothing under `bot/`, `dashboard/`, `scheduler/`, `.github/workflows/`, `database/`, `ledger/` appears.

- [ ] **Step 4: Stage and commit**

```bash
git add sentinel_engine/domain/decision_state.py sentinel_engine/governance/approval_status.py \
  sentinel_engine/tests/test_decision_state.py sentinel_engine/tests/test_approval_status.py \
  sentinel_engine/projections/decision_projection.py sentinel_engine/governance/approval.py \
  sentinel_engine/repositories/projection_repository.py \
  sentinel_engine/services/decision_service.py sentinel_engine/services/evidence_service.py \
  sentinel_engine/services/governance_service.py \
  sentinel_engine/queries/decision_query.py sentinel_engine/queries/decision_center_query.py \
  sentinel_engine/queries/morning_brief_query.py sentinel_engine/presentation/investor_presenter.py \
  applications/trading_intelligence/contracts/decision_contract.py \
  applications/trading_intelligence/projections/decision_view.py \
  applications/trading_intelligence/ui/decision_center/mock_data.py \
  sentinel_engine/tests/ applications/trading_intelligence/tests/ applications/trading_intelligence/ui/tests/ \
  applications/platform/tests/test_trading_intelligence_product_integration.py

git commit -m "$(cat <<'EOF'
Replace string-based decision lifecycle status with DecisionState enum

Adds DecisionState (4 reachable lifecycle states) and ApprovalStatus
(governance verdict) as (str, Enum) types alongside the existing
EventType pattern, and threads them through every projection, contract,
query, presenter, and mock-data construction site that previously held
a raw status string. Zero behavior change: str-Enum inheritance keeps
every existing comparison, dict key, and string-formatting call working
unmodified.
EOF
)"
```

- [ ] **Step 5: Confirm**

Run: `git status` -- expect a clean tree with the new commit on top.

---

## Self-Review Notes (for whoever executes this plan)

- **Spec coverage:** every bullet in the user's four numbered clarifications maps to a task: (1) `DecisionState` scope -> Task 1 + global constraints; (2) `ApprovalStatus` -> Task 2; (3) `mock_data.py` fix -> Task 8 Step 1; (4) scope constraints (no new transitions/execution/persistence/CQRS changes) -> verified file-by-file across Tasks 3-8, and explicitly confirmed no concrete persistence adapter exists yet to accidentally touch.
- **Two decisions made without a fourth round of clarifying questions**, flagged in Global Constraints and worth a quick nod from the user when reviewing the diff: (a) `decision_contract.py`/`decision_view.py` import `DecisionState` directly from `sentinel_engine.domain` (single canonical enum, not a duplicated local one) since the user's file list named both as update targets; (b) `mock_data.py`'s third entry (`"DECISION_EXECUTED"`) gets the same `QUALIFIED_REJECTION`-style swap to `DecisionState.APPROVAL_RECORDED`, by direct extension of the already-approved reasoning, since it has the identical problem (a fictional/unreachable state) that the user only happened to name one instance of.
