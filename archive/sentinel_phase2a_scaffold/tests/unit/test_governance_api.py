"""Test shells for api/governance_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_governance_state_returns_three_state_enum_value():
    """GET /api/governance/state should return NORMAL, WARNING, or DEFENSIVE only."""


def test_get_governance_evaluations_includes_escalations():
    """GET /api/governance/evaluations/{id} should include escalation review details when present."""
