from enum import Enum


class DecisionState(Enum):
    OBSERVED = "OBSERVED"
    EVALUATING = "EVALUATING"
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXECUTED = "EXECUTED"


class InvalidStateTransitionError(ValueError):
    pass


# EXECUTED is a lifecycle state only. It is never a value in this map's
# transition sets — Decision Intelligence has no path to reach it; only a
# system outside this package (the execution layer) can record it.
#
# INSUFFICIENT_EVIDENCE is a terminal state distinct from REJECTED: REJECTED
# means a candidate was evaluated and voted down (by this engine or, via the
# RECOMMENDED -> REJECTED edge, by an external risk/governance decision).
# INSUFFICIENT_EVIDENCE means the engine had nothing to evaluate at all. They
# must not be conflated once decision_log starts persisting `state`, or an
# audit query for "signals the risk layer vetoed" would silently also match
# "signals we never got evidence for" -- a different failure mode entirely.
_ALLOWED_TRANSITIONS = {
    DecisionState.OBSERVED: {DecisionState.EVALUATING},
    DecisionState.EVALUATING: {
        DecisionState.RECOMMENDED,
        DecisionState.REJECTED,
        DecisionState.INSUFFICIENT_EVIDENCE,
    },
    DecisionState.RECOMMENDED: {DecisionState.APPROVED, DecisionState.REJECTED},
    DecisionState.APPROVED: set(),
    DecisionState.REJECTED: set(),
    DecisionState.INSUFFICIENT_EVIDENCE: set(),
    DecisionState.EXECUTED: set(),
}


def transition(current: DecisionState, target: DecisionState) -> DecisionState:
    if target is DecisionState.EXECUTED:
        raise InvalidStateTransitionError(
            "Decision Intelligence cannot transition a decision to EXECUTED"
        )
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidStateTransitionError(f"Cannot transition from {current} to {target}")
    return target
