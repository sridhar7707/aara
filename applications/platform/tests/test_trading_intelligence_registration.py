"""Integration test: Trading Intelligence's real product descriptor against
the platform's ProductRegistry interface.

Verifies the registration flow from
docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md Section 4 works
end-to-end with a real product descriptor (not a synthetic Product), and that
the registry module itself never imports product internals to do it.
"""
import ast
import pathlib

from applications.platform.registry.product_registry import ProductRegistry
from applications.trading_intelligence.product import TRADING_INTELLIGENCE_PRODUCT


class _InMemoryProductRegistry(ProductRegistry):
    def __init__(self):
        self._products = {}

    def register(self, product):
        self._products[product.product_id] = product

    def list_products(self):
        return list(self._products.values())


def test_trading_intelligence_product_can_register():
    registry = _InMemoryProductRegistry()

    registry.register(TRADING_INTELLIGENCE_PRODUCT)

    assert registry.list_products() == [TRADING_INTELLIGENCE_PRODUCT]


def test_platform_registry_can_discover_trading_intelligence():
    registry = _InMemoryProductRegistry()
    registry.register(TRADING_INTELLIGENCE_PRODUCT)

    discovered = registry.list_products()

    assert len(discovered) == 1
    assert discovered[0].product_id == "trading_intelligence"
    assert discovered[0].entitlement_required == "TRADING_INTELLIGENCE"


def test_product_registry_module_does_not_import_product_internals():
    """The registry itself must never import applications.trading_intelligence
    (or wealth_intelligence) -- it only ever receives a Product value handed
    to it by the caller (as this test file does)."""
    forbidden = ("applications.trading_intelligence", "applications.wealth_intelligence")
    path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "registry"
        / "product_registry.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"product_registry.py: forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), (
                f"product_registry.py: forbidden import from {module!r}"
            )
