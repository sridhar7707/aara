"""Phase 2 scaffolding (phase2_requirements.md Section 3.5): Model Experiment
Framework interface. Intended to replay model_outputs already stored in
decision_events against a candidate model-weight change, producing a
counterfactual win rate / return / calibration delta -- without ever writing
to decision_events, model_training_runs, or any production table (Section 5
acceptance criterion).

Not wired into any pipeline -- see analytics/regime_views.py's module
docstring for the same gating note. The counterfactual replay itself is
deliberately left unimplemented: it depends on the exact reweighting
recommendation format Phase 1B produces (phase1b_requirements.md Section 5),
which does not exist yet. Implementing the math now would mean guessing that
format instead of building it from real evidence.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

_log = logging.getLogger("tradegenie.analytics.experiments")


@dataclass
class Experiment:
    name: str
    model_weight_overrides: dict[str, float]
    decision_window_days: int = 30


@dataclass
class ExperimentResult:
    experiment: Experiment
    decisions_replayed: int
    counterfactual_win_rate: float
    production_win_rate: float
    counterfactual_avg_return: float
    production_avg_return: float


def run_experiment(conn: sqlite3.Connection, experiment: Experiment) -> ExperimentResult:
    """Replay `experiment` against `decision_window_days` of decision_events,
    read-only, and compare to the production outcomes already recorded.

    Raises NotImplementedError until Phase 1B defines the reweighting
    recommendation format this needs to replay against.
    """
    raise NotImplementedError(
        "Model Experiment Framework counterfactual replay is scaffolded, not "
        "implemented -- needs Phase 1B's reweighting recommendation format "
        "(phase1b_requirements.md Section 5) and real accumulated "
        "decision_events history, neither of which exist yet "
        "(phase2_requirements.md Gate)."
    )
