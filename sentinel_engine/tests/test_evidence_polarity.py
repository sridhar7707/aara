"""Tests for sentinel_engine.evidence.evidence_polarity."""
from sentinel_engine.evidence.evidence_polarity import EvidencePolarity


def test_all_expected_evidence_polarities_exist():
    assert EvidencePolarity.SUPPORTING == "SUPPORTING"
    assert EvidencePolarity.CONTRADICTING == "CONTRADICTING"


def test_evidence_polarity_has_exactly_two_members():
    assert len(list(EvidencePolarity)) == 2


def test_evidence_polarity_members_are_strings():
    for member in EvidencePolarity:
        assert isinstance(member.value, str)


def test_valid_evidence_polarity_strings_are_recognized():
    assert EvidencePolarity.has_value("SUPPORTING") is True
    assert EvidencePolarity.has_value("CONTRADICTING") is True


def test_invalid_evidence_polarity_string_is_rejected():
    assert EvidencePolarity.has_value("NEUTRAL") is False
    assert EvidencePolarity.has_value("") is False
