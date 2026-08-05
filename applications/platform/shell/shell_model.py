"""Built shell state -- the output of ShellBuilder.build().

available_workspaces is the visible products' product_id list only, not real
routes. Product has no workspace_routes field (deliberately excluded from the
descriptor model in docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md),
and building real routes is explicitly out of scope for this step.
"""
from dataclasses import dataclass
from typing import List, Optional

from applications.platform.identity.user import User
from applications.platform.registry.product_registry import Product


@dataclass(frozen=True)
class ShellModel:
    current_user: Optional[User]
    visible_products: List[Product]
    available_workspaces: List[str]
