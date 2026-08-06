"""Test shells for domain/governance.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_risk_state_uses_three_state_enum():
    """RiskState.current_state must be one of NORMAL/WARNING/DEFENSIVE (no CRITICAL)."""


def test_governance_records_policy_version():
    """Governance.policy_version must be present for auditability."""
