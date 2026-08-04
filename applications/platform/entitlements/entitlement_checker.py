"""Product access check interface.

Products are referenced by a plain string id (e.g. "trading_intelligence"),
not by importing anything from registry/ or any product package -- avoids
coupling entitlements/ to registry/'s internal Product shape. See
docs/platform/AARA_IDENTITY_AND_ACCESS_IMPLEMENTATION_PLAN.md Section 5
("what users can see" -- backend enforcement design is not this file's job).
"""
from abc import ABC, abstractmethod

from applications.platform.identity.user import User


class EntitlementChecker(ABC):
    @abstractmethod
    def has_access(self, user: User, product_id: str) -> bool:
        ...
