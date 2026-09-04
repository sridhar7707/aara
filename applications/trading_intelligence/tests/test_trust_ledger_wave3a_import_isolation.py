"""Wave 3A modules must stay inside the Trading Intelligence boundary
(ADR-064 Section 2.14): no import of a protected runtime package, no
reference to a Trust Ledger table outside the two authorized by ADR-064,
no reference to trades.db / screener_log / signal_log, and no write SQL.
"""
import ast
import inspect

import pytest

import applications.trading_intelligence.adapters.trust_ledger_inspection_source as source
import applications.trading_intelligence.adapters.trust_ledger_snapshot as snapshot
import applications.trading_intelligence.contracts.candidate_decision_contract as contract

_MODULES = (snapshot, source, contract)

_FORBIDDEN_IMPORT_PREFIXES = (
    "bot",
    "ledger",
    "scheduler",
    "dashboard",
    "database",
    "sentinel_engine",
    "sentinel",
)

# ADR-064: out-of-scope Trust Ledger tables + the databases/tables the
# rejected funnel would have used.
_FORBIDDEN_TABLE_TOKENS = (
    "decision_outcome_events",
    "constitution_enforcement_events",
    "risk_evaluation_events",
    "deployment_manifest_events",
    "decision_confidence_events",
    "approval_events",
    "screener_log",
    "signal_log",
    "decision_log",
    "position_state",
    "trade_journal",
)

_WRITE_SQL = ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ", "VACUUM")


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
        top = name.split(".")[0]
        assert top not in _FORBIDDEN_IMPORT_PREFIXES, (
            f"{module.__name__} imports forbidden package {name!r}"
        )


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_forbidden_table_reference(module):
    src = inspect.getsource(module)
    for token in _FORBIDDEN_TABLE_TOKENS:
        assert token not in src, f"{module.__name__} references {token!r}"


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_trades_db_reference(module):
    """No bridge to trades.db identities (ADR-064 Section 2.5 / 2.6)."""
    src = inspect.getsource(module)
    assert "trades.db" not in src
    assert "trades_db_snapshot" not in src


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_no_write_sql(module):
    src = inspect.getsource(module).upper()
    for stmt in _WRITE_SQL:
        assert stmt not in src, f"{module.__name__} contains write SQL {stmt.strip()!r}"


def test_source_default_db_path_is_the_product_runtime_snapshot():
    """The source consumes the product-owned snapshot path, never
    data/trust_ledger.db (ADR-064 Section 2.1 item 4)."""
    src = inspect.getsource(source)
    assert "data/trust_ledger.db" not in src
    reader = source.TrustLedgerInspectionReader()
    assert reader._db_path.endswith("trust_ledger_snapshot.db")
    assert ".runtime" in reader._db_path


def test_contracts_model_no_outcome_or_trade_fields():
    """The frozen contracts carry no outcome, P&L, or trade-linkage field
    (ADR-064 Section 2.8 / Section 8)."""
    src = inspect.getsource(contract).lower()
    for token in ("realized_pnl", "gross_return", "net_return", "holding_period",
                  "pnl", "outcome_direction", "trade_id", "order_id",
                  "exit_price", "calibration", "attribution"):
        assert token not in src, f"contract references {token!r}"
