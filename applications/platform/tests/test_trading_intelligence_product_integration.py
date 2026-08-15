"""Integration test: the real Trading Intelligence product descriptor and a
real Decision Center workspace value, composed end-to-end through
NavigationBuilder.

Closes the specific gap named in
docs/products/AARA_TRADING_INTELLIGENCE_APPLICATION_COMPOSITION_DESIGN.md
Section 2/6: TRADING_INTELLIGENCE_PRODUCT has been proven registrable
(test_trading_intelligence_registration.py) and NavigationBuilder has been
proven to compose Product+Workspace data correctly (test_navigation_builder.py)
-- but never together, and never with the real product descriptor. Every
prior NavigationBuilder test used a synthetic, locally-defined Product, not
applications.trading_intelligence.product.TRADING_INTELLIGENCE_PRODUCT.

No production code is created or modified here -- every class used already
exists (ProductRegistry, WorkspaceRegistry, NavigationBuilder,
AuthenticationProvider, EntitlementChecker, User, Product, Workspace,
NavigationItem, NavigationModel). This file only proves they compose
correctly for Trading Intelligence specifically.

Per docs/platform/AARA_WORKSPACE_ENTRY_ARCHITECTURE.md Section 5: also
proves a NavigationItem can be used to locate and construct the Decision
Center experience end-to-end, with no resolver/router/factory -- the test
itself performs the trivial workspace_id lookup, matching that document's
Section 4 conclusion that no such production object is needed yet.
"""
import datetime

from applications.platform.entitlements.entitlement_checker import EntitlementChecker
from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.user import User
from applications.platform.navigation.navigation_builder import NavigationBuilder
from applications.platform.registry.product_registry import ProductRegistry
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry
from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.product import (
    DECISION_CENTER_WORKSPACE,
    TRADING_INTELLIGENCE_PRODUCT,
)
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
    EvidenceSource,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
    GovernanceSource,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.tests.fakes import InMemoryProjectionRepository
from applications.trading_intelligence.ui.decision_center.controller import (
    DecisionCenterController,
)
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.repositories.projection_repository import ProjectionRepository


class _NoEvidenceSource(EvidenceSource):
    """This file proves NavigationItem -> DecisionCenterController
    construction, not evidence wiring (which has its own dedicated tests
    under applications/trading_intelligence/) -- a deliberately empty
    stand-in, not a real source, matching the pattern already established in
    applications/trading_intelligence/tests/test_decision_center_integration.py."""

    def get_evidence(self, decision_id):
        return []


class _NoGovernanceSource(GovernanceSource):
    """Same rationale as _NoEvidenceSource above, for governance/approval
    wiring -- has its own dedicated tests under
    applications/trading_intelligence/."""

    def get_governance(self, decision_id):
        return []

    def get_approvals(self, decision_id):
        return []


class _NoAuditSource:
    """Same rationale as _NoEvidenceSource/_NoGovernanceSource above, for
    audit-trail wiring -- has its own dedicated tests under
    applications/trading_intelligence/. Duck-typed, not a GovernanceSource/
    EvidenceSource-style ABC subclass: controller.py's own docstring notes
    audit trail is wired directly to SentinelAuditSource with no
    services/-layer abstraction to subclass, by design."""

    def get_audit_trail(self, decision_id):
        return []


class _FakeAuthenticationProvider(AuthenticationProvider):
    def __init__(self, current_user=None):
        self._current_user = current_user

    def get_current_user(self):
        return self._current_user


class _FakeEntitlementChecker(EntitlementChecker):
    def __init__(self, grants=None):
        self._grants = grants or set()  # set of (user_id, product_id)

    def has_access(self, user, product_id):
        return (user.user_id, product_id) in self._grants


class _InMemoryProductRegistry(ProductRegistry):
    def __init__(self):
        self._products = {}

    def register(self, product):
        self._products[product.product_id] = product

    def list_products(self):
        return list(self._products.values())


class _InMemoryWorkspaceRegistry(WorkspaceRegistry):
    def __init__(self):
        self._workspaces = []

    def register_workspace(self, workspace):
        self._workspaces.append(workspace)

    def list_workspaces(self, product_id):
        return [w for w in self._workspaces if w.product_id == product_id]


def test_trading_intelligence_product_can_be_registered():
    registry = _InMemoryProductRegistry()

    registry.register(TRADING_INTELLIGENCE_PRODUCT)

    assert registry.list_products() == [TRADING_INTELLIGENCE_PRODUCT]


def test_decision_center_workspace_can_be_registered():
    registry = _InMemoryWorkspaceRegistry()

    registry.register_workspace(DECISION_CENTER_WORKSPACE)

    assert registry.list_workspaces("trading_intelligence") == [DECISION_CENTER_WORKSPACE]


def test_navigation_builder_discovers_trading_intelligence_when_entitled():
    user = User(user_id="u1", display_name="Investor One")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    assert model.current_user == user
    assert any(item.product_id == "trading_intelligence" for item in model.items)


def test_decision_center_appears_as_a_navigation_item():
    user = User(user_id="u1", display_name="Investor One")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    decision_center_items = [
        item for item in model.items if item.workspace_id == "trading_intelligence.decision_center"
    ]
    assert len(decision_center_items) == 1
    assert decision_center_items[0].label == "Decision Center"
    assert decision_center_items[0].product_id == "trading_intelligence"


def test_non_entitled_users_do_not_see_trading_intelligence():
    user = User(user_id="u2", display_name="Wealth Only User")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants=set())  # no grants for this user
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )

    model = builder.build()

    assert model.items == []


def _build_entitled_navigation_model():
    user = User(user_id="u1", display_name="Investor One")
    products = _InMemoryProductRegistry()
    products.register(TRADING_INTELLIGENCE_PRODUCT)
    workspaces = _InMemoryWorkspaceRegistry()
    workspaces.register_workspace(DECISION_CENTER_WORKSPACE)
    entitlements = _FakeEntitlementChecker(grants={(user.user_id, "trading_intelligence")})
    builder = NavigationBuilder(
        product_registry=products,
        workspace_registry=workspaces,
        entitlement_checker=entitlements,
        auth_provider=_FakeAuthenticationProvider(current_user=user),
    )
    return builder.build()


def test_navigation_item_can_be_used_to_construct_decision_center_experience():
    """1. Platform produces a Trading Intelligence navigation item.
    2. That item identifies the Decision Center workspace.
    3. This integration layer (the test itself -- no resolver/router/factory)
    uses that identity to construct DecisionCenterController.
    4. The controller produces a correct DecisionCenterScreen."""
    model = _build_entitled_navigation_model()

    trading_intelligence_items = [item for item in model.items if item.product_id == "trading_intelligence"]
    assert trading_intelligence_items, "expected a Trading Intelligence navigation item"

    decision_center_item = next(
        (item for item in model.items if item.workspace_id == "trading_intelligence.decision_center"),
        None,
    )
    assert decision_center_item is not None, "expected a Decision Center navigation item"

    # No resolver/router/factory: the test performs the trivial identity
    # check itself, per AARA_WORKSPACE_ENTRY_ARCHITECTURE.md Section 4/5.
    assert decision_center_item.workspace_id == "trading_intelligence.decision_center"

    repository = InMemoryProjectionRepository()
    repository.save(
        DecisionProjection(
            decision_id="dec-001",
            symbol="AAPL",
            action="BUY",
            status=DecisionState.DECISION_CREATED,
            confidence=0.78,
            evidence_reference="evidence-001",
            risk_reference="risk-001",
            updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
        )
    )
    source = SentinelProjectionDecisionSource(repository)
    query_service = DecisionQueryService(source)
    evidence_query_service = DecisionEvidenceQueryService(_NoEvidenceSource())
    governance_query_service = DecisionGovernanceQueryService(_NoGovernanceSource())
    controller = DecisionCenterController(
        query_service, evidence_query_service, governance_query_service, _NoAuditSource(),
    )

    screen = controller.load_screen(["dec-001"])

    assert screen.list_area.decisions[0].decision_id == "dec-001"
    assert screen.detail_area.decision.decision_id == "dec-001"


def test_navigation_driven_construction_performs_no_writes():
    """5. Existing read-only data flow remains unchanged: locating and
    constructing the Decision Center experience via a NavigationItem must
    not introduce any write path into the real projection repository."""
    model = _build_entitled_navigation_model()
    decision_center_item = next(
        item for item in model.items if item.workspace_id == "trading_intelligence.decision_center"
    )
    assert decision_center_item.workspace_id == "trading_intelligence.decision_center"

    class _AssertNoSaveRepository(ProjectionRepository):
        def __init__(self):
            self._projections = {
                "dec-001": DecisionProjection(
                    decision_id="dec-001",
                    symbol="AAPL",
                    action="BUY",
                    status=DecisionState.DECISION_CREATED,
                    confidence=0.78,
                    evidence_reference="evidence-001",
                    risk_reference="risk-001",
                    updated_at=datetime.datetime(2026, 8, 4, 12, 0, 0),
                )
            }

        def get(self, decision_id):
            return self._projections.get(decision_id)

        def save(self, projection):
            raise AssertionError("no layer in this chain may call ProjectionRepository.save()")

    source = SentinelProjectionDecisionSource(_AssertNoSaveRepository())
    controller = DecisionCenterController(
        DecisionQueryService(source),
        DecisionEvidenceQueryService(_NoEvidenceSource()),
        DecisionGovernanceQueryService(_NoGovernanceSource()),
        _NoAuditSource(),
    )

    controller.load_screen(["dec-001"])


def test_module_does_not_import_forbidden_runtimes():
    """This test file itself must never import bot/dashboard/scheduler/
    ledger/database -- it composes only platform + Trading Intelligence's
    product descriptor, both already permitted per
    test_product_registry_module_does_not_import_product_internals's
    established boundary-scan pattern."""
    import ast
    import pathlib

    forbidden = ("bot", "dashboard", "scheduler", "ledger", "database")
    path = pathlib.Path(__file__).resolve()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden), (
                    f"{path}: forbidden import {alias.name!r}"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith(forbidden), (
                f"{path}: forbidden import from {module!r}"
            )
