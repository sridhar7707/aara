"""Tests for applications.trading_intelligence.product."""
import ast
import pathlib

from applications.platform.registry.product_registry import Product
from applications.trading_intelligence.product import TRADING_INTELLIGENCE_PRODUCT


def test_trading_intelligence_product_is_a_product_instance():
    assert isinstance(TRADING_INTELLIGENCE_PRODUCT, Product)


def test_trading_intelligence_product_has_correct_metadata():
    assert TRADING_INTELLIGENCE_PRODUCT.product_id == "trading_intelligence"
    assert TRADING_INTELLIGENCE_PRODUCT.name == "Trading Intelligence"
    assert TRADING_INTELLIGENCE_PRODUCT.entitlement_required == "TRADING_INTELLIGENCE"


def test_product_module_does_not_import_services_adapters_or_sentinel_engine():
    forbidden = (
        "applications.trading_intelligence.services",
        "applications.trading_intelligence.adapters",
        "sentinel_engine",
    )
    path = pathlib.Path(__file__).resolve().parent.parent / "product.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"product.py: forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), (
                f"product.py: forbidden import from {module!r}"
            )
