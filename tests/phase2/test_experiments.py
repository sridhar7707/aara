"""Tests for analytics/experiments.py (Phase 2 scaffolding).

run_experiment is expected to raise NotImplementedError until Phase 1B
defines the reweighting recommendation format -- this test locks in that the
interface exists and fails loudly (not silently) rather than pretending to
compute a real result.
"""
from __future__ import annotations

import pytest

from analytics.experiments import Experiment, ExperimentResult, run_experiment


def test_experiment_dataclass_defaults():
    experiment = Experiment(name="reduce_finbert_weight", model_weight_overrides={"finbert": 0.85})
    assert experiment.decision_window_days == 30


def test_run_experiment_not_yet_implemented(conn):
    experiment = Experiment(name="reduce_finbert_weight", model_weight_overrides={"finbert": 0.85})
    with pytest.raises(NotImplementedError):
        run_experiment(conn, experiment)


def test_experiment_result_is_a_dataclass_with_expected_fields():
    field_names = set(ExperimentResult.__dataclass_fields__)
    assert field_names == {
        "experiment", "decisions_replayed", "counterfactual_win_rate",
        "production_win_rate", "counterfactual_avg_return", "production_avg_return",
    }
