"""Tests for services.decision_regime_outcome_query_service.

`DecisionRegimeOutcomeQueryService` is a pure fold over an already-built
Wave 2A `OutcomeLineage`: no database access, no I/O, no Gradio import,
deterministic. It groups CLOSED BUY decision outcomes by the market
regime recorded at entry (`DecisionOutcome.entry_regime`, verbatim) and
tallies realized WIN / LOSS counts per regime.

Eligibility mirrors the Sprint 4 Item #1 calibration fold exactly, minus
the ensemble-score gate (which does not apply here): an outcome counts
only when its status is CLOSED and its outcome_direction is WIN or LOSS.
This is a historical realized-outcome breakdown -- it makes no
predictive, probability, or calibration claim, and asserting one regime
caused better outcomes is out of scope.
"""
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
    OutcomeDirection,
    OutcomeLineage,
    OutcomeStatus,
    PairingConfidence,
    PairingMethod,
)
from applications.trading_intelligence.projections.regime_outcome_row import (
    REGIME_NOT_RECORDED_LABEL,
    RegimeOutcomeRow,
)
from applications.trading_intelligence.services.decision_regime_outcome_query_service import (
    DecisionRegimeOutcomeQueryService,
)

_ID = 0


def _outcome(*, status=OutcomeStatus.CLOSED, direction=OutcomeDirection.WIN, regime="RANGING"):
    global _ID
    _ID += 1
    return DecisionOutcome(
        decision_id="trade-{}".format(_ID),
        symbol="AAA",
        entry_trade_id=_ID,
        entry_timestamp="2026-06-01T00:00:00+00:00",
        entry_price=10.0,
        entry_shares=1.0,
        status=status,
        pairing_method=PairingMethod.WINDOW_SINGLE_BOT_EXIT,
        pairing_confidence=PairingConfidence.HIGH,
        outcome_direction=direction,
        entry_regime=regime,
    )


def _lineage(*outcomes):
    return OutcomeLineage(decisions=tuple(outcomes), excluded_sells=())


def _rows(*outcomes):
    return DecisionRegimeOutcomeQueryService().get_regime_outcomes(_lineage(*outcomes))


def _by_label(rows):
    return {row.regime: row for row in rows}


# --- shape / empties -----------------------------------------------------


def test_empty_lineage_yields_no_rows():
    assert _rows() == ()


def test_a_regime_with_only_ineligible_outcomes_produces_no_row():
    rows = _rows(
        _outcome(status=OutcomeStatus.OPEN, regime="RANGING"),
        _outcome(direction=OutcomeDirection.FLAT, regime="RANGING"),
    )
    assert rows == ()


def test_rows_are_regime_outcome_row_instances():
    rows = _rows(_outcome(regime="RANGING"))
    assert all(isinstance(r, RegimeOutcomeRow) for r in rows)


# --- grouping / counting ------------------------------------------------


def test_groups_by_the_verbatim_entry_regime_value():
    rows = _rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="TRENDING", direction=OutcomeDirection.WIN),
    )
    assert sorted(r.regime for r in rows) == ["RANGING", "TRENDING"]


def test_counts_wins_and_losses_per_regime_without_cross_regime_mixing():
    rows = _by_label(_rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.LOSS),
        _outcome(regime="TRENDING", direction=OutcomeDirection.LOSS),
    ))
    assert (rows["RANGING"].wins, rows["RANGING"].losses, rows["RANGING"].n) == (2, 1, 3)
    assert (rows["TRENDING"].wins, rows["TRENDING"].losses, rows["TRENDING"].n) == (0, 1, 1)


def test_win_rate_is_wins_over_wins_plus_losses():
    rows = _by_label(_rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.LOSS),
    ))
    assert rows["RANGING"].win_rate == 0.75


def test_win_rate_never_divides_by_zero_for_an_empty_row():
    row = RegimeOutcomeRow(regime="RANGING", wins=0, losses=0)
    assert row.n == 0
    assert row.win_rate is None


# --- eligibility (mirrors the calibration fold) ------------------------


def test_flat_outcomes_are_excluded():
    rows = _rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.FLAT),
    )
    assert _by_label(rows)["RANGING"].n == 1


def test_none_outcome_direction_is_excluded():
    rows = _rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=None),
    )
    assert _by_label(rows)["RANGING"].n == 1


def test_non_closed_outcomes_are_excluded():
    for status in (OutcomeStatus.OPEN, OutcomeStatus.PARTIAL, OutcomeStatus.AMBIGUOUS):
        rows = _rows(
            _outcome(regime="RANGING", status=OutcomeStatus.CLOSED,
                     direction=OutcomeDirection.WIN),
            _outcome(regime="RANGING", status=status, direction=OutcomeDirection.WIN),
        )
        assert _by_label(rows)["RANGING"].n == 1, status


# --- missing / unknown regime -----------------------------------------


def test_none_entry_regime_is_bucketed_explicitly_not_dropped():
    rows = _rows(_outcome(regime=None, direction=OutcomeDirection.WIN))
    assert [r.regime for r in rows] == [REGIME_NOT_RECORDED_LABEL]
    assert rows[0].wins == 1


def test_blank_and_whitespace_entry_regime_join_the_not_recorded_bucket():
    rows = _by_label(_rows(
        _outcome(regime="", direction=OutcomeDirection.WIN),
        _outcome(regime="   ", direction=OutcomeDirection.LOSS),
    ))
    assert set(rows) == {REGIME_NOT_RECORDED_LABEL}
    assert (rows[REGIME_NOT_RECORDED_LABEL].wins, rows[REGIME_NOT_RECORDED_LABEL].losses) == (1, 1)


def test_not_recorded_bucket_sorts_last_and_real_regimes_sort_alphabetically():
    rows = _rows(
        _outcome(regime="TRENDING", direction=OutcomeDirection.WIN),
        _outcome(regime=None, direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="BREAKOUT", direction=OutcomeDirection.WIN),
    )
    assert [r.regime for r in rows] == [
        "BREAKOUT", "RANGING", "TRENDING", REGIME_NOT_RECORDED_LABEL,
    ]


def test_regime_values_are_used_verbatim_and_not_normalised():
    # no invented business semantics: distinct source strings stay distinct
    # groups (no case-folding, no relabelling).
    rows = _by_label(_rows(
        _outcome(regime="RANGING", direction=OutcomeDirection.WIN),
        _outcome(regime="ranging", direction=OutcomeDirection.LOSS),
    ))
    assert set(rows) == {"RANGING", "ranging"}


# --- determinism -----------------------------------------------------


def test_result_is_deterministic_for_the_same_input():
    outcomes = [
        _outcome(regime="TRENDING", direction=OutcomeDirection.WIN),
        _outcome(regime="RANGING", direction=OutcomeDirection.LOSS),
        _outcome(regime=None, direction=OutcomeDirection.WIN),
    ]
    a = DecisionRegimeOutcomeQueryService().get_regime_outcomes(_lineage(*outcomes))
    b = DecisionRegimeOutcomeQueryService().get_regime_outcomes(_lineage(*outcomes))
    assert a == b
