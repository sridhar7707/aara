"""The Wave 2A outcome layer keys decisions with the same
``"trade-<id>"`` identity the Wave 1 Decision Center path uses.
"""
from applications.platform.integrations import ReadResult
from applications.trading_intelligence.adapters.trade_outcome_derivation import (
    derive_outcomes,
)
from applications.trading_intelligence.projections import trade_outcome_row as tor
from applications.trading_intelligence.projections.trade_decision_row import (
    decision_id_for,
    trade_id_from_decision_id,
)
from applications.trading_intelligence.projections.trade_outcome_row import TradeOutcomeRow
from applications.trading_intelligence.services.decision_outcome_query_service import (
    DecisionOutcomeQueryService,
)


def _buy(trade_id, symbol="AAA"):
    return TradeOutcomeRow(
        id=trade_id,
        timestamp="2026-01-01T00:00:{:02d}+00:00".format(trade_id % 60),
        symbol=symbol,
        action="BUY",
        shares=10.0,
        price=5.0,
        notional=50.0,
        realized_pnl=0.0,
        pnl_pct=0.0,
        holding_days=0,
        order_id="o-{}".format(trade_id),
        ensemble_score=0.6,
        regime="RANGING",
    )


def test_outcome_row_reuses_the_wave1_id_helpers():
    assert tor.decision_id_for is decision_id_for
    assert tor.trade_id_from_decision_id is trade_id_from_decision_id


def test_decision_id_round_trip():
    for trade_id in (1, 7, 45, 999):
        assert trade_id_from_decision_id(decision_id_for(trade_id)) == trade_id


def test_outcome_decision_id_matches_entry_trade_id():
    lineage = derive_outcomes([_buy(4), _buy(38)])
    assert [o.entry_trade_id for o in lineage.decisions] == [4, 38]
    for outcome in lineage.decisions:
        assert outcome.decision_id == decision_id_for(outcome.entry_trade_id)
        assert outcome.decision_id == "trade-{}".format(outcome.entry_trade_id)


class _StubSource:
    def __init__(self, rows):
        self._rows = list(rows)

    def read_trade_rows(self):
        return ReadResult.healthy(list(self._rows), "stub")


def test_get_outcome_by_id_and_unknown_and_ill_formed():
    service = DecisionOutcomeQueryService(_StubSource([_buy(4), _buy(38)]))
    assert service.get_outcome("trade-4").entry_trade_id == 4
    assert service.get_outcome("trade-38").entry_trade_id == 38
    assert service.get_outcome("trade-999") is None  # well-formed id, absent
    assert service.get_outcome("garbage") is None  # ill-formed id
    assert service.get_outcome("") is None
