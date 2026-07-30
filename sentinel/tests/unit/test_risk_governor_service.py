"""Test shells for services/risk_governor_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_check_threshold_only_returns_three_states():
    """RiskGovernorService.check_threshold() must return NORMAL, WARNING, or DEFENSIVE."""


def test_breach_beyond_defensive_is_not_a_fourth_state():
    """Drawdown beyond DEFENSIVE's threshold should raise/record a breach event, not a new enum value."""
