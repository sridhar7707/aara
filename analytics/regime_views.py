"""Phase 2 scaffolding (phase2_requirements.md Section 3.2): regime-aware
performance views over the Trust Ledger. Read-only -- extends the Phase 0
AnalyticsRepository rather than replacing it, and adds no new instrumentation:
market_context.regime is already logged on every decision_events row
(bot/_main_trust_decisions.py).

Not wired into any dashboard, cron job, or bot pipeline -- Phase 2
implementation is gated on Phase 1B acceptance (phase2_requirements.md
"Gate"). This module exists so the query shape is ready once there is real
decision history to query; today it will legitimately return an empty list.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass

_log = logging.getLogger("tradegenie.analytics.regime_views")


@dataclass
class RegimePerformance:
    regime: str
    decisions: int
    win_rate: float
    avg_net_return: float


def regime_performance(conn: sqlite3.Connection) -> list[RegimePerformance]:
    """Aggregate EXECUTED decisions with a known outcome by market_context.regime.

    Max drawdown (shown in phase2_requirements.md's illustrative table) is
    deliberately not computed here -- it requires a portfolio-level equity
    curve (AnalyticsRepository.load_snapshots), not just per-decision
    returns, and adding a same-named-but-wrong metric would be worse than
    omitting it.
    """
    rows = conn.execute(
        "SELECT d.market_context, o.net_return "
        "FROM decision_events d "
        "JOIN decision_outcome_events o ON o.decision_id = d.decision_id "
        "WHERE d.event_type = 'EXECUTED'"
    ).fetchall()

    by_regime: dict[str, list[float]] = {}
    for market_context_json, net_return in rows:
        regime = json.loads(market_context_json).get("regime", "UNKNOWN")
        by_regime.setdefault(regime, []).append(net_return)

    return [
        RegimePerformance(
            regime=regime,
            decisions=len(returns),
            win_rate=sum(1 for r in returns if r > 0) / len(returns),
            avg_net_return=sum(returns) / len(returns),
        )
        for regime, returns in by_regime.items()
    ]
