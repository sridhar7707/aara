"""Structural tests for the trading_intelligence application boundary skeleton.

Verifies the package imports cleanly and that the forbidden dependency rules
from README.md (no bot/, dashboard/, scheduler/, database/, or ledger/
imports) hold as a checked fact, not just a documented claim.
"""
import ast
import importlib
import pathlib

import pytest

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent.parent

_SUBPACKAGES = [
    "applications.trading_intelligence",
    "applications.trading_intelligence.product",
    "applications.trading_intelligence.contracts",
    "applications.trading_intelligence.contracts.decision_contract",
    "applications.trading_intelligence.adapters",
    "applications.trading_intelligence.adapters.sentinel_projection_decision_source",
    "applications.trading_intelligence.adapters.sentinel_evidence_source",
    "applications.trading_intelligence.adapters.sentinel_governance_source",
    "applications.trading_intelligence.adapters.sentinel_audit_source",
    "applications.trading_intelligence.entitlements",
    "applications.trading_intelligence.projections",
    "applications.trading_intelligence.projections.decision_view",
    "applications.trading_intelligence.projections.evidence_entry",
    "applications.trading_intelligence.projections.governance_entry",
    "applications.trading_intelligence.projections.approval_entry",
    "applications.trading_intelligence.projections.audit_entry",
    "applications.trading_intelligence.services",
    "applications.trading_intelligence.services.decision_query_service",
    "applications.trading_intelligence.services.decision_evidence_query_service",
    "applications.trading_intelligence.services.decision_governance_query_service",
]


@pytest.mark.parametrize("module_name", _SUBPACKAGES)
def test_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_no_module_imports_forbidden_runtimes():
    forbidden_prefixes = ("bot", "dashboard", "scheduler", "database", "ledger")
    py_files = list(_PACKAGE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one .py file under applications/trading_intelligence/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), (
                    f"{path}: forbidden import from {module!r}"
                )
