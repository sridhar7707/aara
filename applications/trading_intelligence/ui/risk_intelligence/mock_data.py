"""Illustrative-only data for Risk Intelligence -- MVP.

No sentinel_engine/bot/dashboard import: no `RiskEvaluation` contract or
production risk_evaluation_events reader exists or is proposed here (see
docs/products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md
Section 4/5 -- building on top of Phase 1A Observation Mode data is
explicitly flagged as premature). This module is the sole data source for
this screen; every value below is a hand-picked, deterministic
illustrative number, not derived from any real account or ledger.
"""
from applications.trading_intelligence.ui.risk_intelligence.screen import (
    RiskHistoryEntry,
    RiskScreen,
    RiskSnapshot,
)

_MOCK_CURRENT = RiskSnapshot(
    state="NORMAL",
    trigger_reason="Portfolio drawdown -3.1% -- within normal range (threshold -10%).",
    recommended_sizing_pct=100.0,
    actual_sizing_pct=100.0,
    as_of="2026-08-18 14:00 UTC",
)

_MOCK_HISTORY = (
    RiskHistoryEntry(
        timestamp="2026-08-18 14:00 UTC", state="NORMAL",
        trigger_reason="Portfolio drawdown -3.1% -- within normal range.",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    ),
    RiskHistoryEntry(
        timestamp="2026-08-17 09:15 UTC", state="WARNING",
        trigger_reason="Portfolio drawdown -11.4% -- approaching daily loss limit.",
        recommended_sizing_pct=75.0, actual_sizing_pct=70.0,
    ),
    RiskHistoryEntry(
        timestamp="2026-08-16 16:45 UTC", state="DEFENSIVE",
        trigger_reason="Portfolio drawdown -16.8% -- CRO approval required for new positions.",
        recommended_sizing_pct=50.0, actual_sizing_pct=45.0,
    ),
    RiskHistoryEntry(
        timestamp="2026-08-16 08:00 UTC", state="WARNING",
        trigger_reason="Daily loss -3.8% -- 50-100% of daily limit.",
        recommended_sizing_pct=75.0, actual_sizing_pct=75.0,
    ),
    RiskHistoryEntry(
        timestamp="2026-08-15 10:30 UTC", state="NORMAL",
        trigger_reason="Portfolio drawdown -2.0% -- within normal range.",
        recommended_sizing_pct=100.0, actual_sizing_pct=100.0,
    ),
)


def build_mock_screen() -> RiskScreen:
    return RiskScreen(current=_MOCK_CURRENT, history=_MOCK_HISTORY)
