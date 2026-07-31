"""Test shells for api/evidence_api.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_get_evidence_for_decision_returns_dict_with_evidence_list():
    """GET /api/decisions/{id}/evidence should return {decision_id, evidence: [...]}, not a bare list."""
