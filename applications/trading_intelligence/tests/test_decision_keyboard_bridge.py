"""Guards for the Decisions-table keyboard bridge (decision_center/gradio_view.py).

Browser behaviour was verified with Playwright on Gradio 4.44.1 and 5.50.0 against the same
populated trades data: Enter on a focused cell selects it, and ArrowUp/ArrowDown move to the
same column in the adjacent row and select it. These string-level guards keep the parts that
made that work from being removed silently.
"""
from applications.trading_intelligence.ui.decision_center import gradio_view as dc_view

BRIDGE = dc_view._KEYBOARD_SELECTION_BRIDGE_JS


def test_bridge_listens_in_the_capture_phase_so_arrow_keys_reach_it_first():
    # Gradio's own table handler calls preventDefault() on arrows once a cell is selected.
    assert BRIDGE.rstrip().endswith("}, true);\n})();\n</script>")


def test_data_rows_are_found_without_the_slot_marker_gradio_does_not_emit():
    assert 'getAttribute("slot")' not in BRIDGE
    assert "function isDataRow" in BRIDGE
    assert 'closest(\'[aria-hidden="true"]\')' in BRIDGE  # measuring row excluded


def test_selection_uses_pointer_events_because_element_click_does_not_select():
    assert "pointerdown" in BRIDGE and "mousedown" in BRIDGE and "function pressCell" in BRIDGE


def test_focus_is_restored_after_the_server_round_trip_with_stale_retries_ignored():
    assert "function refocusDecisionCell" in BRIDGE
    assert "navGeneration" in BRIDGE
    assert "[80, 300, 700, 1200, 2000]" in BRIDGE


def test_arrow_keys_move_within_the_decisions_table_only():
    assert 'event.key === "ArrowDown" || event.key === "ArrowUp"' in BRIDGE
    assert 'findDecisionCell(event.target)' in BRIDGE
