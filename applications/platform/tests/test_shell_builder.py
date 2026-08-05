"""Tests for applications.platform.shell.shell_builder.ShellBuilder."""
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User
from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.registry.product_registry import Product, ProductRegistry
from applications.platform.shell.shell_builder import ShellBuilder


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


def _build_shell(current_user=None, grants=None, products=None):
    builder = ShellBuilder(
        auth_provider=_FakeAuthenticationProvider(current_user),
        entitlement_checker=_FakeEntitlementChecker(grants),
        product_registry=_InMemoryProductRegistry(products),
    )
    return builder.build()


def test_fake_user_works():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build_shell(current_user=user)

    assert model.current_user == user


def test_no_current_user_yields_an_empty_shell():
    model = _build_shell(current_user=None)

    assert model.current_user is None
    assert model.visible_products == []
    assert model.available_workspaces == []


def test_entitled_product_appears():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build_shell(
        current_user=user,
        grants={("user-001", "trading_intelligence")},
        products=[_TRADING],
    )

    assert model.visible_products == [_TRADING]
    assert model.available_workspaces == ["trading_intelligence"]


def test_non_entitled_product_hidden():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build_shell(
        current_user=user,
        grants=set(),  # no grants at all
        products=[_TRADING],
    )

    assert model.visible_products == []
    assert model.available_workspaces == []


def test_only_entitled_products_appear_among_several_registered():
    user = User(user_id="user-001", display_name="Jordan Smith")

    model = _build_shell(
        current_user=user,
        grants={("user-001", "trading_intelligence")},
        products=[_TRADING, _WEALTH],
    )

    assert model.visible_products == [_TRADING]
    assert model.available_workspaces == ["trading_intelligence"]
