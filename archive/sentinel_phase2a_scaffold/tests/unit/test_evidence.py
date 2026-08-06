"""Test shells for domain/evidence.py. No implementation yet."""

import pytest

pytestmark = pytest.mark.skip(reason="scaffolding: not implemented yet")


def test_evidence_carries_full_provenance():
    """Evidence must carry provider, version, data_as_of, and recorded_at."""


def test_evidence_assessment_score_is_not_a_probability():
    """EvidenceAssessment.score is an internal analytical score, not a return probability."""
