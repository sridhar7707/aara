"""Risk Intelligence -- illustrative-data MVP screen.

Self-contained: no import from ui/decision_center/ or
ui/portfolio_intelligence/, no sentinel_engine/bot/dashboard import. Per
docs/products/AARA_TRADING_INTELLIGENCE_RISK_INTELLIGENCE_DESIGN.md, no
`RiskEvaluation` (or equivalently-named) contract exists in
sentinel_engine, and none is proposed or added by this package -- it is
illustrative-only, standing in for the standalone "Risk Intelligence"
screen named in AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2
(current risk-governor state, trigger reason, recommended vs. actual
sizing), not the decision-scoped capability already covered by Decision
Center's own static "Risk context not yet available" disclosure. Not
wired into main.py/bootstrap.py yet; this is the standalone screen only.
"""
