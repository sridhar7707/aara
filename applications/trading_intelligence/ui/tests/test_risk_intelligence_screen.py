import pytest

from applications.trading_intelligence.ui.risk_intelligence.screen import (
    RiskHistoryEntry,
    RiskScreen,
    RiskSnapshot,
)


def _make_snapshot(**overrides):
    defaults = dict(
        state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0,
        actual_sizing_pct=100.0,
        as_of="2026-08-18 14:00 UTC",
    )
    defaults.update(overrides)
    return RiskSnapshot(**defaults)


def _make_history_entry(**overrides):
    defaults = dict(
        timestamp="2026-08-18 14:00 UTC",
        state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0,
        actual_sizing_pct=100.0,
    )
    defaults.update(overrides)
    return RiskHistoryEntry(**defaults)


@pytest.mark.parametrize("state", ["NORMAL", "WARNING", "DEFENSIVE"])
def test_snapshot_accepts_every_valid_state(state):
    snapshot = _make_snapshot(state=state)

    assert snapshot.state == state


def test_snapshot_rejects_an_invalid_state():
    with pytest.raises(ValueError):
        _make_snapshot(state="CRITICAL")


@pytest.mark.parametrize("state", ["NORMAL", "WARNING", "DEFENSIVE"])
def test_history_entry_accepts_every_valid_state(state):
    entry = _make_history_entry(state=state)

    assert entry.state == state


def test_history_entry_rejects_an_invalid_state():
    with pytest.raises(ValueError):
        _make_history_entry(state="UNKNOWN")


def test_sizing_gap_pct_is_recommended_minus_actual():
    snapshot = _make_snapshot(recommended_sizing_pct=75.0, actual_sizing_pct=70.0)

    assert snapshot.sizing_gap_pct == 5.0


def test_sizing_gap_pct_is_zero_when_recommended_matches_actual():
    snapshot = _make_snapshot(recommended_sizing_pct=100.0, actual_sizing_pct=100.0)

    assert snapshot.sizing_gap_pct == 0.0


def test_sizing_gap_pct_can_be_negative_when_actual_exceeds_recommended():
    snapshot = _make_snapshot(recommended_sizing_pct=50.0, actual_sizing_pct=60.0)

    assert snapshot.sizing_gap_pct == -10.0


def test_risk_screen_is_empty_with_no_history():
    screen = RiskScreen(current=_make_snapshot())

    assert screen.is_empty
    assert screen.empty_state_message == "No risk evaluations recorded yet."


def test_risk_screen_is_not_empty_with_history():
    screen = RiskScreen(current=_make_snapshot(), history=(_make_history_entry(),))

    assert not screen.is_empty


def test_risk_screen_defaults_to_unavailable():
    screen = RiskScreen()

    assert screen.current is None
    assert screen.is_available is False
    assert screen.history == ()
    assert screen.unavailable_message == "Risk Intelligence data is currently unavailable."


def test_risk_screen_is_available_once_a_snapshot_is_supplied():
    screen = RiskScreen(current=_make_snapshot())

    assert screen.is_available is True


def test_risk_screen_stays_frozen():
    screen = RiskScreen()

    with pytest.raises(Exception):
        screen.current = _make_snapshot()
