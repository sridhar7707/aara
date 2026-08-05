"""Tests for applications.platform.shell.shell_model.ShellModel."""
import dataclasses

import pytest

from applications.platform.identity.user import User
from applications.platform.registry.product_registry import Product
from applications.platform.shell.shell_model import ShellModel


def _make_product(**overrides):
    defaults = dict(
        product_id="trading_intelligence",
        name="Trading Intelligence",
        entitlement_required="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return Product(**defaults)


def test_shell_model_is_a_dataclass():
    assert dataclasses.is_dataclass(ShellModel)


def test_shell_model_is_immutable():
    model = ShellModel(current_user=None, visible_products=[], available_workspaces=[])
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.current_user = User(user_id="x", display_name="x")


def test_shell_model_holds_current_user_visible_products_and_workspaces():
    user = User(user_id="user-001", display_name="Jordan Smith")
    product = _make_product()

    model = ShellModel(
        current_user=user,
        visible_products=[product],
        available_workspaces=["trading_intelligence"],
    )

    assert model.current_user == user
    assert model.visible_products == [product]
    assert model.available_workspaces == ["trading_intelligence"]
