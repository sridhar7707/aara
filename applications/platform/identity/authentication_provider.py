"""Authentication provider interface.

No concrete implementation exists here -- Google OAuth / a managed auth
provider / an internal identity service remain undecided
(docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md Section 4).
Whichever is eventually chosen implements this interface.
"""
from abc import ABC, abstractmethod
from typing import Optional

from applications.platform.identity.user import User


class AuthenticationProvider(ABC):
    @abstractmethod
    def get_current_user(self) -> Optional[User]:
        ...
