"""Concrete EntitlementChecker for Trading Intelligence (ADR-038).

Implements exactly ADR-003's Trading-Intelligence-User rule -- product-level
access only, keyed on Product.product_id ("trading_intelligence"), never
Product.entitlement_required (neither NavigationBuilder nor ShellBuilder ever
passes that field to has_access() -- see ADR-038 Sec 1/Sec 2.1). No Role,
Entitlement, or enum type; no Wealth Intelligence or AARA Super User
semantics -- those are simply unreachable through this class, since it only
ever evaluates one hardcoded product_id.

No real permissions engine: the grant set is a constructor-injected,
in-memory value, defaulting to empty -- fail-closed by construction, not by
convention.
"""
from typing import FrozenSet, Optional, Set

from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.user import User

_TRADING_INTELLIGENCE_PRODUCT_ID = "trading_intelligence"


class TradingIntelligenceEntitlementChecker(EntitlementChecker):
    def __init__(self, entitled_user_ids: Optional[Set[str]] = None):
        self._entitled_user_ids: FrozenSet[str] = frozenset(entitled_user_ids or ())

    def has_access(self, user: User, product_id: str) -> bool:
        if product_id != _TRADING_INTELLIGENCE_PRODUCT_ID:
            return False
        return user.user_id in self._entitled_user_ids
