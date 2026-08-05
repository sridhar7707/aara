"""Integration test: the real Trading Intelligence product descriptor and a
real Decision Center workspace value, composed end-to-end through
NavigationBuilder.

Closes the specific gap named in
docs/products/AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md
Section 2/6: TRADING_INTELLIGENCE_PRODUCT has been proven registrable
(test_trading_intelligence_registration.py) and NavigationBuilder has been
proven to compose Product+Workspace data correctly (test_navigation_builder.py)
-- but never together, and never with the real product descriptor. Every
prior NavigationBuilder test used a synthetic, locally-defined Product, not
applications.trading_intelligence.product.TRADING_INTELLIGENCE_PRODUCT.

No production code is created or modified here -- every class used already
exists (ProductRegistry, WorkspaceRegistry, NavigationBuilder,
AuthenticationProvider, EntitlementChecker, User, Product, Workspace,
NavigationItem, NavigationModel). This file only proves they compose
correctly for Trading Intelligence specifically.
"""
from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User
from applications.platform.navigation.navigation_builder import NavigationBuilder
from applications.platform.registry.product_registry import ProductRegistry
from applications.platform.workspaces.workspace import Workspace
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry
from applications.trading_intelligence.product import TRADING_INTELLIGENCE_PRODUCT

_DECISION_CENTER_WORKSPACE = Workspace(
    workspace_id="trading_intelligence.decision_center",
    product_id="trading_intelligence",
    display_name="Decision Center",
    visibility="TRADING_INTELLIGENCE",
    order=0,
)


class _FakeAuthenticationProvider(AuthenticationProvider):
    def __init__(self, current_user=None):
        self._current_user = current_user

    def get_current_user(self):
        return self._current_user


class _FakeEntitlementChecker(EntitlementChecker):
    def __init__(self, grants=None):
        self._grants = grants or set()  # set of (user_id, product_id)

    def has_access(self, user, product_id):
        return (user.user_id, product_id) in self._grants


class _InMemoryProductRegistry(ProductRegistry):
    def __init__(self):
        self._products = {}

    def register(self, product):
        self._products[product.product_id] = product

    def list_products(self):
        return list(self._products.values())


class _InMemoryWorkspaceRegistry(WorkspaceRegistry):
    def __init__(self):
        self._workspaces = []

    def register_workspace(self, workspace):
        self._workspaces.append(workspace)

    def list_workspaces(self, product_id):
        return [w for w in self._workspaces if w.product_id == product_id]


def test_trading_intelligence_product_can_be_registered():
    registry = _InMemoryProductRegistry()

    registry.register(TRADING_INTELLIGENCE_PRODUCT)

    assert registry.list_products() == [TRADING_INTELLIGENCE_PRODUCT]


def test_decision_center_workspace_can_be_registered():
    registry = _InMemoryWorkspaceRegistry()

    registry.register_workspace(_DECISION_CENTER_WORKSPACE)

    assert registry.list_workspaces("trading_intelligence") == [_DECISION_CENTER_WORKSPACE]


def test_navigation_builder_discovers_trading_intelligence_when_entitled():
    user = User(user_id="u1", display_name="Investor One")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(_DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    assert model.current_user == user
    assert any(item.product_id == "trading_intelligence" for item in model.items)


def test_decision_center_appears_as_a_navigation_item():
    user = User(user_id="u1", display_name="Investor One")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(_DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    decision_center_items = [
        item for item in model.items if item.workspace_id == "trading_intelligence.decision_center"
    ]
    assert len(decision_center_items) == 1
    assert decision_center_items[0].label == "Decision Center"
    assert decision_center_items[0].product_id == "trading_intelligence"


def test_non_entitled_users_do_not_see_trading_intelligence():
    user = User(user_id="u2", display_name="Wealth Only User")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(_DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants=set())  # no grants for this user
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    assert model.items == []


def test_module_does_not_import_forbidden_runtimes():
    """This test file itself must never import bot/dashboard/scheduler/
    ledger/database -- it composes only platform + Trading Intelligence's
    product descriptor, both already permitted per
    test_product_registry_module_does_not_import_product_internals's
    established boundary-scan pattern."""
    import ast
    import pathlib

    forbidden = ("bot", "dashboard", "scheduler", "ledger", "database")
    path = pathlib.Path(__file__).resolve()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"{path}: forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), (
                f"{path}: forbidden import from {module!r}"
            )
