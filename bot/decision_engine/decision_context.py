from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class DecisionContext:
    symbol: str
    timestamp: datetime
    strategy_signals: Mapping[str, Any]
    portfolio_context: Mapping[str, Any]
    market_regime: str
    risk_state: str
