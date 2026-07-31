"""Test shells for api/portfolio_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_portfolio_health_returns_mock_data_in_phase_2a():
    """GET /api/portfolio/health should return simulated data; no real broker state."""


def test_get_portfolio_positions_includes_tax_lots():
    """GET /api/portfolio/positions should include per-lot days_held and tax_term."""


def test_get_tax_analysis_flags_wash_sale_risk():
    """GET /api/portfolio/tax-analysis should surface wash_sale_risk per position."""
