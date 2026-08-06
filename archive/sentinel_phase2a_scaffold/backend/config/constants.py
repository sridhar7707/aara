"""Sentinel constants. Values TBD when Phase 2A implementation begins."""

API_VERSION = "v1"

# Risk Governor thresholds (GRADIO_IMPLEMENTATION_GUIDE.md).
# 3-state machine: DEFENSIVE's upper bound is a hard stop, not a
# transition into a 4th state.
RISK_GOVERNOR_WARNING_DRAWDOWN_PCT = -10.0
RISK_GOVERNOR_DEFENSIVE_DRAWDOWN_PCT = -15.0
RISK_GOVERNOR_BREACH_DRAWDOWN_PCT = -20.0
