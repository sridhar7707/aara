"""Tests for applications.platform.workspaces.workspace_registry.WorkspaceRegistry."""
import pytest

from applications.platform.workspaces.workspace import Workspace
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry


class _InMemoryWorkspaceRegistry(WorkspaceRegistry):
    """Fake registry -- no database, per this task's constraints."""

    def __init__(self):
        self._workspaces = []

    def register_workspace(self, workspace):
        self._workspaces.append(workspace)

    def list_workspaces(self, product_id):
        return [w for w in self._workspaces if w.product_id == product_id]


def _make_workspace(**overrides):
    defaults = dict(
        workspace_id="trading_intelligence.decision_center",
        product_id="trading_intelligence",
        display_name="Decision Center",
        visibility="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return Workspace(**defaults)


def test_workspace_registry_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        WorkspaceRegistry()


def test_incomplete_workspace_registry_subclass_cannot_be_instantiated():
    class _Incomplete(WorkspaceRegistry):
        def register_workspace(self, workspace):
            pass
        # list_workspaces deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()


def test_fake_registry_works():
    registry = _InMemoryWorkspaceRegistry()

    assert registry.list_workspaces("trading_intelligence") == []


def test_workspace_registration_works():
    registry = _InMemoryWorkspaceRegistry()
    workspace = _make_workspace()

    registry.register_workspace(workspace)

    assert registry.list_workspaces("trading_intelligence") == [workspace]


def test_product_filtering_works():
    registry = _InMemoryWorkspaceRegistry()
    trading_workspace = _make_workspace(
        workspace_id="trading_intelligence.decision_center",
        product_id="trading_intelligence",
    )
    wealth_workspace = _make_workspace(
        workspace_id="wealth_intelligence.wealth_home",
        product_id="wealth_intelligence",
        display_name="Wealth Home",
        visibility="WEALTH_INTELLIGENCE",
    )

    registry.register_workspace(trading_workspace)
    registry.register_workspace(wealth_workspace)

    assert registry.list_workspaces("trading_intelligence") == [trading_workspace]
    assert registry.list_workspaces("wealth_intelligence") == [wealth_workspace]


def test_product_filtering_returns_multiple_workspaces_for_the_same_product():
    registry = _InMemoryWorkspaceRegistry()
    decision_center = _make_workspace(
        workspace_id="trading_intelligence.decision_center", order=0
    )
    portfolio = _make_workspace(
        workspace_id="trading_intelligence.portfolio",
        display_name="Portfolio",
        order=1,
    )

    registry.register_workspace(decision_center)
    registry.register_workspace(portfolio)

    assert registry.list_workspaces("trading_intelligence") == [decision_center, portfolio]


def test_product_filtering_returns_empty_list_for_unregistered_product():
    registry = _InMemoryWorkspaceRegistry()
    registry.register_workspace(_make_workspace())

    assert registry.list_workspaces("wealth_intelligence") == []
