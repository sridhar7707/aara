"""Performance & Learning screen.

Self-contained: no import from ui/decision_center/, ui/portfolio_intelligence/,
ui/risk_intelligence/, ui/morning_brief/, or ui/settings/; no
sentinel_engine/bot/dashboard import; no service call from within this
package.

Two of the three frozen IA areas -- Attribution Breakdown, Model
Confidence Calibration -- still have no wired data source and render a
fixed, honest unavailable state (Wave 2A produces no attribution or
calibration data and none is fabricated here).

Wave 2B wires the first real source into the third area, Outcome History:
the composition root (bootstrap.py) maps the verified Wave 2A trades-only
decision-outcome lineage (`DecisionOutcomeQueryService`) into this
package's own `OutcomeHistoryRow` presentation shape. It renders a
factual, read-only table of one row per BUY decision -- OPEN / PARTIAL /
CLOSED / AMBIGUOUS -- with an honest unavailable state when the read is
not HEALTHY and an honest empty state when it is HEALTHY with no BUY
decisions. Nothing here recomputes P&L, holding period, exit price, or
outcome direction (Wave 2A owns those), and it never implies every
decision produces an outcome.
"""
