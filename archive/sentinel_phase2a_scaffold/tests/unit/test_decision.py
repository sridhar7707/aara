"""Test shells for domain/decision.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_decision_is_created_with_identified_state():
    """A new Decision should be constructible with DecisionState.IDENTIFIED."""


def test_decision_requires_evidence_assessment():
    """Decision.evidence_assessment must be an EvidenceAssessment, not raw evidence."""
