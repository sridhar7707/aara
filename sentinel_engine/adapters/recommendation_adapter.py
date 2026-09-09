"""ADR-069 (B2) -- the first Sentinel-authored investment recommendation.

A pure, deterministic seam, equivalent in responsibility to B1's
evidence_adapter._polarity_for_signal: it reads only the three existing
MODEL_OUTPUT `signal` strings already present in `model_outputs` and returns
the `action` / `action_source` the pre-gate causal Decision (ADR-067) is born
with.

Candidate A -- three-model unanimity -- is the sole authorized rule
(ADR-069 SS5.3, SS5.5):

    xgboost signal == "BUY" AND lstm signal == "BUY" AND finbert signal == "BUY"
        -> ("BUY",  "SENTINEL")      Sentinel concurs
    every other case                 any "SELL", any "HOLD", missing / empty /
        -> ("WAIT", "SENTINEL")      unrecognised signal -- exhaustive

`action_source` is always "SENTINEL": B2 authored the value either way.

This module has zero bot import; it reads nothing but the three signal
strings; it computes exactly one three-input AND; it exposes no threshold,
weight, score, count, or configuration; it constructs no Evidence and no
Decision; it mutates `model_outputs` nowhere; it persists nothing; it
calculates no confidence. It is not a general-purpose action generator and is
invoked only from EntryDecisionRecorder.__init__() on the existing
upstream-BUY entry path (ADR-069 SS4.1, SS13.2). A different rule -- a
threshold, a weighting, an added model, majority/partial-support -- would
require its own subsequent ADR in this lineage.
"""
from __future__ import annotations

from sentinel_engine.domain.action_source import ActionSource
from sentinel_engine.domain.decision_action import DecisionAction

_REQUIRED_MODELS = ("xgboost", "lstm", "finbert")
_CONCUR_SIGNAL = "BUY"


def _signal_of(model_outputs: dict, model: str) -> object:
    """The model's already-computed directional signal string, or None if it
    is absent or the entry is malformed. Never raises on a missing key or a
    non-dict entry -- an unavailable signal is simply not "BUY", so it yields
    WAIT (ADR-069 SS5.3: missing / empty / unrecognised -> WAIT)."""
    try:
        return model_outputs[model]["signal"]
    except (KeyError, TypeError, IndexError):
        return None


def recommend_entry_action(model_outputs: dict) -> tuple[str, str]:
    """ADR-069 SS5.3 Candidate A. Returns ``(action, action_source)``.

    `action` is ``DecisionAction.BUY`` iff all three MODEL_OUTPUT signals are
    exactly ``"BUY"``; otherwise ``DecisionAction.WAIT`` (inert abstention).
    `action_source` is always ``ActionSource.SENTINEL``.
    """
    unanimous_buy = all(
        _signal_of(model_outputs, model) == _CONCUR_SIGNAL
        for model in _REQUIRED_MODELS
    )
    action = DecisionAction.BUY if unanimous_buy else DecisionAction.WAIT
    return action.value, ActionSource.SENTINEL.value
