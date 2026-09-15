import pytest

from applications.trading_intelligence.ui.risk_intelligence.screen import (
    CURRENT_RISK_PARAMETERS,
    ConcentrationHolding,
    DrawdownPoint,
    RiskHistoryEntry,
    RiskParameter,
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


def test_snapshot_requires_only_state_and_as_of():
    """Slice B: state + as_of are the only fields the operational
    risk_state table can supply, so they stay required; trigger_reason and
    the two sizing figures are Optional and default to None."""
    snapshot = RiskSnapshot(state="NORMAL", as_of="2026-08-20 10:03 CDT")

    assert snapshot.state == "NORMAL"
    assert snapshot.as_of == "2026-08-20 10:03 CDT"
    assert snapshot.trigger_reason is None
    assert snapshot.recommended_sizing_pct is None
    assert snapshot.actual_sizing_pct is None


def test_snapshot_still_validates_state_when_the_other_fields_are_omitted():
    with pytest.raises(ValueError):
        RiskSnapshot(state="CRITICAL", as_of="2026-08-20 10:03 CDT")


def test_sizing_gap_pct_is_none_when_recommended_is_missing():
    snapshot = RiskSnapshot(
        state="NORMAL", as_of="2026-08-20 10:03 CDT", actual_sizing_pct=100.0,
    )

    assert snapshot.sizing_gap_pct is None


def test_sizing_gap_pct_is_none_when_actual_is_missing():
    snapshot = RiskSnapshot(
        state="NORMAL", as_of="2026-08-20 10:03 CDT", recommended_sizing_pct=100.0,
    )

    assert snapshot.sizing_gap_pct is None


def test_sizing_gap_pct_is_none_when_both_are_missing():
    snapshot = RiskSnapshot(state="NORMAL", as_of="2026-08-20 10:03 CDT")

    assert snapshot.sizing_gap_pct is None


def test_screen_with_a_partial_snapshot_is_available_and_empty():
    """A state-only snapshot is still a real, available screen -- it just
    has no history and no reason/sizing detail."""
    screen = RiskScreen(current=RiskSnapshot(state="WARNING", as_of="2026-08-20 10:03 CDT"))

    assert screen.is_available is True
    assert screen.is_empty is True
    assert screen.history == ()


def test_risk_screen_is_empty_with_no_history():
    screen = RiskScreen(current=_make_snapshot())

    assert screen.is_empty
    assert screen.empty_state_message == (
        "Risk evaluation history is not recorded in this data source."
    )


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


# --- Concentration -----------------------------------------------------


def test_concentration_holding_is_immutable():
    holding = ConcentrationHolding(symbol="AAPL", weight_pct=45.0)

    assert holding.symbol == "AAPL"
    assert holding.weight_pct == 45.0
    with pytest.raises(Exception):
        holding.weight_pct = 50.0


def test_concentration_unavailable_by_default():
    """No concentration_holdings supplied -> unavailable, matching every
    other None-vs-empty convention on this screen (drawdown_history,
    history)."""
    screen = RiskScreen()

    assert screen.concentration_is_available is False
    assert screen.concentration_holdings is None


def test_concentration_populated():
    holdings = (
        ConcentrationHolding(symbol="AAPL", weight_pct=60.0),
        ConcentrationHolding(symbol="MSFT", weight_pct=40.0),
    )
    screen = RiskScreen(concentration_holdings=holdings)

    assert screen.concentration_is_available is True
    assert screen.concentration_is_empty is False
    assert screen.concentration_holdings == holdings


def test_concentration_empty_is_a_real_healthy_zero_positions_state():
    """An empty tuple is a genuine 'connected, no open positions' result,
    distinct from None (unavailable) -- same convention as
    drawdown_history_is_empty / portfolio_history_is_empty elsewhere in
    this product."""
    screen = RiskScreen(concentration_holdings=())

    assert screen.concentration_is_available is True
    assert screen.concentration_is_empty is True
    assert screen.concentration_empty_state_message == (
        "No open positions to show concentration for."
    )


def test_largest_concentration_holding_picks_the_highest_weight():
    holdings = (
        ConcentrationHolding(symbol="AAPL", weight_pct=30.0),
        ConcentrationHolding(symbol="MSFT", weight_pct=55.0),
        ConcentrationHolding(symbol="GOOGL", weight_pct=15.0),
    )
    screen = RiskScreen(concentration_holdings=holdings)

    assert screen.largest_concentration_holding == ConcentrationHolding(
        symbol="MSFT", weight_pct=55.0
    )


def test_largest_concentration_holding_breaks_ties_alphabetically():
    """Deterministic tie-break -- same rule Portfolio Intelligence's own
    Allocation by Holding bar list uses (weight_pct descending, symbol
    ascending)."""
    holdings = (
        ConcentrationHolding(symbol="ZETA", weight_pct=50.0),
        ConcentrationHolding(symbol="ALPHA", weight_pct=50.0),
    )
    screen = RiskScreen(concentration_holdings=holdings)

    assert screen.largest_concentration_holding.symbol == "ALPHA"


def test_largest_concentration_holding_none_when_unavailable():
    screen = RiskScreen()

    assert screen.largest_concentration_holding is None


def test_largest_concentration_holding_none_when_empty():
    screen = RiskScreen(concentration_holdings=())

    assert screen.largest_concentration_holding is None


def test_risk_screen_stays_frozen_for_concentration_fields():
    screen = RiskScreen()

    with pytest.raises(Exception):
        screen.concentration_holdings = ()


# --- Risk Parameters (static, read-only) --------------------------------


def test_risk_parameter_is_immutable():
    param = RiskParameter(label="Max Open Positions", value_display="8")

    assert param.label == "Max Open Positions"
    assert param.value_display == "8"
    with pytest.raises(Exception):
        param.value_display = "10"


def test_current_risk_parameters_contains_the_six_documented_values():
    labels = {p.label: p.value_display for p in CURRENT_RISK_PARAMETERS}

    assert labels == {
        "Max Position Size": "20% of portfolio",
        "Max Risk Per Trade": "1.5% of portfolio",
        "Max Position Drift": "25%",
        "Max Open Positions": "8",
        "Correlation Threshold": "0.85",
        "MACD Confirmation Minimum": "Disabled",
    }


def test_current_risk_parameters_is_a_fixed_tuple_not_a_screen_field():
    """Static, compile-time content -- never sourced from a RiskScreen
    instance, never gated on availability/health (it is not a live read)."""
    assert isinstance(CURRENT_RISK_PARAMETERS, tuple)
    assert len(CURRENT_RISK_PARAMETERS) == 6


# --- Current drawdown context --------------------------------------------


def test_current_drawdown_pct_none_when_drawdown_history_unavailable():
    screen = RiskScreen()

    assert screen.current_drawdown_pct is None


def test_current_drawdown_pct_none_when_drawdown_history_is_empty():
    screen = RiskScreen(drawdown_history=())

    assert screen.current_drawdown_pct is None


def test_current_drawdown_pct_is_the_latest_points_own_value():
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=0.0),
        DrawdownPoint(as_of="2026-09-02T00:00:00+00:00", portfolio_value=95000.0, drawdown_pct=5.0),
    )
    screen = RiskScreen(drawdown_history=points)

    assert screen.current_drawdown_pct == 5.0


def test_current_drawdown_pct_is_zero_at_a_new_peak():
    points = (
        DrawdownPoint(as_of="2026-09-01T00:00:00+00:00", portfolio_value=100000.0, drawdown_pct=0.0),
    )
    screen = RiskScreen(drawdown_history=points)

    assert screen.current_drawdown_pct == 0.0
