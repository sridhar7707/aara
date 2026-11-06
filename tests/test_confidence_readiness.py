"""ADR-081 3.2: Wilson interval for the readiness win rate."""
from scripts.confidence_check import wilson_interval


def test_wilson_interval_matches_reference_for_8_of_13():
    low, high = wilson_interval(8, 13)
    assert round(low, 2) == 0.36
    assert round(high, 2) == 0.82


def test_wilson_interval_with_no_trades_is_uninformative():
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_wilson_interval_stays_inside_zero_and_one():
    for wins, n in [(0, 5), (5, 5), (1, 1000)]:
        low, high = wilson_interval(wins, n)
        assert 0.0 <= low <= high <= 1.0
