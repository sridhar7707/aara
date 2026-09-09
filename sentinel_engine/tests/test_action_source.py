"""Tests for sentinel_engine.domain.action_source.ActionSource (ADR-069 B2)."""
from sentinel_engine.domain.action_source import ActionSource


def test_action_source_has_exactly_two_members():
    assert [m.value for m in ActionSource] == ["STRATEGY", "SENTINEL"]
    assert len(list(ActionSource)) == 2


def test_expected_action_sources_exist():
    assert ActionSource.STRATEGY == "STRATEGY"
    assert ActionSource.SENTINEL == "SENTINEL"


def test_action_source_members_are_strings():
    for member in ActionSource:
        assert isinstance(member.value, str)


def test_valid_action_source_strings_are_recognized():
    assert ActionSource.has_value("STRATEGY") is True
    assert ActionSource.has_value("SENTINEL") is True


def test_invalid_action_source_strings_are_rejected():
    for bad in ("SENTINEL_CONCUR", "sentinel", "STRATEGY ", "NONE", "", "REJECT"):
        assert ActionSource.has_value(bad) is False


def test_no_third_provenance_value_is_introduced():
    assert set(m.value for m in ActionSource) == {"STRATEGY", "SENTINEL"}
