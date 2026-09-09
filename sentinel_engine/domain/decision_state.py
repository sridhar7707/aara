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
CANDIDATE_EVALUATED, RISK_EVALUATED, or DECISION_OUTCOME_RECORDED until an
actual service path transitions a decision into one of them.

Batch 4 attempted to add DECISION_EXECUTED, backed by a real producer
(a paper-execution gateway) -- and then removed both, on discovering the
gateway could not legally exist anywhere that produces it: it needed to
import bot.execution/bot.risk, which sentinel_engine's own ADR-001
independence boundary (enforced by
sentinel_engine/tests/test_package_imports.py) and
applications/trading_intelligence's equivalent boundary both forbid, and
duplicating the primitive independently was separately out of scope.

ADR-065 (Accepted) resolved this by authorizing a producer that stays on
the correct side of the boundary: bot/_main_cycle.py::_handle_entry()
reports an already-completed execution outcome to
sentinel_engine/adapters/execution_adapter.py (zero bot import), which
DecisionService.record_execution() persists as a DECISION_EXECUTED event
and advances the projection to this state. DECISION_EXECUTED is therefore
now a real, additively-introduced terminal state -- both a successful fill
and a rejected/failed execution attempt advance to it, distinguished by the
event payload's "outcome" field (ADR-065 SS3.1), not by separate states.
"""
from enum import Enum


class DecisionState(str, Enum):
    DECISION_CREATED = "DECISION_CREATED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    GOVERNANCE_EVALUATED = "GOVERNANCE_EVALUATED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"
    DECISION_EXECUTED = "DECISION_EXECUTED"

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
