"""Regression guard for ADR-052 — retrain.yml's backtest quality gate must be
fatal (no continue-on-error), so a failed model-quality gate blocks the
subsequent HuggingFace push. Parses the workflow file structurally; does not
invoke GitHub Actions or scripts/backtest_gate.py itself.
"""
from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "retrain.yml"


@pytest.fixture(scope="module")
def retrain_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["retrain"]["steps"]


def _find_step(steps: list[dict], name: str) -> dict:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"Step {name!r} not found in retrain.yml's retrain job")


def test_backtest_quality_gate_step_exists(retrain_steps):
    _find_step(retrain_steps, "Backtest quality gate")


def test_backtest_quality_gate_has_no_continue_on_error(retrain_steps):
    step = _find_step(retrain_steps, "Backtest quality gate")
    assert "continue-on-error" not in step, (
        "Backtest quality gate' step must not set continue-on-error — a "
        "failed gate must fail the job and block the HuggingFace push "
        "(ADR-052)."
    )


def test_push_model_to_huggingface_step_exists(retrain_steps):
    _find_step(retrain_steps, "Push model to HuggingFace")


def test_push_model_to_huggingface_has_no_if_condition(retrain_steps):
    step = _find_step(retrain_steps, "Push model to HuggingFace")
    assert "if" not in step, (
        "Push model to HuggingFace' step must rely on GitHub Actions' "
        "implicit default if: success() — an explicit if: condition is not "
        "authorized by ADR-052."
    )


@pytest.mark.parametrize("step_name", [
    "Model quality alert",
    "Pull trade database from HuggingFace",
    "Send weekly report",
])
def test_notification_steps_remain_if_always(retrain_steps, step_name):
    step = _find_step(retrain_steps, step_name)
    assert step.get("if") == "always()", (
        f"{step_name!r} step must keep if: always() unchanged (ADR-052 "
        "does not authorize modifying it)."
    )
