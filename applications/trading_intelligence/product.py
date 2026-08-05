"""Trading Intelligence's product descriptor -- metadata only.

No services/adapters/sentinel_engine import: this file exists purely to be
discoverable by applications.platform.registry.ProductRegistry, per
docs/platform/AARA_PRODUCT_REGISTRATION_ARCHITECTURE.md Section 5. It is not
registered with any registry implementation anywhere in this codebase --
no concrete ProductRegistry exists, and nothing calls .register() with this
value.

`status` is deliberately left unset (defaults to None) -- no status
vocabulary has been decided (see the registration architecture document's
Section 7), and this product has no real backend/auth wiring, so asserting a
value like "ACTIVE" would overstate its readiness.
"""
from applications.platform.registry.product_registry import Product

TRADING_INTELLIGENCE_PRODUCT = Product(
    product_id="trading_intelligence",
    name="Trading Intelligence",
    entitlement_required="TRADING_INTELLIGENCE",
    description=(
        "Medium-term investing intelligence: portfolio decisions, trade "
        "evaluation, risk management, paper trading validation."
    ),
)
