"""Tests for adapters.trade_outcome_derivation.derive_outcomes.

All functions under test are pure -- these tests never touch a database,
except the opt-in production-snapshot regression at the end, which is
skipped unless AARA_WAVE2A_PROD_SNAPSHOT points at a real 42-row
``trades.db``.
"""
import os
import random
from collections import Counter

import pytest

from applications.trading_intelligence.adapters.trade_outcome_derivation import (
    derive_outcomes,
)
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    ExcludedSellReason,
    ExitBasis,
    OutcomeDirection,
    OutcomeStatus,
    PairingConfidence,
    PairingMethod,
)
from applications.trading_intelligence.projections.trade_outcome_row import TradeOutcomeRow

_BOT_ACTIONS = ("SELL_STOP", "SELL_TIME_EXIT")
_UNSET = object()


def _buy(trade_id, symbol="AAA", ts=None, shares=100.0, price=10.0,
         ensemble_score=0.6, regime="RANGING"):
    return TradeOutcomeRow(
        id=trade_id,
        timestamp=ts or "2026-06-01T00:00:{:02d}+00:00".format(trade_id % 60),
        symbol=symbol,
        action="BUY",
        shares=shares,
        price=price,
        notional=(shares or 0.0) * (price or 0.0),
        realized_pnl=0.0,
        pnl_pct=0.0,
        holding_days=0,
        order_id="buy-{}".format(trade_id),
        ensemble_score=ensemble_score,
        regime=regime,
    )


def _sell(trade_id, symbol="AAA", ts=None, action="SELL_TIME_EXIT", shares=100.0,
          price=11.0, realized_pnl=100.0, pnl_pct=0.1, holding_days=7,
          order_id=_UNSET):
    if order_id is _UNSET:
        order_id = "sell-{}".format(trade_id) if action in _BOT_ACTIONS else None
    return TradeOutcomeRow(
        id=trade_id,
        timestamp=ts or "2026-07-01T00:00:{:02d}+00:00".format(trade_id % 60),
        symbol=symbol,
        action=action,
        shares=shares,
        price=price,
        notional=(shares or 0.0) * (price or 0.0),
        realized_pnl=realized_pnl,
        pnl_pct=pnl_pct,
        holding_days=holding_days,
        order_id=order_id,
        ensemble_score=None,
        regime=None,
    )


# ---------------------------------------------------------------- case 1
def test_clean_single_bot_exit():
    lineage = derive_outcomes([_buy(1), _sell(2, realized_pnl=-15.0)])
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.pairing_method is PairingMethod.WINDOW_SINGLE_BOT_EXIT
    assert outcome.pairing_confidence is PairingConfidence.HIGH
    assert outcome.exit_basis is ExitBasis.BOT_FILL
    assert outcome.exit_trade_id == 2
    assert outcome.realized_pnl_usd == -15.0
    assert outcome.outcome_direction is OutcomeDirection.LOSS
    assert lineage.excluded_sells == ()


# ---------------------------------------------------------------- case 2
def test_single_reconcile_mark():
    lineage = derive_outcomes(
        [_buy(1), _sell(2, action="SELL_RECONCILE", realized_pnl=808.83)]
    )
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.pairing_method is PairingMethod.WINDOW_SINGLE_RECONCILE_MARK
    assert outcome.pairing_confidence is PairingConfidence.MEDIUM
    assert outcome.exit_basis is ExitBasis.RECONCILIATION_MARK
    assert outcome.outcome_direction is OutcomeDirection.WIN
    assert lineage.excluded_sells == ()


# ---------------------------------------------------------------- case 3
def test_reconcile_followed_by_valid_bot_exit_is_suppressed():
    rows = [
        _buy(1),
        _sell(2, action="SELL_RECONCILE", ts="2026-07-02T00:00:00+00:00"),
        _sell(3, action="SELL_STOP", ts="2026-07-09T00:00:00+00:00",
              realized_pnl=-50.0),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert (
        outcome.pairing_method
        is PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
    )
    assert outcome.pairing_confidence is PairingConfidence.MEDIUM
    assert outcome.exit_basis is ExitBasis.BOT_FILL
    assert outcome.exit_trade_id == 3
    assert outcome.suppressed_reconcile_sell_ids == (2,)
    (excluded,) = lineage.excluded_sells
    assert excluded.sell_trade_id == 2
    assert excluded.reason is ExcludedSellReason.PHANTOM_RECONCILE_SUPPRESSED


# ---------------------------------------------------------------- case 4
def test_phantom_suppression_is_structural_for_any_ids():
    rows = [
        _buy(1),
        _sell(777, action="SELL_RECONCILE", ts="2026-07-02T00:00:00+00:00"),
        _sell(778, action="SELL_TIME_EXIT", ts="2026-07-09T00:00:00+00:00"),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert (
        outcome.pairing_method
        is PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
    )
    assert outcome.suppressed_reconcile_sell_ids == (777,)


def test_reconcile_not_suppressed_without_a_valid_later_bot_fill():
    # later SELL_STOP has a NULL order_id -> not a valid bot fill -> no suppression
    rows = [
        _buy(1),
        _sell(2, action="SELL_RECONCILE", ts="2026-07-02T00:00:00+00:00"),
        _sell(3, action="SELL_STOP", ts="2026-07-09T00:00:00+00:00", order_id=None),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.pairing_method is PairingMethod.WINDOW_SINGLE_RECONCILE_MARK
    assert outcome.suppressed_reconcile_sell_ids == ()
    (excluded,) = lineage.excluded_sells
    assert excluded.sell_trade_id == 3
    assert excluded.reason is ExcludedSellReason.UNATTRIBUTED_IN_WINDOW


# ---------------------------------------------------------------- case 5
def test_bkng_style_reentry_isolated_by_window():
    rows = [
        _buy(1, symbol="BKNG", ts="2026-06-25T15:06:00+00:00", shares=66.70),
        _sell(2, symbol="BKNG", action="SELL_TIME_EXIT",
              ts="2026-07-02T18:13:00+00:00", shares=66.57, realized_pnl=100.51),
        _buy(3, symbol="BKNG", ts="2026-07-02T18:28:00+00:00", shares=44.15),
        _sell(4, symbol="BKNG", action="SELL_RECONCILE",
              ts="2026-07-07T14:33:00+00:00", shares=44.28),
        _sell(5, symbol="BKNG", action="SELL_TIME_EXIT",
              ts="2026-07-14T16:30:00+00:00", shares=44.15, realized_pnl=-298.45),
    ]
    lineage = derive_outcomes(rows)
    by_id = {o.entry_trade_id: o for o in lineage.decisions}
    assert by_id[1].status is OutcomeStatus.CLOSED
    assert by_id[1].pairing_method is PairingMethod.WINDOW_SINGLE_BOT_EXIT
    assert by_id[1].exit_trade_id == 2
    assert by_id[3].status is OutcomeStatus.CLOSED
    assert (
        by_id[3].pairing_method
        is PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
    )
    assert by_id[3].exit_trade_id == 5
    assert by_id[3].suppressed_reconcile_sell_ids == (4,)
    assert {(e.sell_trade_id, e.reason) for e in lineage.excluded_sells} == {
        (4, ExcludedSellReason.PHANTOM_RECONCILE_SUPPRESSED)
    }


# ---------------------------------------------------------------- case 6
def test_nke_style_reentry_with_partial_second_leg():
    rows = [
        _buy(1, symbol="NKE", ts="2026-07-06T15:10:00+00:00", shares=191.5),
        _sell(2, symbol="NKE", action="SELL_RECONCILE",
              ts="2026-07-07T14:33:00+00:00", shares=191.5),
        _sell(3, symbol="NKE", action="SELL_TIME_EXIT",
              ts="2026-07-15T18:06:00+00:00", shares=191.4, realized_pnl=73.69),
        _buy(4, symbol="NKE", ts="2026-07-17T18:21:00+00:00", shares=226.7),
        _sell(5, symbol="NKE", action="SELL_RECONCILE",
              ts="2026-09-01T16:45:00+00:00", shares=35.30, realized_pnl=-198.54,
              pnl_pct=-0.1285, holding_days=45),
    ]
    lineage = derive_outcomes(rows)
    by_id = {o.entry_trade_id: o for o in lineage.decisions}

    assert by_id[1].status is OutcomeStatus.CLOSED
    assert (
        by_id[1].pairing_method
        is PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
    )
    assert by_id[1].suppressed_reconcile_sell_ids == (2,)
    assert by_id[1].exit_trade_id == 3

    partial = by_id[4]
    assert partial.status is OutcomeStatus.PARTIAL
    assert partial.pairing_method is PairingMethod.WINDOW_PARTIAL_RECONCILE_MARK
    assert partial.pairing_confidence is PairingConfidence.LOW
    assert partial.exit_basis is ExitBasis.RECONCILIATION_MARK
    assert partial.outcome_direction is None
    assert partial.realized_pnl_usd == -198.54
    assert partial.holding_days == 45
    assert partial.remaining_qty_note is not None
    assert partial.exit_trade_id == 5

    assert {(e.sell_trade_id, e.reason) for e in lineage.excluded_sells} == {
        (2, ExcludedSellReason.PHANTOM_RECONCILE_SUPPRESSED)
    }


# ---------------------------------------------------------------- case 7
def test_orphan_sell_with_no_buy():
    rows = [
        _buy(1, symbol="AAA"),
        _sell(9, symbol="MS", action="SELL_STOP", ts="2026-06-26T19:50:00+00:00",
              realized_pnl=-473.86),
    ]
    lineage = derive_outcomes(rows)
    assert {o.entry_trade_id for o in lineage.decisions} == {1}
    assert all(o.symbol != "MS" for o in lineage.decisions)
    (excluded,) = lineage.excluded_sells
    assert (excluded.sell_trade_id, excluded.symbol, excluded.reason) == (
        9,
        "MS",
        ExcludedSellReason.ORPHAN_NO_BUY,
    )


# ---------------------------------------------------------------- case 8
def test_open_buy_with_no_sell():
    (outcome,) = derive_outcomes([_buy(1)]).decisions
    assert outcome.status is OutcomeStatus.OPEN
    assert outcome.pairing_method is PairingMethod.NONE_OPEN
    assert outcome.pairing_confidence is PairingConfidence.NONE
    assert outcome.exit_basis is None
    assert outcome.exit_trade_id is None
    assert outcome.outcome_direction is None


# ---------------------------------------------------------------- case 9
def test_amzn_style_clean_47_day_exit():
    rows = [
        _buy(1, symbol="AMZN", ts="2026-07-16T16:50:00+00:00", shares=23.68,
             price=256.09),
        _sell(2, symbol="AMZN", action="SELL_TIME_EXIT",
              ts="2026-09-02T14:33:00+00:00", shares=23.66, price=254.92,
              realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
    ]
    (outcome,) = derive_outcomes(rows).decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.pairing_method is PairingMethod.WINDOW_SINGLE_BOT_EXIT
    assert outcome.pairing_confidence is PairingConfidence.HIGH
    assert outcome.exit_basis is ExitBasis.BOT_FILL
    assert outcome.realized_pnl_usd == -27.77
    assert outcome.realized_pnl_pct == -0.00234
    assert outcome.holding_days == 47
    assert outcome.outcome_direction is OutcomeDirection.LOSS


# --------------------------------------------------------------- case 10
def test_quantity_epsilon_just_inside_is_closed():
    # buy 100 -> epsilon = max(0.01 * 100, 1e-6) = 1.0 ; diff 0.9 <= 1.0
    (outcome,) = derive_outcomes([_buy(1, shares=100.0), _sell(2, shares=99.1)]).decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.pairing_method is PairingMethod.WINDOW_SINGLE_BOT_EXIT


# --------------------------------------------------------------- case 11
def test_quantity_epsilon_just_outside_is_partial():
    # buy 100 -> epsilon 1.0 ; diff 1.1 > 1.0 ; matched 98.9 > 1.0
    (outcome,) = derive_outcomes([_buy(1, shares=100.0), _sell(2, shares=98.9)]).decisions
    assert outcome.status is OutcomeStatus.PARTIAL
    assert outcome.pairing_method is PairingMethod.WINDOW_PARTIAL_BOT_EXIT
    assert outcome.pairing_confidence is PairingConfidence.LOW
    assert outcome.outcome_direction is None
    assert outcome.remaining_qty_note is not None


# --------------------------------------------------------------- case 12
def test_near_zero_matched_quantity_is_open():
    lineage = derive_outcomes([_buy(1, shares=100.0), _sell(2, shares=0.0001)])
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.OPEN
    assert outcome.pairing_method is PairingMethod.NONE_OPEN
    (excluded,) = lineage.excluded_sells
    assert (excluded.sell_trade_id, excluded.reason) == (
        2,
        ExcludedSellReason.UNATTRIBUTED_IN_WINDOW,
    )


# --------------------------------------------------------------- case 13
def test_two_surviving_bot_exits_are_ambiguous():
    rows = [
        _buy(1, shares=100.0),
        _sell(2, action="SELL_TIME_EXIT", ts="2026-07-02T00:00:00+00:00", shares=50.0),
        _sell(3, action="SELL_STOP", ts="2026-07-05T00:00:00+00:00", shares=50.0),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.AMBIGUOUS
    assert outcome.pairing_method is PairingMethod.UNRESOLVED_MULTIPLE
    assert outcome.pairing_confidence is PairingConfidence.NONE
    assert outcome.candidate_sell_ids == (2, 3)
    assert outcome.exit_trade_id is None
    assert outcome.outcome_direction is None
    assert {(e.sell_trade_id, e.reason) for e in lineage.excluded_sells} == {
        (2, ExcludedSellReason.UNATTRIBUTED_IN_WINDOW),
        (3, ExcludedSellReason.UNATTRIBUTED_IN_WINDOW),
    }


# --------------------------------------------------------------- case 14
def test_unknown_sell_action_never_becomes_bot_fill():
    rows = [
        _buy(1, shares=100.0),
        _sell(2, action="SELL_MYSTERY", shares=100.0, order_id="x-2"),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.OPEN
    assert outcome.exit_basis is None
    assert outcome.pairing_method is PairingMethod.NONE_OPEN
    (excluded,) = lineage.excluded_sells
    assert (excluded.sell_trade_id, excluded.reason) == (
        2,
        ExcludedSellReason.UNATTRIBUTED_IN_WINDOW,
    )


# --------------------------------------------------------------- case 15
def test_bot_action_with_null_order_id_never_becomes_bot_fill():
    rows = [
        _buy(1, shares=100.0),
        _sell(2, action="SELL_STOP", shares=100.0, order_id=None),
    ]
    lineage = derive_outcomes(rows)
    (outcome,) = lineage.decisions
    assert outcome.status is OutcomeStatus.OPEN
    assert outcome.exit_basis is None
    (excluded,) = lineage.excluded_sells
    assert (excluded.sell_trade_id, excluded.reason) == (
        2,
        ExcludedSellReason.UNATTRIBUTED_IN_WINDOW,
    )


# --------------------------------------------------------------- extras
def test_reconcile_mark_exit_fields_are_copied_verbatim():
    rows = [
        _buy(1, shares=50.0),
        _sell(2, action="SELL_RECONCILE", shares=50.0, price=62.08,
              realized_pnl=28.91, pnl_pct=0.00478, holding_days=37),
    ]
    (outcome,) = derive_outcomes(rows).decisions
    assert outcome.exit_basis is ExitBasis.RECONCILIATION_MARK
    assert (
        outcome.exit_price,
        outcome.realized_pnl_usd,
        outcome.realized_pnl_pct,
        outcome.holding_days,
    ) == (62.08, 28.91, 0.00478, 37)


def test_derivation_is_order_independent():
    rows = [
        _buy(1, symbol="AAA"),
        _sell(2, symbol="AAA"),
        _buy(3, symbol="BBB"),
        _sell(4, symbol="BBB", action="SELL_RECONCILE"),
    ]
    shuffled = rows[:]
    random.Random(0).shuffle(shuffled)
    assert derive_outcomes(rows) == derive_outcomes(shuffled)


def test_decisions_are_sorted_by_entry_trade_id():
    ids = [o.entry_trade_id for o in derive_outcomes([_buy(9), _buy(2), _buy(5)]).decisions]
    assert ids == [2, 5, 9]


def test_flat_direction_when_realized_pnl_is_zero():
    (outcome,) = derive_outcomes(
        [_buy(1), _sell(2, realized_pnl=0.0)]
    ).decisions
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.outcome_direction is OutcomeDirection.FLAT


# ---------------------------------------------- opt-in production regression
_PROD_SNAPSHOT = os.environ.get("AARA_WAVE2A_PROD_SNAPSHOT")


@pytest.mark.skipif(
    not _PROD_SNAPSHOT,
    reason="set AARA_WAVE2A_PROD_SNAPSHOT to a real 42-row trades.db to run",
)
def test_production_snapshot_regression():
    from applications.trading_intelligence.adapters.trades_db_outcome_source import (
        TradesDbOutcomeReader,
    )

    result = TradesDbOutcomeReader(db_path=_PROD_SNAPSHOT).read_trade_rows()
    assert result.health.is_healthy
    lineage = derive_outcomes(result.value)

    status_counts = Counter(o.status for o in lineage.decisions)
    assert len(lineage.decisions) == 19
    assert status_counts[OutcomeStatus.CLOSED] == 15
    assert status_counts[OutcomeStatus.PARTIAL] == 1
    assert status_counts[OutcomeStatus.OPEN] == 3
    assert status_counts[OutcomeStatus.AMBIGUOUS] == 0

    suppressed = {
        sid for o in lineage.decisions for sid in o.suppressed_reconcile_sell_ids
    }
    assert suppressed == {20, 21, 22, 23, 24, 26}, (
        "structural phantom suppression diverged from the known 2026-07-07 batch"
    )

    excluded = {(e.sell_trade_id, e.reason) for e in lineage.excluded_sells}
    assert len(lineage.excluded_sells) == 7
    assert (7, ExcludedSellReason.ORPHAN_NO_BUY) in excluded
    assert sum(
        1 for _sid, reason in excluded
        if reason is ExcludedSellReason.PHANTOM_RECONCILE_SUPPRESSED
    ) == 6

    closed = [o for o in lineage.decisions if o.status is OutcomeStatus.CLOSED]
    wins = sum(1 for o in closed if o.outcome_direction is OutcomeDirection.WIN)
    losses = sum(1 for o in closed if o.outcome_direction is OutcomeDirection.LOSS)
    assert (wins, losses) == (7, 8)

    by_id = {o.entry_trade_id: o for o in lineage.decisions}
    assert by_id[4].pairing_method is PairingMethod.WINDOW_SINGLE_RECONCILE_MARK
    assert by_id[5].pairing_method is PairingMethod.WINDOW_SINGLE_BOT_EXIT
    assert (
        by_id[10].pairing_method
        is PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
    )
    assert by_id[28].status is OutcomeStatus.OPEN
    assert by_id[35].status is OutcomeStatus.OPEN
    assert by_id[40].status is OutcomeStatus.PARTIAL
    assert by_id[45].status is OutcomeStatus.OPEN
