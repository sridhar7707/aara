"""Tests for applications.platform.workspaces.workspace.Workspace."""
import dataclasses

import pytest

from applications.platform.workspaces.workspace import Workspace


def _make_workspace(**overrides):
    defaults = dict(
        workspace_id="trading_intelligence.decision_center",
        product_id="trading_intelligence",
        display_name="Decision Center",
        visibility="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return Workspace(**defaults)


def test_workspace_can_be_created_with_required_fields():
    workspace = _make_workspace()

    assert workspace.workspace_id == "trading_intelligence.decision_center"
    assert workspace.product_id == "trading_intelligence"
    assert workspace.display_name == "Decision Center"
    assert workspace.visibility == "TRADING_INTELLIGENCE"


def test_workspace_is_a_dataclass():
    assert dataclasses.is_dataclass(Workspace)


def test_workspace_is_immutable():
    workspace = _make_workspace()
    with pytest.raises(dataclasses.FrozenInstanceError):
        workspace.display_name = "Something Else"


def test_workspace_requires_visibility():
    with pytest.raises(TypeError):
        Workspace(
            workspace_id="trading_intelligence.decision_center",
            product_id="trading_intelligence",
            display_name="Decision Center",
        )


def test_workspace_description_defaults_to_empty_string():
    workspace = _make_workspace()

    assert workspace.description == ""


def test_workspace_order_defaults_to_zero():
    workspace = _make_workspace()

    assert workspace.order == 0


def test_workspace_accepts_explicit_description_and_order():
    workspace = _make_workspace(description="Reviews AI trading decisions.", order=1)

    assert workspace.description == "Reviews AI trading decisions."
    assert workspace.order == 1
