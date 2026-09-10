"""Tests for services.decision_calibration_query_service.

`DecisionCalibrationQueryService` is a pure fold over an already-built
Wave 2A `OutcomeLineage`: no database access, no I/O, no Gradio import,
deterministic. It groups CLOSED BUY decision outcomes by the ensemble
score recorded at entry and tallies realized WIN / LOSS counts per band.

This is a historical realized-outcome view only -- it makes no
predictive-accuracy or statistical-significance claim, and these tests
assert none.
"""
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
    OutcomeDirection,
    OutcomeLineage,
    OutcomeStatus,
    PairingConfidence,
    PairingMethod,
)
from applications.trading_intelligence.projections.calibration_band import CalibrationBand
from applications.trading_intelligence.services.decision_calibration_query_service import (
    BAND_LABELS,
    DecisionCalibrationQueryService,
)

_ID = 0


def _outcome(
    *,
    status=OutcomeStatus.CLOSED,
    direction=OutcomeDirection.WIN,
    score=0.60,
):
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
        entry_ensemble_score=score,
    )


def _lineage(*outcomes):
    return OutcomeLineage(decisions=tuple(outcomes), excluded_sells=())


def _calibrate(*outcomes):
    return DecisionCalibrationQueryService().get_calibration(_lineage(*outcomes))


def _band(bands, label):
    (match,) = [b for b in bands if b.label == label]
    return match


# --- shape -----------------------------------------------------------------


def test_returns_the_four_fixed_bands_in_a_stable_order():
    bands = _calibrate()
    assert [b.label for b in bands] == list(BAND_LABELS)
    assert BAND_LABELS == ("0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-1.00")


def test_empty_input_yields_four_all_zero_bands():
    bands = _calibrate()
    for b in bands:
        assert (b.n, b.wins, b.losses) == (0, 0, 0)
        assert b.win_rate is None


# --- inclusion / exclusion ----------------------------------------------------


def test_closed_win_is_counted():
    bands = _calibrate(_outcome(direction=OutcomeDirection.WIN, score=0.60))
    b = _band(bands, "0.60-0.65")
    assert (b.n, b.wins, b.losses) == (1, 1, 0)
    assert b.win_rate == 1.0


def test_closed_loss_is_counted():
    bands = _calibrate(_outcome(direction=OutcomeDirection.LOSS, score=0.60))
    b = _band(bands, "0.60-0.65")
    assert (b.n, b.wins, b.losses) == (1, 0, 1)
    assert b.win_rate == 0.0


def test_flat_outcome_is_excluded():
    bands = _calibrate(_outcome(direction=OutcomeDirection.FLAT, score=0.60))
    assert all(b.n == 0 for b in bands)


def test_none_outcome_direction_is_excluded():
    bands = _calibrate(_outcome(direction=None, score=0.60))
    assert all(b.n == 0 for b in bands)


def test_non_closed_outcome_is_excluded():
    for status in (
        OutcomeStatus.OPEN,
        OutcomeStatus.PARTIAL,
        OutcomeStatus.AMBIGUOUS,
    ):
        bands = _calibrate(
            _outcome(status=status, direction=OutcomeDirection.WIN, score=0.60)
        )
        assert all(b.n == 0 for b in bands), status


def test_missing_entry_ensemble_score_is_excluded():
    bands = _calibrate(_outcome(score=None))
    assert all(b.n == 0 for b in bands)


def test_score_below_the_first_band_is_excluded():
    bands = _calibrate(_outcome(score=0.49))
    assert all(b.n == 0 for b in bands)


def test_score_above_the_final_band_is_excluded():
    bands = _calibrate(_outcome(score=1.01))
    assert all(b.n == 0 for b in bands)


# --- boundary behavior ------------------------------------------------------


def test_exact_lower_boundaries_fall_in_the_band_they_open():
    for score, label in (
        (0.50, "0.50-0.55"),
        (0.55, "0.55-0.60"),
        (0.60, "0.60-0.65"),
        (0.65, "0.65-1.00"),
    ):
        bands = _calibrate(_outcome(score=score))
        assert _band(bands, label).n == 1, (score, label)
        assert sum(b.n for b in bands) == 1


def test_upper_boundaries_are_exclusive_except_the_final_band():
    # 0.55 belongs to the SECOND band, not the first (upper bound exclusive).
    bands = _calibrate(_outcome(score=0.55))
    assert _band(bands, "0.50-0.55").n == 0
    assert _band(bands, "0.55-0.60").n == 1

    # just under an internal boundary stays in the lower band
    bands = _calibrate(_outcome(score=0.5499))
    assert _band(bands, "0.50-0.55").n == 1


def test_final_band_includes_its_upper_bound_of_one():
    bands = _calibrate(_outcome(score=1.00))
    assert _band(bands, "0.65-1.00").n == 1


def test_final_band_covers_the_whole_range_at_and_above_0_65():
    bands = _calibrate(
        _outcome(score=0.65),
        _outcome(score=0.80),
        _outcome(score=0.999),
        _outcome(score=1.00),
    )
    assert _band(bands, "0.65-1.00").n == 4


# --- tally correctness -----------------------------------------------------


def test_counts_wins_losses_and_n_per_band_without_cross_band_aggregation():
    bands = _calibrate(
        _outcome(direction=OutcomeDirection.WIN, score=0.51),
        _outcome(direction=OutcomeDirection.WIN, score=0.52),
        _outcome(direction=OutcomeDirection.LOSS, score=0.53),
        _outcome(direction=OutcomeDirection.WIN, score=0.61),
        _outcome(direction=OutcomeDirection.LOSS, score=0.62),
        _outcome(direction=OutcomeDirection.LOSS, score=0.63),
    )
    first = _band(bands, "0.50-0.55")
    third = _band(bands, "0.60-0.65")

    assert (first.n, first.wins, first.losses) == (3, 2, 1)
    assert (third.n, third.wins, third.losses) == (3, 1, 2)
    # the untouched bands stay at zero -- nothing is aggregated across bands
    assert _band(bands, "0.55-0.60").n == 0
    assert _band(bands, "0.65-1.00").n == 0


def test_win_rate_is_wins_over_wins_plus_losses():
    bands = _calibrate(
        _outcome(direction=OutcomeDirection.WIN, score=0.61),
        _outcome(direction=OutcomeDirection.WIN, score=0.62),
        _outcome(direction=OutcomeDirection.WIN, score=0.63),
        _outcome(direction=OutcomeDirection.LOSS, score=0.64),
    )
    assert _band(bands, "0.60-0.65").win_rate == 0.75


def test_win_rate_never_divides_by_zero_for_an_unpopulated_band():
    bands = _calibrate(_outcome(score=0.60))
    empty = _band(bands, "0.50-0.55")
    assert empty.n == 0
    assert empty.win_rate is None


def test_result_is_deterministic_for_the_same_input():
    outcomes = [
        _outcome(direction=OutcomeDirection.WIN, score=0.58),
        _outcome(direction=OutcomeDirection.LOSS, score=0.72),
        _outcome(direction=OutcomeDirection.WIN, score=0.51),
    ]
    a = DecisionCalibrationQueryService().get_calibration(_lineage(*outcomes))
    b = DecisionCalibrationQueryService().get_calibration(_lineage(*outcomes))
    assert a == b


def test_bands_are_calibration_band_instances():
    bands = _calibrate(_outcome(score=0.60))
    assert all(isinstance(b, CalibrationBand) for b in bands)
