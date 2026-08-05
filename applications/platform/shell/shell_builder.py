"""Builds ShellModel from the three platform abstractions only -- no login,
no OAuth, no frontend, no routes, no database. If no user is authenticated,
the resulting shell has no visible products (nothing to entitlement-check
against).
"""
from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.registry.product_registry import ProductRegistry
from applications.platform.shell.shell_model import ShellModel


class ShellBuilder:
    def __init__(
        self,
        auth_provider: AuthenticationProvider,
        entitlement_checker: EntitlementChecker,
        product_registry: ProductRegistry,
    ):
        self._auth_provider = auth_provider
        self._entitlement_checker = entitlement_checker
        self._product_registry = product_registry

    def build(self) -> ShellModel:
        user = self._auth_provider.get_current_user()
        if user is None:
            return ShellModel(current_user=None, visible_products=[], available_workspaces=[])

        visible = [
            product
            for product in self._product_registry.list_products()
            if self._entitlement_checker.has_access(user, product.product_id)
        ]
        return ShellModel(
            current_user=user,
            visible_products=visible,
            available_workspaces=[product.product_id for product in visible],
        )
