"""Tests for adapters.trades_db_decision_outcome_source.TradesDbDecisionOutcomeSource --
the Decision -> Outcome linkage collaborator backing Decision Center's
"Decision Outcome" section.

Also proves the shared decision_id lineage the read-only reassessment
identified: the SAME "trade-<id>" decision_id Decision Center's own
TradesDbDecisionReader produces (via projections/trade_decision_row.py's
decision_id_for()) is exactly the id this adapter's get_outcome() accepts
and resolves against real, seeded trades.db rows -- proven end-to-end here
with a real sqlite fixture, not asserted only by code inspection.
"""
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.trades_db_decision_outcome_source import (
    TradesDbDecisionOutcomeSource,
)
from applications.trading_intelligence.adapters.trades_db_outcome_source import (
    TradesDbOutcomeReader,
)
from applications.trading_intelligence.contracts.decision_outcome_contract import (
    OutcomeDirection,
    OutcomeStatus,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.trade_decision_row import decision_id_for
from applications.trading_intelligence.services.decision_outcome_query_service import (
    DecisionOutcomeQueryService,
)

_DDL = """
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, symbol TEXT, action TEXT,
    shares REAL, price REAL, notional REAL,
    regime TEXT, portfolio_value REAL, pnl_pct REAL,
    xgb_prob REAL, lstm_prob REAL, sentiment_score REAL, macro_score REAL,
    ensemble_score REAL, realized_pnl REAL, order_id TEXT, holding_days INTEGER,
    feature_drivers TEXT, ai_reasoning TEXT,
    stop_loss REAL, take_profit REAL, risk_reward_ratio REAL
)
"""

_COLS = (
    "id", "timestamp", "symbol", "action", "shares", "price", "notional",
    "realized_pnl", "pnl_pct", "holding_days", "order_id",
)


def _row(**over):
    base = dict(
        id=None, timestamp="2026-07-01T00:00:00+00:00", symbol="AAA", action="BUY",
        shares=100.0, price=10.0, notional=1000.0, realized_pnl=0.0, pnl_pct=0.0,
        holding_days=0, order_id=None,
    )
    base.update(over)
    return tuple(base[c] for c in _COLS)


def _make_db(rows):
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute(_DDL)
    ph = ", ".join("?" for _ in _COLS)
    conn.executemany(f"INSERT INTO trades ({', '.join(_COLS)}) VALUES ({ph})", rows)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db_path():
    paths = []

    def _make(rows):
        path = _make_db(rows)
        paths.append(path)
        return path

    yield _make
    for path in paths:
        os.remove(path)


def _outcome_source_for(path):
    reader = TradesDbOutcomeReader(db_path=path)
    return TradesDbDecisionOutcomeSource(DecisionOutcomeQueryService(reader))


def test_get_outcome_returns_the_real_closed_outcome_for_a_matching_buy(db_path):
    """Proves the shared decision_id lineage end-to-end: decision_id_for(1)
    -- the exact id Decision Center's own TradesDbDecisionReader would
    produce for this same BUY row -- resolves to the real, derived
    DecisionOutcome for that same trade."""
    path = db_path([
        _row(id=1, symbol="AMZN", action="BUY", shares=23.68,
             timestamp="2026-07-16T16:50:00+00:00", price=256.09),
        _row(id=2, symbol="AMZN", action="SELL_TIME_EXIT", shares=23.66,
             timestamp="2026-09-02T14:33:00+00:00", price=254.92, order_id="o-2",
             realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
    ])
    source = _outcome_source_for(path)

    outcome = source.get_outcome(decision_id_for(1))

    assert outcome is not None
    assert outcome.decision_id == "trade-1"
    assert outcome.status is OutcomeStatus.CLOSED
    assert outcome.outcome_direction is OutcomeDirection.LOSS
    assert outcome.realized_pnl_usd == -27.77
    assert outcome.realized_pnl_pct == -0.00234
    assert outcome.holding_days == 47


def test_get_outcome_returns_a_real_open_outcome_for_an_unresolved_buy(db_path):
    """A BUY with no matching SELL still produces a real DecisionOutcome --
    status OPEN, no exit fields -- never None. None is reserved for a
    decision_id with no matching row at all (see the next test)."""
    path = db_path([
        _row(id=1, symbol="SLB", action="BUY", shares=139.75,
             timestamp="2026-09-02T14:39:08+00:00", order_id="o-1"),
    ])
    source = _outcome_source_for(path)

    outcome = source.get_outcome(decision_id_for(1))

    assert outcome is not None
    assert outcome.status is OutcomeStatus.OPEN
    assert outcome.outcome_direction is None
    assert outcome.realized_pnl_pct is None
    assert outcome.holding_days is None


def test_get_outcome_returns_none_for_an_unknown_decision_id(db_path):
    path = db_path([
        _row(id=1, symbol="AAA", action="BUY", shares=10.0,
             timestamp="2026-07-01T00:00:00+00:00"),
    ])
    source = _outcome_source_for(path)

    outcome = source.get_outcome(decision_id_for(999))

    assert outcome is None


def test_get_outcome_raises_on_non_healthy_read():
    missing_db_source = _outcome_source_for("does-not-exist-decision-outcome-source.db")

    with pytest.raises(TradingIntelligenceReadError):
        missing_db_source.get_outcome(decision_id_for(1))


def test_get_outcome_matches_decision_outcome_query_service_verbatim(db_path):
    """Regression guard: the adapter must not alter, round, or recompute
    any value on the way through -- the object it returns is exactly what
    DecisionOutcomeQueryService.get_outcome() (frozen, Wave 2A) itself
    returns for the identical read, field for field."""
    path = db_path([
        _row(id=1, symbol="AMZN", action="BUY", shares=23.68,
             timestamp="2026-07-16T16:50:00+00:00", price=256.09),
        _row(id=2, symbol="AMZN", action="SELL_TIME_EXIT", shares=23.66,
             timestamp="2026-09-02T14:33:00+00:00", price=254.92, order_id="o-2",
             realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
    ])
    source = _outcome_source_for(path)
    direct_service = DecisionOutcomeQueryService(TradesDbOutcomeReader(db_path=path))

    via_adapter = source.get_outcome(decision_id_for(1))
    via_service_directly = direct_service.get_outcome(decision_id_for(1))

    assert via_adapter == via_service_directly
