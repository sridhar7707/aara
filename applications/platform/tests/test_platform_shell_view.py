"""Tests for applications.platform.shell.platform_shell_view.PlatformShellView."""
import dataclasses

import pytest

from applications.platform.identity.user import User
from applications.platform.navigation.navigation_item import NavigationItem
from applications.platform.shell.platform_shell_view import PlatformShellView


def _make_item(**overrides):
    defaults = dict(
        product_id="trading_intelligence",
        workspace_id="trading_intelligence.decision_center",
        label="Decision Center",
        order=0,
        visibility="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return NavigationItem(**defaults)


def test_platform_shell_view_is_a_dataclass():
    assert dataclasses.is_dataclass(PlatformShellView)


def test_platform_shell_view_is_immutable():
    view = PlatformShellView(current_user=None, navigation=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.navigation = [_make_item()]


def test_platform_shell_view_holds_current_user_and_navigation():
    user = User(user_id="user-001", display_name="Jordan Smith")
    item = _make_item()

    view = PlatformShellView(current_user=user, navigation=[item])

    assert view.current_user == user
    assert view.navigation == [item]
