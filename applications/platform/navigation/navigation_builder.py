"""Builds NavigationModel from the four platform abstractions only -- no
login, no OAuth, no URL routing, no UI rendering, no React.

Entitlement filtering happens at the product level: EntitlementChecker.has_access()
only takes a product_id, not a workspace_id, so a product's workspaces are
all-or-nothing visible together. This concretely resolves the open question
in docs/platform/AARA_WORKSPACE_REGISTRATION_ARCHITECTURE.md Section 3 and
docs/platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md Section 3 ("does
workspace visibility inherit from the product, or can it be independent?")
-- it inherits, because no other interface exists to check otherwise.

NavigationItem.visibility is a passthrough of the workspace's own declared
visibility field, not a re-derived entitlement-check result.
"""
from typing import List

from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.navigation.navigation_item import NavigationItem
from applications.platform.navigation.navigation_model import NavigationModel
from applications.platform.registry.product_registry import ProductRegistry
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry


class NavigationBuilder:
    def __init__(
        self,
        product_registry: ProductRegistry,
        workspace_registry: WorkspaceRegistry,
        entitlement_checker: EntitlementChecker,
        auth_provider: AuthenticationProvider,
    ):
        self._product_registry = product_registry
        self._workspace_registry = workspace_registry
        self._entitlement_checker = entitlement_checker
        self._auth_provider = auth_provider

    def build(self) -> NavigationModel:
        user = self._auth_provider.get_current_user()
        if user is None:
            return NavigationModel(current_user=None, items=[])

        items: List[NavigationItem] = []
        for product in self._product_registry.list_products():
            if not self._entitlement_checker.has_access(user, product.product_id):
                continue
            for workspace in self._workspace_registry.list_workspaces(product.product_id):
                items.append(
                    NavigationItem(
                        product_id=workspace.product_id,
                        workspace_id=workspace.workspace_id,
                        label=workspace.display_name,
                        order=workspace.order,
                        visibility=workspace.visibility,
                    )
                )

        return NavigationModel(current_user=user, items=items)
