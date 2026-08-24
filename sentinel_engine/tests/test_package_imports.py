"""Structural tests for the sentinel_engine package.

Verifies imports and the independence rule from ADR-001: sentinel_engine is
a separate package, extracted from sentinel/, independent of bot/,
dashboard/, database/ (and, by the same principle, scheduler/, ledger/, and
applications/ -- nothing Trading-Intelligence-side or product-side).

Mirrors the pattern established in
applications/platform/tests/test_platform_structure.py: a parametrized
import-cleanliness check over every production module, plus one AST-based
forbidden-import scan over the whole package. The forbidden-import scan
deliberately excludes tests/ itself -- integration tests elsewhere in this
codebase (e.g. applications/trading_intelligence/tests/) legitimately import
sentinel_engine to prove real wiring; that exemption is for other packages'
tests importing sentinel_engine, not the reverse, but the same
tests-are-exempt principle applies here for consistency and to leave room
for any future sentinel_engine-side integration test that needs to reach
across a boundary to prove something.

Only one narrower, single-file equivalent existed before this file
(test_decision_adapter.py's test_decision_adapter_module_does_not_import_bot),
scoped to one module and one forbidden prefix -- this supersedes that scope
without removing it.
"""
import ast
import importlib
import pathlib

import pytest

_SENTINEL_ENGINE_ROOT = pathlib.Path(__file__).resolve().parent.parent

_MODULES = [
    "sentinel_engine",
    "sentinel_engine.domain",
    "sentinel_engine.domain.decision",
    "sentinel_engine.events",
    "sentinel_engine.events.event",
    "sentinel_engine.events.event_types",
    "sentinel_engine.evidence",
    "sentinel_engine.evidence.evidence",
    "sentinel_engine.governance",
    "sentinel_engine.governance.policy",
    "sentinel_engine.governance.approval",
    "sentinel_engine.ledger",
    "sentinel_engine.ledger.ledger",
    "sentinel_engine.projections",
    "sentinel_engine.projections.decision_projection",
    "sentinel_engine.repositories",
    "sentinel_engine.repositories.ledger_repository",
    "sentinel_engine.repositories.projection_repository",
    "sentinel_engine.services",
    "sentinel_engine.services.decision_service",
    "sentinel_engine.services.evidence_service",
    "sentinel_engine.services.governance_service",
    "sentinel_engine.services.sentinel_engine",
    "sentinel_engine.adapters",
    "sentinel_engine.adapters.decision_adapter",
    "sentinel_engine.composition",
    "sentinel_engine.composition.evidence",
    "sentinel_engine.composition.governance",
]


@pytest.mark.parametrize("module_name", _MODULES)
def test_sentinel_engine_package_imports_cleanly(module_name):
    importlib.import_module(module_name)


def test_sentinel_engine_does_not_import_bot_dashboard_scheduler_ledger_database_or_applications():
    forbidden_prefixes = (
        "bot",
        "dashboard",
        "scheduler",
        "ledger",
        "database",
        "applications",
    )
    py_files = [
        path
        for path in _SENTINEL_ENGINE_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(_SENTINEL_ENGINE_ROOT).parts
        and "__pycache__" not in path.parts
    ]
    assert py_files, "expected at least one production .py file under sentinel_engine/"

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
