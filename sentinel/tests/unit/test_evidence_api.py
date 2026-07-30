"""Test shells for api/evidence_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_evidence_for_decision_returns_list():
    """GET /api/v1/decisions/{id}/evidence should return all Evidence for that decision."""
