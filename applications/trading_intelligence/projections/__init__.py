"""Trading Intelligence projections.

Trading-Intelligence-specific read models — the UI-facing shape of data,
distinct from sentinel_engine.projections.DecisionProjection (see
TRADING_INTELLIGENCE_APPLICATION_ARCHITECTURE.md's read-flow: Sentinel
Projection -> Reader Contract -> Trading Intelligence Projection -> UI).

Implemented: DecisionView (decision_view.py) — no persistence, no database.

See ../README.md for scope and dependency rules.
"""
