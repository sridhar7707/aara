"""The Wave 2A modules must stay inside the Trading Intelligence
boundary: no import of a protected runtime package, no reference to a
table outside the ADR-055-authorized ``trades`` read, and no write SQL.
"""
import ast
import inspect

import pytest

import applications.trading_intelligence.adapters.trade_outcome_derivation as derivation
import applications.trading_intelligence.adapters.trades_db_outcome_source as source
import applications.trading_intelligence.contracts.decision_outcome_contract as contract
import applications.trading_intelligence.projections.trade_outcome_row as projection
import applications.trading_intelligence.services.decision_outcome_query_service as service

_MODULES = (projection, contract, derivation, source, service)

_FORBIDDEN_IMPORT_PREFIXES = (
    "bot",
    "dashboard",
    "scheduler",
    "database",
    "ledger",
    "sentinel_engine",
    "sentinel",
)
_FORBIDDEN_TABLE_TOKENS = ("decision_log", "position_state", "trade_journal")
_WRITE_SQL = ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ")


def _imported_names(module):
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_protected_package_import(module):
    for name in _imported_names(module):
        assert not name.startswith(_FORBIDDEN_IMPORT_PREFIXES), (
            f"{module.__name__} imports forbidden package {name!r}"
        )


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_forbidden_table_reference(module):
    src = inspect.getsource(module)
    for token in _FORBIDDEN_TABLE_TOKENS:
        assert token not in src, f"{module.__name__} references {token!r}"


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_write_sql(module):
    src = inspect.getsource(module).upper()
    for stmt in _WRITE_SQL:
        assert stmt not in src, f"{module.__name__} contains write SQL {stmt.strip()!r}"


def test_derivation_has_no_pinned_phantom_ids():
    """Phantom-reconcile suppression must be purely structural -- the
    known 2026-07-07 batch ids are a test/regression concern only and
    must never drive runtime behaviour. The word "phantom" in docstrings
    and helper names is fine; a hard-coded id collection is not."""
    src = inspect.getsource(derivation)
    assert not hasattr(derivation, "PHANTOM_RECONCILE_TRADE_IDS")
    assert "20,21,22,23,24,26" not in src.replace(" ", "")

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            ints = {
                elt.value
                for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int)
            }
            assert not {20, 21, 22, 23, 24, 26}.issubset(ints), (
                "runtime module contains a hard-coded phantom-reconcile id set"
            )
