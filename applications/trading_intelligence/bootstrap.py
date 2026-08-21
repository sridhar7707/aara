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

import gradio as gr

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
from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    PortfolioIntelligenceUI,
)
from applications.trading_intelligence.ui.risk_intelligence.gradio_view import RiskIntelligenceUI


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


# Composition-only fix for a regression found in live verification: Decision
# Center's own theme.py gives .aara-shell-header a `margin-top: -16px
# !important` specifically to cancel .gradio-container's own 16px top
# padding, so the header sits flush against the true top of the page when
# DecisionCenterUI.build() runs standalone (the only context that CSS rule
# was ever designed for). Nested inside this composition's gr.TabbedInterface,
# the tab list now renders above it in the same document, so that same
# negative margin pulls the header up into the tab list's own box and
# intercepts its pointer events (confirmed via getBoundingClientRect +
# elementFromPoint: the header's top edge sits above the tab row's bottom
# edge). ".tabitem" is Gradio's own stable TabItem wrapper class (confirmed
# against the live DOM), giving this override higher selector specificity
# than the original "!important" rule without editing
# ui/decision_center/theme.py at all -- this selector never matches when
# DecisionCenterUI.build() is launched standalone, so that file and its
# standalone appearance are completely unaffected.
#
# Class selector, not scoped to Decision Center specifically -- since the
# AARA shell consistency pass gave Portfolio and Risk Intelligence their own
# .aara-shell-header (via ui/shell.py, styled by this same globally-merged
# theme.py CSS), this one rule already cancels the same negative margin
# inside their .tabitem wrappers too; nothing here needed to change for that.
#
# Duplicate-navigation audit: composing all three screens under one
# gr.TabbedInterface produces two visible nav rows per screen -- the outer
# native Gradio tabs (role="tablist") this composition adds, and each
# screen's own inner AARA nav (also role="tablist" as of this pass; see
# ui/shell.py's build_shell_nav_html() and decision_center/gradio_view.py's
# _SHELL_NAV_HTML). The live-verified fix (see audit notes) is to hide only
# the outer tabs, visually and in the accessibility tree -- not remove or
# restructure them -- since _INNER_NAV_LINK_JS below already drives the real
# tab-switching machinery through them via .click(), which works identically
# whether or not the target button is display:none. The selector excludes
# .aara-shell-nav-list explicitly: both navs now carry role="tablist", so a
# bare [role="tablist"] rule would hide the inner nav too, leaving zero
# visible navigation. Composition-only, exact same reasoning as the
# .aara-shell-header rule above: this selector only matches
# gr.TabbedInterface's own markup, so DecisionCenterUI.build() (and
# Portfolio/Risk's own build()) are completely unaffected when launched
# standalone.
#
# P3 Other Visual Polish audit (read-only, this session) found a third
# composition-only regression, same root cause as the two above: passing
# title="AARA Trading Intelligence" to gr.TabbedInterface() makes it render
# that title itself as a plain "# {title}" Markdown block above the tabs --
# an unstyled Gradio-default <h1> (confirmed live: no elem_id/elem_classes
# hook exists on gr.TabbedInterface's own title param to style or suppress
# it directly, Gradio's default gray/Inter font, sitting immediately above
# the fully-branded .aara-shell-header, which already states the same
# "AARA / Trading Intelligence" identity). Per gradio/interface.py's
# TabbedInterface.__init__, this default title always renders as
# `Markdown(f"<h1 style='...'>{title}</h1>")` -- an h1 with an inline
# `style` attribute and no class or elem_id of its own, wrapped (like every
# gr.Markdown/gr.HTML output) in Gradio's own generic `.prose` div
# (confirmed in the installed gradio package's HTML.svelte: `.prose` is
# applied unconditionally to gr.HTML's wrapper too, not only gr.Markdown's
# -- an earlier version of this comment claimed otherwise and was wrong).
# `.block` is Gradio's own generic per-component wrapper class (confirmed
# already relied on implicitly elsewhere in this app, e.g. the
# live-announcer's own rendered wrapper carries it); `:has()` is already an
# established selector technique in this exact codebase
# (`ui/decision_center/theme.py`'s row-selection rules), not a new pattern.
# A bare `.block:has(.prose h1)` therefore matches *any* `.prose`-wrapped
# h1, not just Gradio's own -- and after the Decision Center heading
# hierarchy fix promoted its own page header from `<h2 class="aara-eyebrow">`
# to `<h1 class="aara-eyebrow">` (see decision_center/gradio_view.py's
# _PAGE_HEADER_HTML, rendered via gr.HTML so it too lands inside `.prose`),
# the bare selector started hiding Decision Center's own legitimate page
# header as a false positive (live-verified P0 regression). The two h1s are
# distinguished by class: Gradio's default title carries no class at all,
# AARA's own page-header h1s always carry `aara-eyebrow` (see
# decision_center/gradio_view.py and ui/shell.py) -- so `:not(.aara-eyebrow)`
# excludes AARA's own headers while still matching Gradio's unstyled
# default. Hides the whole title block, not just the heading text, so the
# padded band collapses instead of leaving empty vertical space. This is a
# hide, not a restyle -- no color, font, or spacing token from either
# screen's own theme.py is touched, and the rule only ever matches this one
# composition-level block.
_TABBED_LAYOUT_CSS = """
.tabitem .aara-shell-header {
  margin-top: 0 !important;
}
[role="tablist"]:not(.aara-shell-nav-list) {
  display: none !important;
}
.block:has(.prose h1:not(.aara-eyebrow)) {
  display: none !important;
}
"""

# Composition-only fix for the second regression found in live verification:
# gr.TabbedInterface's own bundled Tabs component (Tabs-*.js) reactively
# re-invokes its "select the currently-selected tab" handler every time its
# registered-tabs list is marked dirty -- verified directly in the compiled
# source (`t.$$.dirty & 520 && m !== null && A(m)`), and that list is marked
# dirty on every child Tab's own re-registration, which happens on every SSE
# update Decision Center's own demo.load()/Refresh/row-select handlers
# produce (unrelated to any tab click). If that reactive re-selection lands
# in the transient window before a tab has re-registered, A(m) hits its own
# "not found or not interactive/visible" branch and logs
# console.warn("Attempted to select a non-interactive or hidden tab.") --
# confirmed harmless (tab content, selection, and focus are all still
# correct every time this was observed live). This is Gradio 4.44.1's own
# internal Svelte reactivity; no Python or CSS lever in this app reaches it,
# and patching the pinned Gradio version is out of scope. Filtering this one
# exact, known-benign message at the console is the narrowest available
# mitigation: matches only this single-argument, exact-string call, so every
# other console.warn (including the pre-existing, unrelated "Too many
# arguments provided for the endpoint." warning) is untouched.
_TAB_WARNING_SUPPRESSION_JS = """
<script>
(function () {
  var TARGET_WARNING = "Attempted to select a non-interactive or hidden tab.";
  var originalWarn = console.warn.bind(console);
  console.warn = function () {
    if (arguments.length === 1 && arguments[0] === TARGET_WARNING) {
      return;
    }
    originalWarn.apply(console, arguments);
  };
})();
</script>
"""

# Makes every screen's own inner shell-nav labels ("Decision Center",
# "Portfolio Intelligence", "Risk Intelligence" -- plain, non-interactive
# <span>s per each screen's own gr.HTML nav block: Decision Center's
# _SHELL_NAV_HTML, and, since the AARA shell consistency pass, Portfolio/Risk
# Intelligence's own ui/shell.py-built nav) actually navigate to the real tab
# this composition adds. None of the three screens' own files gain any new
# class/attribute or behavior change from this -- this bridge finds each
# label purely by its own already-fixed text content within
# .aara-shell-nav-list .nav-item, then forwards a click (or Enter/Space) to
# the matching real gr.TabbedInterface tab button, found the same way.
#
# Originally scoped to "Portfolio Intelligence" only, and to the first
# matching label found in the whole document (Decision Center was the only
# screen with a shell nav, so only one occurrence of that text ever existed,
# and nothing ever needed to link back to Decision Center since it was the
# only landing screen). The AARA shell consistency pass gave Portfolio and
# Risk Intelligence their own copy of the same nav -- including their own
# "Decision Center" item -- so all three labels now need wiring, and each
# appears up to three times in the composed DOM (once per screen's own nav).
# A user-reported bug (inner "Decision Center" unclickable while on Portfolio
# Intelligence) surfaced that the original 2-label list missed this: this
# bridge now wires every occurrence of all three managed labels, not just
# "Portfolio Intelligence"/"Risk Intelligence" and not just the first match.
# Bounded polling (wait for all three screens' own .aara-shell-nav-list to
# exist, wire once, then stop) is the same pattern Decision Center's own
# accessibility bridges already use for exactly the same reason: the labels
# don't exist yet when this <script> parses, since Gradio's client mounts
# asynchronously.
#
# Duplicate-navigation audit (this pass): wireNavItem() now sets role="tab"
# (was role="link"), matching the static role="tab"/aria-selected markup
# ui/shell.py's build_shell_nav_html() and decision_center/gradio_view.py's
# _SHELL_NAV_HTML now emit directly -- this bridge only adds the interactive
# behavior (cursor, tabIndex, click/Enter/Space forwarding) on top of markup
# that's already a correct ARIA Tabs pattern on its own; aria-selected itself
# is never touched here since each screen's nav is pre-built server-side
# with exactly one item already marked selected. This bridge's own click/
# Enter/Space forwarding logic is otherwise unchanged from before this pass.
_INNER_NAV_LINK_JS = """
<script>
(function () {
  var LABELS = ["Decision Center", "Portfolio Intelligence", "Risk Intelligence"];
  var EXPECTED_NAV_LISTS = 3;

  function findRealTab(label) {
    return Array.from(document.querySelectorAll('button[role="tab"]')).find(
      function (btn) { return btn.textContent.trim() === label; }
    );
  }

  function activateTab(label) {
    var tabButton = findRealTab(label);
    if (tabButton) {
      tabButton.click();
    }
  }

  function wireNavItem(span, label) {
    span.style.cursor = "pointer";
    span.tabIndex = 0;
    span.setAttribute("role", "tab");
    span.addEventListener("click", function () { activateTab(label); });
    span.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(label);
      }
    });
  }

  var attempts = 0;
  var maxAttempts = 100;
  var intervalId = setInterval(function () {
    attempts += 1;
    var navLists = document.querySelectorAll(".aara-shell-nav-list");
    if (navLists.length >= EXPECTED_NAV_LISTS) {
      clearInterval(intervalId);
      Array.from(document.querySelectorAll(".aara-shell-nav-list .nav-item")).forEach(
        function (span) {
          var text = span.textContent.trim();
          if (LABELS.indexOf(text) !== -1) {
            wireNavItem(span, text);
          }
        }
      );
      return;
    }
    if (attempts >= maxAttempts) {
      clearInterval(intervalId);
    }
  }, 50);
})();
</script>
"""


def build_trading_intelligence_app() -> gr.Blocks:
    """Composes every Trading Intelligence screen into one tabbed app via
    gr.TabbedInterface -- the smallest wiring that reaches multiple
    screens without touching any screen's own build() internals.
    TabbedInterface.render()s each already-built gr.Blocks unmodified
    (verified: component tree, event-dependency graph, and fn-index
    chaining all carry over intact), but it does not inherit a child
    Blocks' own title/css/head -- gr.TabbedInterface's own constructor
    defaults those to "Gradio"/None/None otherwise (verified directly
    against the installed gradio package) -- so css/head are read back off
    each already-built Blocks object and re-supplied explicitly here, the
    one thing this composition step must do that a screen's own build()
    does not. title is the one exception: gr.Blocks renders its `title`
    as a visible page <h1> (not just the browser tab title), and a
    UI-polish audit found this composition reusing Decision Center's own
    title verbatim left that <h1> permanently reading "-- Decision Center"
    on the Portfolio/Risk Intelligence tabs too -- so this composition
    uses its own neutral, screen-agnostic title instead of any one
    screen's.

    All three shipped screens are composed here -- Decision Center,
    Portfolio Intelligence, and Risk Intelligence -- each Blocks object
    unmodified from its own build()."""
    decision_blocks = build_application().build()
    portfolio_blocks = PortfolioIntelligenceUI().build()
    risk_blocks = RiskIntelligenceUI().build()

    merged_css = "\n".join(
        css for css in (
            decision_blocks.css, portfolio_blocks.css, risk_blocks.css, _TABBED_LAYOUT_CSS,
        )
        if css
    )
    merged_head = "\n".join(
        head for head in (
            decision_blocks.head, portfolio_blocks.head, risk_blocks.head,
            _TAB_WARNING_SUPPRESSION_JS, _INNER_NAV_LINK_JS,
        )
        if head
    )

    return gr.TabbedInterface(
        [decision_blocks, portfolio_blocks, risk_blocks],
        ["Decision Center", "Portfolio Intelligence", "Risk Intelligence"],
        title="AARA Trading Intelligence",
        css=merged_css,
        head=merged_head,
    )
