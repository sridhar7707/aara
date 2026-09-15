"""Tests for adapters.trades_db_decision_calibration_source.
TradesDbDecisionCalibrationSource -- the Decision Quality Cross-Linking
collaborator backing Decision Center's calibration-band context.

Mirrors test_trades_db_decision_outcome_source.py's own real-sqlite-fixture
approach: a genuinely non-HEALTHY read becomes a TradingIntelligenceReadError;
a HEALTHY read is folded through the frozen DecisionCalibrationQueryService
verbatim, over the SAME DecisionOutcomeQueryService/TradesDbOutcomeReader
lineage-reading path Decision -> Outcome linkage and Performance & Learning
both already exercise.
"""
import os
import sqlite3
import tempfile

import pytest

from applications.trading_intelligence.adapters.trades_db_decision_calibration_source import (
    TradesDbDecisionCalibrationSource,
)
from applications.trading_intelligence.adapters.trades_db_outcome_source import (
    TradesDbOutcomeReader,
)
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.calibration_band_context import (
    CalibrationBandContext,
)
from applications.trading_intelligence.services.decision_calibration_query_service import (
    DecisionCalibrationQueryService,
)
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
    "realized_pnl", "pnl_pct", "holding_days", "order_id", "ensemble_score",
)


def _row(**over):
    base = dict(
        id=None, timestamp="2026-07-01T00:00:00+00:00", symbol="AAA", action="BUY",
        shares=100.0, price=10.0, notional=1000.0, realized_pnl=0.0, pnl_pct=0.0,
        holding_days=0, order_id=None, ensemble_score=None,
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


def _calibration_source_for(path):
    reader = TradesDbOutcomeReader(db_path=path)
    return TradesDbDecisionCalibrationSource(
        DecisionOutcomeQueryService(reader), DecisionCalibrationQueryService(),
    )


def test_get_band_context_returns_the_real_band_and_total_for_a_matching_score(db_path):
    """Proves the shared decision-outcome lineage feeds calibration
    end-to-end: two CLOSED BUY decisions whose entry_ensemble_score both
    land in the same band produce a real CalibrationBandContext, not a
    fabricated one."""
    path = db_path([
        _row(id=1, symbol="AMZN", action="BUY", shares=23.68,
             timestamp="2026-07-16T16:50:00+00:00", price=256.09, ensemble_score=0.61),
        _row(id=2, symbol="AMZN", action="SELL_TIME_EXIT", shares=23.66,
             timestamp="2026-09-02T14:33:00+00:00", price=254.92, order_id="o-2",
             realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
        _row(id=3, symbol="NKE", action="BUY", shares=10.0,
             timestamp="2026-07-01T00:00:00+00:00", price=50.0, ensemble_score=0.62),
        _row(id=4, symbol="NKE", action="SELL_TIME_EXIT", shares=10.0,
             timestamp="2026-08-01T00:00:00+00:00", price=60.0, order_id="o-4",
             realized_pnl=100.0, pnl_pct=0.2, holding_days=31),
    ])
    source = _calibration_source_for(path)

    context = source.get_band_context(0.615)

    assert isinstance(context, CalibrationBandContext)
    assert context.band.label == "0.60-0.65"
    assert (context.band.n, context.band.wins, context.band.losses) == (2, 1, 1)
    assert context.total_outcomes == 2


def test_get_band_context_returns_none_for_a_score_outside_every_band(db_path):
    path = db_path([
        _row(id=1, symbol="AAA", action="BUY", shares=10.0,
             timestamp="2026-07-01T00:00:00+00:00", ensemble_score=0.61),
    ])
    source = _calibration_source_for(path)

    assert source.get_band_context(0.30) is None
    assert source.get_band_context(1.5) is None


def test_get_band_context_returns_none_for_a_missing_score(db_path):
    path = db_path([
        _row(id=1, symbol="AAA", action="BUY", shares=10.0,
             timestamp="2026-07-01T00:00:00+00:00", ensemble_score=0.61),
    ])
    source = _calibration_source_for(path)

    assert source.get_band_context(None) is None


def test_get_band_context_still_resolves_a_band_when_no_outcome_qualifies_yet(db_path):
    """An OPEN BUY (no matching sell) has a real entry_ensemble_score but
    contributes no WIN/LOSS tally -- the band identity must still resolve,
    with an honest all-zero tally, never an error and never a fabricated
    n."""
    path = db_path([
        _row(id=1, symbol="SLB", action="BUY", shares=139.75,
             timestamp="2026-09-02T14:39:08+00:00", order_id="o-1", ensemble_score=0.61),
    ])
    source = _calibration_source_for(path)

    context = source.get_band_context(0.61)

    assert context.band.label == "0.60-0.65"
    assert (context.band.n, context.band.wins, context.band.losses) == (0, 0, 0)
    assert context.total_outcomes == 0


def test_get_band_context_raises_on_non_healthy_read():
    missing_db_source = _calibration_source_for("does-not-exist-decision-calibration-source.db")

    with pytest.raises(TradingIntelligenceReadError):
        missing_db_source.get_band_context(0.61)


def test_get_band_context_matches_the_query_service_verbatim(db_path):
    """Regression guard: the adapter must not alter, round, or recompute
    any value on the way through -- the band it returns is exactly what
    DecisionCalibrationQueryService.get_band_for_score() (frozen) itself
    returns for the identical lineage."""
    path = db_path([
        _row(id=1, symbol="AMZN", action="BUY", shares=23.68,
             timestamp="2026-07-16T16:50:00+00:00", price=256.09, ensemble_score=0.61),
        _row(id=2, symbol="AMZN", action="SELL_TIME_EXIT", shares=23.66,
             timestamp="2026-09-02T14:33:00+00:00", price=254.92, order_id="o-2",
             realized_pnl=-27.77, pnl_pct=-0.00234, holding_days=47),
    ])
    source = _calibration_source_for(path)
    direct_service = DecisionCalibrationQueryService()
    direct_lineage = DecisionOutcomeQueryService(TradesDbOutcomeReader(db_path=path)).get_lineage().value

    via_adapter = source.get_band_context(0.61)
    via_service_directly = direct_service.get_band_for_score(direct_lineage, 0.61)

    assert via_adapter.band == via_service_directly
