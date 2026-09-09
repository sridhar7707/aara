"""Tests for sentinel_engine.domain.horizon."""
from sentinel_engine.domain.horizon import Horizon


def test_all_expected_horizons_exist():
    assert Horizon.TACTICAL == "TACTICAL"
    assert Horizon.MEDIUM == "MEDIUM"
    assert Horizon.LONG == "LONG"


def test_horizon_has_exactly_three_members():
    assert len(list(Horizon)) == 3


def test_horizon_members_are_strings():
    for member in Horizon:
        assert isinstance(member.value, str)


def test_valid_horizon_strings_are_recognized():
    assert Horizon.has_value("TACTICAL") is True
    assert Horizon.has_value("MEDIUM") is True
    assert Horizon.has_value("LONG") is True


def test_invalid_horizon_string_is_rejected():
    assert Horizon.has_value("SHORT_TERM") is False
    assert Horizon.has_value("") is False
