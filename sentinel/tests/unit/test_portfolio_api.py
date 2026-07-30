"""Test shells for api/portfolio_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_portfolio_health_returns_mock_data_in_phase_2a():
    """GET /api/v1/portfolio/health should return simulated data; no real broker state."""
