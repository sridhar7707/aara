"""Test shells for api/decision_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_decision_returns_projection_shape():
    """GET /api/decisions/{id} should match the frontend data contract JSON schema."""


def test_get_pending_decisions_returns_list():
    """GET /api/decisions/pending should return only non-terminal decisions."""


def test_list_decisions_applies_filters():
    """GET /api/decisions should honor state/asset/date/quality_score_min filters."""


def test_list_decisions_paginates():
    """GET /api/decisions should respect limit/offset and return total count."""


def test_get_decision_timeline_returns_ordered_states():
    """GET /api/decisions/{id}/timeline should return lifecycle entries in timestamp order."""
