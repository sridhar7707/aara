"""Tests for applications.platform.navigation.navigation_model.NavigationModel."""
import dataclasses

import pytest

from applications.platform.identity.user import User
from applications.platform.navigation.navigation_item import NavigationItem
from applications.platform.navigation.navigation_model import NavigationModel


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


def test_navigation_model_is_a_dataclass():
    assert dataclasses.is_dataclass(NavigationModel)


def test_navigation_model_is_immutable():
    model = NavigationModel(current_user=None, items=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.items = [_make_item()]


def test_fake_navigation_model_works():
    """A NavigationModel built from a fake user and fake items -- no real
    identity/registry backend involved."""
    user = User(user_id="user-001", display_name="Jordan Smith")
    item = _make_item()

    model = NavigationModel(current_user=user, items=[item])

    assert model.current_user == user
    assert model.items == [item]


def test_navigation_model_holds_no_user_and_no_items():
    model = NavigationModel(current_user=None, items=[])

    assert model.current_user is None
    assert model.items == []


def test_navigation_model_holds_multiple_items_in_given_order():
    first = _make_item(workspace_id="trading_intelligence.decision_center", order=0)
    second = _make_item(workspace_id="trading_intelligence.portfolio", label="Portfolio", order=1)

    model = NavigationModel(current_user=None, items=[first, second])

    assert [item.workspace_id for item in model.items] == [
        "trading_intelligence.decision_center",
        "trading_intelligence.portfolio",
    ]
