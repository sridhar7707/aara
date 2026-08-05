"""Tests for applications.platform.navigation.navigation_item.NavigationItem."""
import dataclasses

import pytest

from applications.platform.navigation.navigation_item import NavigationItem


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


def test_navigation_item_can_be_created_with_required_fields():
    item = _make_item()

    assert item.product_id == "trading_intelligence"
    assert item.workspace_id == "trading_intelligence.decision_center"
    assert item.label == "Decision Center"
    assert item.order == 0
    assert item.visibility == "TRADING_INTELLIGENCE"


def test_navigation_item_is_a_dataclass():
    assert dataclasses.is_dataclass(NavigationItem)


def test_navigation_item_is_immutable():
    item = _make_item()
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.label = "Something Else"


def test_navigation_item_requires_all_fields():
    with pytest.raises(TypeError):
        NavigationItem(product_id="trading_intelligence", workspace_id="trading_intelligence.decision_center")


def test_ordering_works_when_sorting_multiple_items():
    first = _make_item(workspace_id="trading_intelligence.decision_center", order=1)
    second = _make_item(workspace_id="trading_intelligence.portfolio", label="Portfolio", order=0)

    ordered = sorted([first, second], key=lambda i: i.order)

    assert [i.workspace_id for i in ordered] == [
        "trading_intelligence.portfolio",
        "trading_intelligence.decision_center",
    ]


def test_visibility_is_preserved_exactly():
    item = _make_item(visibility="WEALTH_INTELLIGENCE")

    assert item.visibility == "WEALTH_INTELLIGENCE"
