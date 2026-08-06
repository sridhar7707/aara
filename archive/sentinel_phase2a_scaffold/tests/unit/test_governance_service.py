"""Test shells for services/governance_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_evaluate_returns_governance_with_current_policy_version():
    """GovernanceService.evaluate() should stamp the decision with get_policy_version()."""


def test_evaluate_does_not_bypass_failed_checks():
    """A failed governance check must escalate, never be silently overridden."""
