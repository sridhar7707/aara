from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from bot.decision_engine.decision_context import DecisionContext


def _make_context(**overrides):
    defaults = dict(
        symbol="AAPL",
        timestamp=datetime(2026, 8, 5, tzinfo=timezone.utc),
        strategy_signals={"xgb_prob": 0.62},
        portfolio_context={"cash": 10000.0},
        market_regime="RISK_ON",
        risk_state="GREEN",
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)


def test_context_holds_all_fields():
    ctx = _make_context()
    assert ctx.symbol == "AAPL"
    assert ctx.timestamp == datetime(2026, 8, 5, tzinfo=timezone.utc)
    assert ctx.strategy_signals == {"xgb_prob": 0.62}
    assert ctx.portfolio_context == {"cash": 10000.0}
    assert ctx.market_regime == "RISK_ON"
    assert ctx.risk_state == "GREEN"


def test_context_is_frozen_and_rejects_mutation():
    ctx = _make_context()
    with pytest.raises(FrozenInstanceError):
        ctx.symbol = "MSFT"
