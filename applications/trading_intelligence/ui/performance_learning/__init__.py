"""Performance & Learning -- screen shell only.

Self-contained: no import from ui/decision_center/, ui/portfolio_intelligence/,
ui/risk_intelligence/, ui/morning_brief/, or ui/settings/; no
sentinel_engine/bot/dashboard import; no outcome/attribution/calibration
contract of any kind. Per docs/products/AARA_TRADING_INTELLIGENCE_UI_
SPECIFICATION.md Section 2, this screen's three required areas -- Outcome
History, Attribution Breakdown, Model Confidence Calibration -- have a
named but unwired future Sentinel Engine input (`DECISION_OUTCOME_RECORDED`,
BUY-scoped only) and no adapter exists for it in this application. This
package renders each area as an honest, fixed unavailable state rather
than inventing performance figures, outcomes, or a persistence model for
any of them, and never implies that every decision produces an outcome.
"""
