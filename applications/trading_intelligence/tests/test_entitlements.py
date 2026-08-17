"""Tests for applications.trading_intelligence.entitlements.TradingIntelligenceEntitlementChecker.

Per ADR-038 Sec 2.1/Sec 6: verifies the checker implements exactly ADR-003's
Trading-Intelligence-User rule -- product_id == "trading_intelligence" plus
an injected grant set, fail-closed by construction, nothing more.
"""
from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.user import User
from applications.trading_intelligence.entitlements import TradingIntelligenceEntitlementChecker


def _make_user(user_id="user-001"):
    return User(user_id=user_id, display_name="Jordan Smith")


def test_trading_intelligence_entitlement_checker_is_an_entitlement_checker():
    checker = TradingIntelligenceEntitlementChecker()

    assert isinstance(checker, EntitlementChecker)


def test_has_access_returns_false_for_a_user_not_in_the_grant_set():
    checker = TradingIntelligenceEntitlementChecker(entitled_user_ids={"user-999"})

    assert checker.has_access(_make_user(), "trading_intelligence") is False


def test_has_access_returns_true_for_a_user_in_the_grant_set():
    user = _make_user()
    checker = TradingIntelligenceEntitlementChecker(entitled_user_ids={user.user_id})

    assert checker.has_access(user, "trading_intelligence") is True


def test_has_access_returns_false_for_wealth_intelligence_regardless_of_grants():
    user = _make_user()
    checker = TradingIntelligenceEntitlementChecker(entitled_user_ids={user.user_id})

    assert checker.has_access(user, "wealth_intelligence") is False


def test_has_access_returns_false_with_no_grant_set_argument():
    checker = TradingIntelligenceEntitlementChecker()

    assert checker.has_access(_make_user(), "trading_intelligence") is False
