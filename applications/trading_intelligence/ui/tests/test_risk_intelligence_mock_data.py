from applications.trading_intelligence.ui.risk_intelligence.mock_data import build_mock_screen


def test_build_mock_screen_returns_a_non_empty_screen():
    screen = build_mock_screen()

    assert not screen.is_empty
    assert len(screen.history) == 5


def test_mock_current_state_is_a_valid_state():
    screen = build_mock_screen()

    assert screen.current.state in ("NORMAL", "WARNING", "DEFENSIVE")


def test_mock_history_includes_every_state_at_least_once():
    screen = build_mock_screen()

    states = {entry.state for entry in screen.history}

    assert states == {"NORMAL", "WARNING", "DEFENSIVE"}


def test_mock_current_snapshot_has_a_non_empty_trigger_reason():
    screen = build_mock_screen()

    assert screen.current.trigger_reason.strip() != ""


def test_mock_history_entries_each_have_a_non_empty_trigger_reason():
    screen = build_mock_screen()

    assert all(entry.trigger_reason.strip() != "" for entry in screen.history)


def test_mock_sizing_percentages_are_within_zero_to_one_hundred():
    screen = build_mock_screen()

    all_snapshots = [screen.current, *screen.history]
    for snapshot in all_snapshots:
        assert 0.0 <= snapshot.recommended_sizing_pct <= 100.0
        assert 0.0 <= snapshot.actual_sizing_pct <= 100.0
