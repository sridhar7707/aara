"""Composition root for the AARA Trading Intelligence application.

Only place in this product that constructs sentinel_engine repositories,
services, SentinelEngine, or the Trading Intelligence read-side adapter/
query-service/controller/UI chain. Every other module receives its
collaborators through dependency injection instead of constructing them
itself, mirroring applications.wealth_intelligence.bootstrap's pattern.

Backend note: the LedgerStore/ProjectionRepository implementations below
are minimal in-memory placeholders, not a production persistence choice.
ADR-004 (sentinel-ledger-ownership-strategy) explicitly defers which
backend sentinel_engine's ledger should use until Phase 1A validation
completes. These classes live here in applications/trading_intelligence/,
not in sentinel_engine/, purely so build_application() has something
concrete to wire today; they are expected to be replaced once ADR-004 is
resolved.

Seed data: Decision Center is read-only (SentinelProjectionDecisionSource
never calls ProjectionRepository.save() -- see its own tests), so this
module seeds a handful of decisions through the real Sentinel Engine
write path (DecisionService/EvidenceService/GovernanceService via the
SentinelEngine facade) before building the read-side chain -- the same
way a real caller (a future signal-generation adapter) would produce
decisions. This is illustrative seed data for a first visible slice, not
real trading data.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sentinel_engine.domain.decision import Decision
from sentinel_engine.evidence.evidence import Evidence
from sentinel_engine.events.event import Event
from sentinel_engine.governance.approval import Approval
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.governance.policy import Policy
from sentinel_engine.ledger.ledger import LedgerStore
from sentinel_engine.projections.decision_projection import DecisionProjection
from sentinel_engine.queries.decision_query import DecisionQuery
from sentinel_engine.repositories.ledger_repository import LedgerRepository
from sentinel_engine.repositories.projection_repository import ProjectionRepository
from sentinel_engine.services.decision_service import DecisionService
from sentinel_engine.services.evidence_service import EvidenceService
from sentinel_engine.services.governance_service import GovernanceService
from sentinel_engine.services.sentinel_engine import SentinelEngine

from applications.platform.identity.authentication_provider import AuthenticationProvider
from applications.platform.identity.principal import PrincipalRegistry
from applications.platform.identity.supabase_authentication_provider import (
    SupabaseAuthenticationProvider,
)
from applications.platform.identity.user import User
from applications.platform.navigation.navigation_builder import NavigationBuilder
from applications.platform.registry.product_registry import Product, ProductRegistry
from applications.platform.workspaces.workspace import Workspace
from applications.platform.workspaces.workspace_registry import WorkspaceRegistry
from applications.trading_intelligence.adapters.sentinel_audit_source import SentinelAuditSource
from applications.trading_intelligence.adapters.sentinel_evidence_source import SentinelEvidenceSource
from applications.trading_intelligence.adapters.sentinel_governance_source import (
    SentinelGovernanceSource,
)
from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.entitlements import TradingIntelligenceEntitlementChecker
from applications.trading_intelligence.product import (
    DECISION_CENTER_WORKSPACE,
    TRADING_INTELLIGENCE_PRODUCT,
)
from applications.trading_intelligence.services.decision_evidence_query_service import (
    DecisionEvidenceQueryService,
)
from applications.trading_intelligence.services.decision_governance_query_service import (
    DecisionGovernanceQueryService,
)
from applications.trading_intelligence.services.decision_query_service import DecisionQueryService
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.gradio_view import DecisionCenterUI


class _InMemoryLedgerStore(LedgerStore):
    def __init__(self):
        self._events: List[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def read_all(self) -> List[Event]:
        return list(self._events)


class _InMemoryProjectionRepository(ProjectionRepository):
    def __init__(self):
        self._projections: Dict[str, DecisionProjection] = {}

    def save(self, projection: DecisionProjection) -> None:
        self._projections[projection.decision_id] = projection

    def get(self, decision_id: str) -> Optional[DecisionProjection]:
        return self._projections.get(decision_id)


class _NoOpSupabaseClient:
    """Placeholder Supabase client per ADR-029 Section 2.1 -- makes no
    network call and always reports no authenticated user."""

    def get_user(self, jwt=None):
        return None


class _ResolvedUserAuthenticationProvider(AuthenticationProvider):
    """Wraps an already-resolved Optional[User] value; performs no lookup,
    network call, or re-invocation of the real SupabaseAuthenticationProvider
    of any kind. Per ADR-038 Section 2.2 item 4 -- a second, distinct
    AuthenticationProvider implementation, not a second call on the real
    provider ADR-029 Section 2.2 governs. Gives NavigationBuilder something
    to call get_current_user() on without a second real lookup, keeping
    ADR-029 Section 2.2's "exactly once" call count on the real provider
    instance intact."""

    def __init__(self, current_user):
        self._current_user = current_user

    def get_current_user(self):
        return self._current_user


class _InMemoryProductRegistry(ProductRegistry):
    """Process-local, non-durable registry per ADR-038 Section 2.2 item 1 --
    mirrors _InMemoryLedgerStore/_InMemoryProjectionRepository's existing
    per-call pattern in this same file. Not shared, not a singleton, not
    module-level."""

    def __init__(self):
        self._products: Dict[str, Product] = {}

    def register(self, product: Product) -> None:
        self._products[product.product_id] = product

    def list_products(self) -> List[Product]:
        return list(self._products.values())


class _InMemoryWorkspaceRegistry(WorkspaceRegistry):
    """Process-local, non-durable registry per ADR-038 Section 2.2 item 1 --
    same rationale as _InMemoryProductRegistry above."""

    def __init__(self):
        self._workspaces: List[Workspace] = []

    def register_workspace(self, workspace: Workspace) -> None:
        self._workspaces.append(workspace)

    def list_workspaces(self, product_id: str) -> List[Workspace]:
        return [workspace for workspace in self._workspaces if workspace.product_id == product_id]


def _seed_decisions(engine: SentinelEngine) -> List[str]:
    """Drive five decisions through the real Sentinel Engine write path,
    each stopped at a different lifecycle stage (or governance verdict), so
    the first visible Decision Center screen demonstrates DecisionState's
    full range with genuine engine-produced data rather than hand-built
    projections -- dec-seed-004 (added to reach GOVERNANCE_EVALUATED)
    closes the one terminal-status gap the three original seeds left: none
    of them ever displayed GOVERNANCE_EVALUATED as a decision's *current*
    status, only as a passed-through stage inside dec-seed-003's own
    journey. dec-seed-005 (added alongside the Decision List verdict badge)
    closes the equivalent gap for approval verdict: dec-seed-003 is the
    only prior seed reaching record_approval(), and always with APPROVED --
    dec-seed-005 exercises the REJECTED path end to end.

    Each decision gets its own fixed timestamp(s), staggered across a single
    illustrative trading morning and advancing chronologically within a
    decision's own lifecycle (create -> evidence -> governance -> approval),
    rather than every event across all decisions sharing one identical
    instant -- still fully deterministic (fixed datetime literals, no
    randomness), just no longer visually flat. confidence is similarly
    given a genuine spread (0.54 / 0.71 / 0.83 / 0.91) instead of clustering
    in the 60-90% band. Governance evaluation's own displayed timestamp
    remains real-clock (GovernanceService.evaluate_policy() stamps
    datetime.utcnow() internally, not a caller-supplied value) -- unaffected
    by any of this, and out of scope to change without touching
    sentinel_engine. dec-seed-004 reuses "pol-seed-001" (already registered
    while seeding dec-seed-003, and GovernanceService's policy registry is
    shared across the whole engine instance for this function's duration)
    rather than registering a second, functionally-identical policy."""
    decision_ids: List[str] = []

    # dec-seed-001: DECISION_CREATED only.
    created_001 = datetime(2026, 8, 8, 8, 12, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-001", symbol="AAPL", action="BUY",
        timestamp=created_001, confidence=0.71,
        evidence_reference="evidence-seed-001", risk_reference="risk-seed-001",
    ))
    decision_ids.append("dec-seed-001")

    # dec-seed-002: through EVIDENCE_ATTACHED.
    created_002 = datetime(2026, 8, 8, 8, 47, 0)
    evidence_attached_002 = datetime(2026, 8, 8, 8, 52, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-002", symbol="MSFT", action="HOLD",
        timestamp=created_002, confidence=0.54,
        evidence_reference="evidence-seed-002", risk_reference="risk-seed-002",
    ))
    engine.attach_evidence("dec-seed-002", Evidence(
        evidence_id="ev-seed-002", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={
            "score": 0.58,
            # ADR-036/ADR-037-authorized shape (data["metadata"]): illustrates
            # the same raw_score/headlines fields the real finbert evidence
            # record already carries, so the ADR-037 Evidence detail
            # disclosure has something to render in the seeded demo -- see
            # ADR-034's own "Negative consequences" section, which names this
            # exact seed as not yet reflecting that shape.
            "metadata": {
                "raw_score": 0.58,
                "headlines": [
                    "Microsoft cloud growth steady but guidance mixed",
                    "Analysts split on MSFT ahead of earnings",
                ],
            },
        },
        collected_at=evidence_attached_002,
    ))
    decision_ids.append("dec-seed-002")

    # dec-seed-003: through APPROVAL_RECORDED (full lifecycle).
    created_003 = datetime(2026, 8, 8, 9, 5, 0)
    evidence_attached_003 = datetime(2026, 8, 8, 9, 11, 0)
    approved_003 = datetime(2026, 8, 8, 9, 34, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-003", symbol="NVDA", action="SELL",
        timestamp=created_003, confidence=0.91,
        evidence_reference="evidence-seed-003", risk_reference="risk-seed-003",
    ))
    engine.attach_evidence("dec-seed-003", Evidence(
        evidence_id="ev-seed-003", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={"score": 0.74}, collected_at=evidence_attached_003,
    ))
    engine.register_policy(Policy(
        policy_id="pol-seed-001", name="max_position_size",
        description="Caps single-position exposure as a percent of portfolio value.",
        enabled=True,
    ))
    engine.evaluate_policy("dec-seed-003", "pol-seed-001")
    engine.record_approval(Approval(
        approval_id="apr-seed-001", decision_id="dec-seed-003",
        status=ApprovalStatus.APPROVED, approved_by="risk_officer", timestamp=approved_003,
    ))
    decision_ids.append("dec-seed-003")

    # dec-seed-004: through GOVERNANCE_EVALUATED only -- governance passed,
    # awaiting approval. No record_approval() call.
    created_004 = datetime(2026, 8, 8, 9, 40, 0)
    evidence_attached_004 = datetime(2026, 8, 8, 9, 46, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-004", symbol="GOOGL", action="BUY",
        timestamp=created_004, confidence=0.83,
        evidence_reference="evidence-seed-004", risk_reference="risk-seed-004",
    ))
    engine.attach_evidence("dec-seed-004", Evidence(
        evidence_id="ev-seed-004", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={"score": 0.69}, collected_at=evidence_attached_004,
    ))
    engine.evaluate_policy("dec-seed-004", "pol-seed-001")
    decision_ids.append("dec-seed-004")

    # dec-seed-005: through APPROVAL_RECORDED with a REJECTED verdict --
    # full lifecycle like dec-seed-003, but exercising the rejection path
    # end to end (Decision List verdict badge, Decision Detail approval
    # card) that no prior seed demonstrated. Reuses "pol-seed-001" for the
    # same reason dec-seed-004 does.
    created_005 = datetime(2026, 8, 8, 9, 52, 0)
    evidence_attached_005 = datetime(2026, 8, 8, 9, 58, 0)
    rejected_005 = datetime(2026, 8, 8, 10, 4, 0)
    engine.create_decision(Decision(
        decision_id="dec-seed-005", symbol="TSLA", action="BUY",
        timestamp=created_005, confidence=0.61,
        evidence_reference="evidence-seed-005", risk_reference="risk-seed-005",
    ))
    engine.attach_evidence("dec-seed-005", Evidence(
        evidence_id="ev-seed-005", evidence_type="NEWS_SENTIMENT", source="newsapi",
        data={"score": 0.41}, collected_at=evidence_attached_005,
    ))
    engine.evaluate_policy("dec-seed-005", "pol-seed-001")
    engine.record_approval(Approval(
        approval_id="apr-seed-002", decision_id="dec-seed-005",
        status=ApprovalStatus.REJECTED, approved_by="risk_officer", timestamp=rejected_005,
    ))
    decision_ids.append("dec-seed-005")

    return decision_ids


def build_application() -> DecisionCenterUI:
    auth_provider = SupabaseAuthenticationProvider(_NoOpSupabaseClient())
    # ADR-029 Sec 2.3/2.4: captured only -- never passed to any collaborator
    # constructed below, and a None result is not an error.
    current_user: Optional[User] = auth_provider.get_current_user()

    # ADR-032 Sec 2/3: fresh, process-local registry; current_user.user_id is
    # today's opaque lookup key only, not a durable identity mapping. Result
    # stays local -- never passed to any collaborator constructed below.
    principal_registry = PrincipalRegistry()
    current_principal = (
        principal_registry.get_or_create(current_user.user_id)
        if current_user is not None
        else None
    )

    # ADR-038 Sec 2.2: product-local, in-memory registries, registered with
    # only Trading Intelligence's own already-existing descriptors -- no
    # Wealth Intelligence import, no platform-wide composition root.
    product_registry = _InMemoryProductRegistry()
    product_registry.register(TRADING_INTELLIGENCE_PRODUCT)

    workspace_registry = _InMemoryWorkspaceRegistry()
    workspace_registry.register_workspace(DECISION_CENTER_WORKSPACE)

    entitlement_checker = TradingIntelligenceEntitlementChecker()

    # ADR-038 Sec 2.2 item 4: NavigationBuilder receives a
    # _ResolvedUserAuthenticationProvider wrapping the already-captured
    # current_user, never the real auth_provider instance -- preserves
    # ADR-029 Sec 2.2's "exactly once" call count on that instance.
    resolved_user_provider = _ResolvedUserAuthenticationProvider(current_user)
    navigation_builder = NavigationBuilder(
        product_registry, workspace_registry, entitlement_checker, resolved_user_provider,
    )
    # ADR-038 Sec 2.3: confined to local scope -- never passed to any
    # collaborator constructed below, never returned.
    navigation_model = navigation_builder.build()

    ledger_repository = LedgerRepository(_InMemoryLedgerStore())
    projection_repository = _InMemoryProjectionRepository()

    decision_service = DecisionService(ledger_repository, projection_repository)
    evidence_service = EvidenceService(ledger_repository, projection_repository)
    governance_service = GovernanceService(ledger_repository, projection_repository)
    engine = SentinelEngine(decision_service, evidence_service, governance_service)

    decision_ids = _seed_decisions(engine)

    decision_query = DecisionQuery(ledger_repository, projection_repository)

    source = SentinelProjectionDecisionSource(projection_repository, decision_query)
    query_service = DecisionQueryService(source)

    evidence_source = SentinelEvidenceSource(decision_query)
    evidence_query_service = DecisionEvidenceQueryService(evidence_source)

    governance_source = SentinelGovernanceSource(decision_query)
    governance_query_service = DecisionGovernanceQueryService(governance_source)

    audit_source = SentinelAuditSource(decision_query)

    controller = DecisionCenterController(
        query_service, evidence_query_service, governance_query_service, audit_source,
    )

    return DecisionCenterUI(controller, decision_ids)
