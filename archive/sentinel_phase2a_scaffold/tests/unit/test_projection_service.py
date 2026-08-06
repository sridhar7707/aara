"""Test shells for services/projection_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_decision_view_never_exposes_raw_events():
    """ProjectionService.get_decision_view() must return a derived view, not Event objects."""


def test_get_portfolio_health_is_precalculated():
    """ProjectionService.get_portfolio_health() should return pre-calculated metrics only."""
