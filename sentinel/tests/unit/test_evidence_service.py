"""Test shells for services/evidence_service.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_record_persists_evidence_immutably():
    """EvidenceService.record() should not allow updating an already-recorded artifact."""


def test_get_by_decision_returns_all_linked_evidence():
    """EvidenceService.get_by_decision() should return every Evidence for a decision_id."""
