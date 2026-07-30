"""Test shells for api/decision_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_decision_returns_projection_shape():
    """GET /api/v1/decisions/{id} should match the frontend data contract JSON schema."""


def test_get_pending_decisions_returns_list():
    """GET /api/v1/decisions/pending should return only non-terminal decisions."""
