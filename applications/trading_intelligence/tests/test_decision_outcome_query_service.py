"""Tests for services.decision_outcome_query_service.DecisionOutcomeQueryService.

The service composes an injected TradeRowSource with the pure
derivation. These tests inject in-memory stub sources -- never a real
database.
"""
from applications.platform.integrations import (
    IntegrationHealth,
    IntegrationStatus,
    ReadResult,
)
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    OutcomeLineage,
    OutcomeStatus,
)
from applications.trading_intelligence.projections.trade_outcome_row import TradeOutcomeRow
from applications.trading_intelligence.services.decision_outcome_query_service import (
    DecisionOutcomeQueryService,
    TradeRowSource,
)


def _buy(trade_id, symbol="AAA"):
    return TradeOutcomeRow(
        id=trade_id,
        timestamp="2026-06-01T00:00:{:02d}+00:00".format(trade_id % 60),
        symbol=symbol,
        action="BUY",
        shares=10.0,
        price=5.0,
        notional=50.0,
        realized_pnl=0.0,
        pnl_pct=0.0,
        holding_days=0,
        order_id="b-{}".format(trade_id),
        ensemble_score=0.6,
        regime="RANGING",
    )


def _sell(trade_id, symbol="AAA", action="SELL_TIME_EXIT"):
    return TradeOutcomeRow(
        id=trade_id,
        timestamp="2026-07-01T00:00:{:02d}+00:00".format(trade_id % 60),
        symbol=symbol,
        action=action,
        shares=10.0,
        price=6.0,
        notional=60.0,
        realized_pnl=10.0,
        pnl_pct=0.2,
        holding_days=5,
        order_id="s-{}".format(trade_id) if action in ("SELL_STOP", "SELL_TIME_EXIT") else None,
        ensemble_score=None,
        regime=None,
    )


class _Source(TradeRowSource):
    def __init__(self, result):
        self._result = result

    def read_trade_rows(self):
        return self._result


def _healthy(rows):
    return ReadResult.healthy(list(rows), "stub")


def _failed():
    return ReadResult.failed(IntegrationHealth.unavailable("stub"))


def test_get_lineage_healthy_wraps_the_derivation():
    service = DecisionOutcomeQueryService(_Source(_healthy([_buy(1), _sell(2)])))
    result = service.get_lineage()
    assert result.health.status is IntegrationStatus.HEALTHY
    assert isinstance(result.value, OutcomeLineage)
    (outcome,) = result.value.decisions
    assert outcome.status is OutcomeStatus.CLOSED


def test_get_lineage_healthy_empty_when_source_has_no_rows():
    service = DecisionOutcomeQueryService(_Source(_healthy([])))
    result = service.get_lineage()
    assert result.health.status is IntegrationStatus.HEALTHY
    assert result.value == OutcomeLineage(decisions=(), excluded_sells=())


def test_get_lineage_propagates_the_sources_unhealthy_health():
    service = DecisionOutcomeQueryService(_Source(_failed()))
    result = service.get_lineage()
    assert result.value is None
    assert result.health.status is IntegrationStatus.UNAVAILABLE


def test_convenience_methods_degrade_to_empty_on_unhealthy_read():
    service = DecisionOutcomeQueryService(_Source(_failed()))
    assert service.list_outcomes() == []
    assert service.list_excluded_sells() == []
    assert service.get_outcome("trade-1") is None


def test_list_outcomes_and_excluded_sells_on_a_healthy_read():
    rows = [
        _buy(1),
        _sell(2, action="SELL_RECONCILE"),
        _buy(3, symbol="ZZZ"),  # no ZZZ sell -> OPEN
        _sell(9, symbol="QQQ", action="SELL_STOP"),  # orphan
    ]
    service = DecisionOutcomeQueryService(_Source(_healthy(rows)))
    assert [o.entry_trade_id for o in service.list_outcomes()] == [1, 3]
    assert [e.sell_trade_id for e in service.list_excluded_sells()] == [9]


def test_get_outcome_ill_formed_id_does_not_touch_the_source():
    class _Boom(TradeRowSource):
        def read_trade_rows(self):
            raise AssertionError("must not be called for an ill-formed id")

    assert DecisionOutcomeQueryService(_Boom()).get_outcome("garbage") is None


def test_get_outcome_returns_the_matching_decision():
    service = DecisionOutcomeQueryService(_Source(_healthy([_buy(1), _buy(2)])))
    assert service.get_outcome("trade-2").entry_trade_id == 2
    assert service.get_outcome("trade-777") is None
