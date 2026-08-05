"""Tests for applications.platform.navigation.navigation_builder.NavigationBuilder."""
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User
from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.navigation.navigation_builder import NavigationBuilder
from applications.platform.registry.product_registry import Product, ProductRegistry
from applications.platform.workspaces.workspace import Workspace
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry


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
    def __init__(self, products=None):
        self._products = {p.product_id: p for p in (products or [])}

    def register(self, product):
        self._products[product.product_id] = product

    def list_products(self):
        return list(self._products.values())


class _InMemoryWorkspaceRegistry(WorkspaceRegistry):
    def __init__(self, workspaces=None):
        self._workspaces = list(workspaces or [])

    def register_workspace(self, workspace):
        self._workspaces.append(workspace)

    def list_workspaces(self, product_id):
        return [w for w in self._workspaces if w.product_id == product_id]


_TRADING = Product(
    product_id="trading_intelligence",
    name="Trading Intelligence",
    entitlement_required="TRADING_INTELLIGENCE",
)
_WEALTH = Product(
    product_id="wealth_intelligence",
    name="Wealth Intelligence",
    entitlement_required="WEALTH_INTELLIGENCE",
)

_DECISION_CENTER = Workspace(
    workspace_id="trading_intelligence.decision_center",
    product_id="trading_intelligence",
    display_name="Decision Center",
    visibility="TRADING_INTELLIGENCE",
    order=0,
)
_PORTFOLIO = Workspace(
    workspace_id="trading_intelligence.portfolio",
    product_id="trading_intelligence",
    display_name="Portfolio",
    visibility="TRADING_INTELLIGENCE",
    order=1,
)
_WEALTH_HOME = Workspace(
    workspace_id="wealth_intelligence.wealth_home",
    product_id="wealth_intelligence",
    display_name="Wealth Home",
    visibility="WEALTH_INTELLIGENCE",
    order=0,
)


def _build(current_user=None, grants=None, products=None, workspaces=None):
    builder = NavigationBuilder(
        product_registry=_InMemoryProductRegistry(products),
        workspace_registry=_InMemoryWorkspaceRegistry(workspaces),
        entitlement_checker=_FakeEntitlementChecker(grants),
        auth_provider=_FakeAuthenticationProvider(current_user),
    )
    return builder.build()


def test_entitled_product_produces_navigation():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build(
        current_user=user,
        grants={("user-001", "trading_intelligence")},
        products=[_TRADING],
        workspaces=[_DECISION_CENTER],
    )

    assert model.current_user == user
    assert len(model.items) == 1
    assert model.items[0].workspace_id == "trading_intelligence.decision_center"
    assert model.items[0].product_id == "trading_intelligence"
    assert model.items[0].label == "Decision Center"


def test_non_entitled_product_hidden():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build(
        current_user=user,
        grants=set(),  # no grants
        products=[_TRADING],
        workspaces=[_DECISION_CENTER],
    )

    assert model.items == []


def test_workspace_filtering_works():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build(
        current_user=user,
        grants={("user-001", "trading_intelligence")},
        products=[_TRADING, _WEALTH],
        workspaces=[_DECISION_CENTER, _PORTFOLIO, _WEALTH_HOME],
    )

    workspace_ids = [item.workspace_id for item in model.items]
    assert "trading_intelligence.decision_center" in workspace_ids
    assert "trading_intelligence.portfolio" in workspace_ids
    assert "wealth_intelligence.wealth_home" not in workspace_ids


def test_ordering_preserved():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build(
        current_user=user,
        grants={("user-001", "trading_intelligence")},
        products=[_TRADING],
        workspaces=[_PORTFOLIO, _DECISION_CENTER],  # registered out of order
    )

    orders = {item.workspace_id: item.order for item in model.items}
    assert orders["trading_intelligence.decision_center"] == 0
    assert orders["trading_intelligence.portfolio"] == 1


def test_empty_navigation_when_no_current_user():
    model = _build(current_user=None)

    assert model.current_user is None
    assert model.items == []


def test_empty_navigation_when_no_products_registered():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build(current_user=user, products=[], workspaces=[])

    assert model.current_user == user
    assert model.items == []
