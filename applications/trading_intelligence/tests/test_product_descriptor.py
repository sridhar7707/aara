"""Tests for applications.trading_intelligence.product."""
import ast
import pathlib

from applications.platform.registry.product_registry import Product
from applications.platform.workspaces.workspace import Workspace
from applications.trading_intelligence.product import (
    DECISION_CENTER_WORKSPACE,
    TRADING_INTELLIGENCE_PRODUCT,
)


def test_trading_intelligence_product_is_a_product_instance():
    assert isinstance(TRADING_INTELLIGENCE_PRODUCT, Product)


def test_trading_intelligence_product_has_correct_metadata():
    assert TRADING_INTELLIGENCE_PRODUCT.product_id == "trading_intelligence"
    assert TRADING_INTELLIGENCE_PRODUCT.name == "Trading Intelligence"
    assert TRADING_INTELLIGENCE_PRODUCT.entitlement_required == "TRADING_INTELLIGENCE"


def test_decision_center_workspace_is_a_workspace_instance():
    assert isinstance(DECISION_CENTER_WORKSPACE, Workspace)


def test_decision_center_workspace_has_correct_metadata():
    assert DECISION_CENTER_WORKSPACE.workspace_id == "trading_intelligence.decision_center"
    assert DECISION_CENTER_WORKSPACE.product_id == "trading_intelligence"
    assert DECISION_CENTER_WORKSPACE.display_name == "Decision Center"
    assert DECISION_CENTER_WORKSPACE.visibility == "TRADING_INTELLIGENCE"
    assert DECISION_CENTER_WORKSPACE.order == 0


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
