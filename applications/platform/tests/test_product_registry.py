"""Tests for applications.platform.registry.product_registry."""
import dataclasses

import pytest

from applications.platform.registry.product_registry import Product, ProductRegistry


class _InMemoryProductRegistry(ProductRegistry):
    """Minimal conforming implementation -- no database, per this task's
    constraints."""

    def __init__(self):
        self._products = {}

    def register(self, product):
        self._products[product.product_id] = product

    def list_products(self):
        return list(self._products.values())


def _make_product(**overrides):
    defaults = dict(
        product_id="trading_intelligence",
        name="Trading Intelligence",
        entitlement_required="TRADING_INTELLIGENCE",
    )
    defaults.update(overrides)
    return Product(**defaults)


def test_product_is_a_dataclass():
    assert dataclasses.is_dataclass(Product)


def test_product_is_immutable():
    product = _make_product()
    with pytest.raises(dataclasses.FrozenInstanceError):
        product.name = "Something Else"


def test_product_requires_entitlement_required():
    with pytest.raises(TypeError):
        Product(product_id="trading_intelligence", name="Trading Intelligence")


def test_product_description_defaults_to_empty_string():
    product = _make_product()

    assert product.description == ""


def test_product_status_defaults_to_none():
    product = _make_product()

    assert product.status is None


def test_product_accepts_explicit_description_and_status():
    product = _make_product(description="A short description.", status="IN_DEVELOPMENT")

    assert product.description == "A short description."
    assert product.status == "IN_DEVELOPMENT"


def test_product_registry_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ProductRegistry()


def test_list_products_returns_empty_list_when_nothing_registered():
    registry = _InMemoryProductRegistry()

    assert registry.list_products() == []


def test_register_then_list_products_returns_the_registered_product():
    registry = _InMemoryProductRegistry()
    product = _make_product()

    registry.register(product)

    assert registry.list_products() == [product]


def test_register_multiple_products():
    registry = _InMemoryProductRegistry()
    trading = _make_product(product_id="trading_intelligence", name="Trading Intelligence")
    wealth = _make_product(product_id="wealth_intelligence", name="Wealth Intelligence")

    registry.register(trading)
    registry.register(wealth)

    assert set(registry.list_products()) == {trading, wealth}


def test_incomplete_product_registry_subclass_cannot_be_instantiated():
    class _Incomplete(ProductRegistry):
        def register(self, product):
            pass
        # list_products deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
