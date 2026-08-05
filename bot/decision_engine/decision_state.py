from enum import Enum


class DecisionState(Enum):
    OBSERVED = "OBSERVED"
    EVALUATING = "EVALUATING"
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class InvalidStateTransitionError(ValueError):
    pass


# EXECUTED is a lifecycle state only. It is never a value in this map's
# transition sets — Decision Intelligence has no path to reach it; only a
# system outside this package (the execution layer) can record it.
_ALLOWED_TRANSITIONS = {
    DecisionState.OBSERVED: {DecisionState.EVALUATING},
    DecisionState.EVALUATING: {DecisionState.RECOMMENDED, DecisionState.REJECTED},
    DecisionState.RECOMMENDED: {DecisionState.APPROVED, DecisionState.REJECTED},
    DecisionState.APPROVED: set(),
    DecisionState.REJECTED: set(),
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
