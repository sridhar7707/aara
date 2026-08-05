"""Shell presentation model -- the output of ShellPresenter.present().

Presentation model only: no frontend code, no routes, no React, no
authentication. `navigation` holds the NavigationModel's items directly, not
the whole NavigationModel -- current_user is its own field here rather than
duplicated inside a nested model.
"""
from dataclasses import dataclass
from typing import List, Optional

from applications.platform.identity.user import User
from applications.platform.navigation.navigation_item import NavigationItem


@dataclass(frozen=True)
class PlatformShellView:
    current_user: Optional[User]
    navigation: List[NavigationItem]
