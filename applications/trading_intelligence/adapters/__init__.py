"""Trading Intelligence adapters.

Two directions of translation live here:

- Read direction (Sentinel -> Trading Intelligence): implemented.
  SentinelProjectionDecisionSource (sentinel_projection_decision_source.py)
  wraps a sentinel_engine ProjectionRepository and implements the
  DecisionSource abstraction, read-only.
- Write direction (bot/-shaped data -> sentinel_engine contracts): not
  implemented. Future home for candidate, risk, execution, and outcome
  adapters, per docs/platform/TRADING_INTELLIGENCE_EVENT_MODEL.md Section 6.

sentinel_engine/adapters/decision_adapter.py already exists on the Sentinel
Engine side (translates a plain dict into a Decision) and is not duplicated
here.

See ../README.md for scope and dependency rules.
"""
