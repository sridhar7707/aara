"""Tests for applications.platform.entitlements.entitlement_checker.EntitlementChecker."""
import pytest

from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.user import User


class _FakeEntitlementChecker(EntitlementChecker):
    """Minimal conforming implementation -- no real permissions engine, per
    this task's constraints."""

    def __init__(self, grants=None):
        self._grants = grants or set()  # set of (user_id, product_id)

    def has_access(self, user, product_id):
        return (user.user_id, product_id) in self._grants


def _make_user(user_id="user-001"):
    return User(user_id=user_id, display_name="Jordan Smith")


def test_entitlement_checker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        EntitlementChecker()


def test_has_access_returns_false_when_no_grant_exists():
    checker = _FakeEntitlementChecker()

    assert checker.has_access(_make_user(), "trading_intelligence") is False


def test_has_access_returns_true_when_a_grant_exists():
    user = _make_user()
    checker = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})

    assert checker.has_access(user, "trading_intelligence") is True


def test_has_access_is_scoped_per_product():
    user = _make_user()
    checker = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})

    assert checker.has_access(user, "wealth_intelligence") is False


def test_incomplete_entitlement_checker_subclass_cannot_be_instantiated():
    class _Incomplete(EntitlementChecker):
        pass  # has_access deliberately not implemented

    with pytest.raises(TypeError):
        _Incomplete()
