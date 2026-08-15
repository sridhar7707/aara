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

DECISION_CENTER_WORKSPACE: the same reusable-descriptor treatment as
TRADING_INTELLIGENCE_PRODUCT above, for the one workspace this product
currently has. Previously duplicated inline in
applications/platform/tests/test_trading_intelligence_product_integration.py
as a test-local value -- promoted here so that test imports it instead of
maintaining its own copy, which is not itself registered with any
WorkspaceRegistry implementation anywhere in this codebase.
"""
from applications.platform.registry.product_registry import Product
from applications.platform.workspaces.workspace import Workspace

TRADING_INTELLIGENCE_PRODUCT = Product(
    product_id="trading_intelligence",
    name="Trading Intelligence",
    entitlement_required="TRADING_INTELLIGENCE",
    description=(
        "Medium-term investing intelligence: portfolio decisions, trade "
        "evaluation, risk management, paper trading validation."
    ),
)

DECISION_CENTER_WORKSPACE = Workspace(
    workspace_id="trading_intelligence.decision_center",
    product_id="trading_intelligence",
    display_name="Decision Center",
    visibility="TRADING_INTELLIGENCE",
    order=0,
)
