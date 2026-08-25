"""Settings -- screen shell only.

Self-contained: no import from ui/decision_center/, ui/portfolio_intelligence/,
ui/risk_intelligence/, or ui/morning_brief/; no sentinel_engine/bot/dashboard
import; no persistence/configuration contract of any kind. Per
docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 2,
Settings' three required areas -- User Settings, Thresholds, Notification
Preferences -- have "none proposed" for Sentinel Engine inputs (this is
explicitly a product-layer concern, not a Sentinel governance concern) and
no wired product-layer persistence contract exists in
applications/trading_intelligence/ either. This package renders each area
as an honest, fixed unavailable state rather than inventing content or a
new configuration contract for any of them.
"""
