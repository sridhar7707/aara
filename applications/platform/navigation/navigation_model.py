"""The built navigation state -- current user plus composed navigation items.

No builder exists to produce one from AuthenticationProvider/EntitlementChecker/
ProductRegistry/WorkspaceRegistry yet, per
docs/platform/AARA_NAVIGATION_MODEL_ARCHITECTURE.md Section 5's noted gap:
ShellBuilder (Phase 4E) predates NavigationItem and does not build this.
"""
from dataclasses import dataclass
from typing import List, Optional

from applications.platform.identity.user import User
from applications.platform.navigation.navigation_item import NavigationItem


@dataclass(frozen=True)
class NavigationModel:
    current_user: Optional[User]
    items: List[NavigationItem]
