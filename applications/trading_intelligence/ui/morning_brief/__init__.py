"""Morning Brief -- screen shell only.

Self-contained: no import from ui/decision_center/, ui/portfolio_intelligence/,
or ui/risk_intelligence/; no sentinel_engine/bot/dashboard import; no
MorningBriefQuery wiring. Per docs/products/AARA_TRADING_INTELLIGENCE_UI_
SPECIFICATION.md Section 2, this screen's four required sections --
Portfolio Snapshot, Market Mood/Regime, Candidate Screening Summary,
Overnight Holdings News -- have no Sentinel-side contract wired or
proposed. Unlike ui/portfolio_intelligence/ and ui/risk_intelligence/,
which render hand-picked illustrative numbers for their own, differently-
scoped gaps, this package renders each section as an honest, fixed
unavailable state instead of inventing content for any of them.
"""
