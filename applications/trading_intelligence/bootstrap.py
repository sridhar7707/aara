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

No seed data: Decision Center renders only real decisions. No production
decision source is wired yet (ADR-004 defers the ledger backend), so
build_application() hands DecisionCenterUI an empty decision-id
collection and the screen shows its existing "No decisions recorded yet."
empty state until a governed real producer exists. The write-path
services and the SentinelEngine facade are still constructed below -- the
read chain shares their ledger/projection repositories -- but nothing
drives them now that seeding is removed.
"""
from dataclasses import replace
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import gradio as gr

from sentinel_engine.events.event import Event
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
from applications.trading_intelligence.adapters.alpaca_news_source import (
    AlpacaNewsSource,
    OvernightHoldingsNews,
)
from applications.trading_intelligence.adapters.alpaca_paper_orders_source import (
    AlpacaPaperOrdersSource,
)
from applications.trading_intelligence.adapters.alpaca_paper_source import AlpacaPaperSource
from applications.trading_intelligence.adapters.legacy_candidate_screening_source import (
    CandidateScreeningSnapshot,
    LegacyCandidateScreeningSource,
)
from applications.trading_intelligence.adapters.legacy_capital_source import LegacyCapitalSource
from applications.trading_intelligence.adapters.legacy_position_source import (
    LegacyPositionSource,
    OpenPosition,
)
from applications.trading_intelligence.adapters.legacy_regime_source import LegacyRegimeSource
from applications.trading_intelligence.adapters.legacy_risk_state_source import LegacyRiskStateSource
from applications.trading_intelligence.adapters.live_price_source import LivePriceSource
from applications.trading_intelligence.adapters.sentinel_audit_source import SentinelAuditSource
from applications.trading_intelligence.adapters.sentinel_evidence_source import SentinelEvidenceSource
from applications.trading_intelligence.adapters.sentinel_governance_source import (
    SentinelGovernanceSource,
)
from applications.trading_intelligence.adapters.sentinel_projection_decision_source import (
    SentinelProjectionDecisionSource,
)
from applications.trading_intelligence.adapters.trades_db_snapshot import fetch_trades_db_snapshot
from applications.trading_intelligence.bootstrap_trades_db_snapshot import (
    legacy_source_kwargs,
    snapshot_bound_provider,
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
from applications.trading_intelligence.ui.morning_brief.gradio_view import MorningBriefUI
from applications.trading_intelligence.ui.morning_brief.mock_data import (
    build_mock_screen as build_mock_morning_brief_screen,
)
from applications.trading_intelligence.ui.morning_brief.screen import MorningBriefScreen
from applications.trading_intelligence.ui.performance_learning.gradio_view import (
    PerformanceLearningUI,
)
from applications.trading_intelligence.ui.portfolio_intelligence.gradio_view import (
    PortfolioIntelligenceUI,
)
from applications.trading_intelligence.ui.portfolio_intelligence.screen import (
    PortfolioHolding,
    PortfolioScreen,
)
from applications.trading_intelligence.ui.risk_intelligence.gradio_view import RiskIntelligenceUI
from applications.trading_intelligence.ui.risk_intelligence.screen import RiskScreen, RiskSnapshot
from applications.trading_intelligence.ui.settings.gradio_view import SettingsUI


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
    # Constructed but undriven now that seeding is removed -- same
    # retained-seam pattern as navigation_model above. The read chain below
    # shares ledger_repository/projection_repository; removing the
    # SentinelEngine write-path seam would be an out-of-scope
    # composition-root change. Real decisions appear only once a governed
    # producer writes them.
    engine = SentinelEngine(decision_service, evidence_service, governance_service)

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

    return DecisionCenterUI(controller, [])


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
#
# Six-screen audit (live Playwright verification, this pass): LABELS and
# EXPECTED_NAV_LISTS were never updated when Morning Brief, Performance &
# Learning, and Settings were added -- they stayed at the original 3-label/
# 3-list values. Concrete, live-verified consequence: any .nav-item span
# reading "Morning Brief", "Performance & Learning", or "Settings" was never
# passed to wireNavItem() (LABELS.indexOf(text) === -1), so it stayed a
# static <span> with no click handler -- indistinguishable by sight from a
# working nav item, but a completely dead link. Reproduced live: after
# navigating away from Morning Brief (the only tab reachable without a nav
# click, since it's index 0), no click path anywhere in the app could ever
# reach Morning Brief, Performance & Learning, or Settings again. All six
# labels are wired now; EXPECTED_NAV_LISTS raised to 6 to match the six
# .aara-shell-nav-list blocks actually mounted (confirmed live via
# document.querySelectorAll('.aara-shell-nav-list').length === 6).
_INNER_NAV_LINK_JS = """
<script>
(function () {
  var LABELS = [
    "Morning Brief", "Decision Center", "Portfolio Intelligence", "Risk Intelligence",
    "Performance & Learning", "Settings"
  ];
  var EXPECTED_NAV_LISTS = 6;

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


def _format_candidate_screening_summary(snapshot: CandidateScreeningSnapshot) -> str:
    """Pure formatting, no I/O -- always states the actual persisted
    screened_at date literally (never "today"), so a stale local
    screener_log (the screener may not have run recently) can never be
    misrepresented as a fresh, current-day result."""
    screened_date = datetime.fromisoformat(snapshot.screened_at).date().isoformat()
    count = len(snapshot.picks)
    plural = "s" if count != 1 else ""
    top = snapshot.picks[0]
    if top.rank is None:
        return f"{count} candidate{plural} screened on {screened_date}."
    score_clause = f", score {top.composite_score:.2f}" if top.composite_score is not None else ""
    return (
        f"{count} candidate{plural} screened on {screened_date} -- "
        f"top pick {top.symbol} (rank {top.rank}{score_clause})."
    )


def _format_overnight_holdings_news(
    news: OvernightHoldingsNews, holdings_symbols: Tuple[str, ...]
) -> str:
    """Pure formatting, no I/O. news is already a real, successful fetch
    result (callers only reach here when AlpacaNewsSource returned
    non-None) -- an empty result means the fetch succeeded and simply
    matched nothing, which is stated plainly rather than left as an
    unavailable section. The headline text is the provider's own,
    unmodified: this summary reports what Alpaca returned for the current
    holdings, it never characterises, scores, or acts on it."""
    if not holdings_symbols:
        return "No open holdings -- no overnight holdings news to report."
    symbols_clause = ", ".join(holdings_symbols)
    if news.is_empty:
        return f"No recent news for current holdings ({symbols_clause})."
    count = len(news.items)
    plural = "s" if count != 1 else ""
    latest = news.items[0]
    source_clause = f" ({latest.source})" if latest.source else ""
    return (
        f"{count} recent headline{plural} for current holdings ({symbols_clause}) -- "
        f'latest: "{latest.headline}"{source_clause}.'
    )


def _build_morning_brief_screen(db_path: Optional[str] = None) -> MorningBriefScreen:
    """Assemble one real-or-unavailable MorningBriefScreen from the legacy
    trades.db adapters plus the read-only AlpacaNewsSource.

    Real Portfolio Snapshot (reusing the exact same, unmodified
    LegacyCapitalSource already wired for Portfolio Intelligence -- no
    second capital adapter), real Market Mood/Regime (via
    LegacyRegimeSource), and real Candidate Screening Summary (via
    LegacyCandidateScreeningSource, reading trades.db's screener_log --
    explicitly not the Trust Ledger's candidate_evaluation_events, which
    stays gated behind ADR-004/Q1) when their respective legacy trades.db
    data is available. Overnight Holdings News is real Alpaca news (via
    AlpacaNewsSource, read-only NewsClient GET) filtered to the current
    holdings symbols from the same LegacyPositionSource Portfolio
    Intelligence already uses -- attempted only when real holdings can be
    determined; a None from either adapter (no trades.db, no Alpaca
    credentials, network/API failure, malformed response) leaves the
    section on its existing honest unavailable message, and news is
    treated as source/evidence only, never as a decision input. Each
    real-eligible section falls back to its own existing unavailable
    message independently when its adapter finds no real data -- expected
    in the deployed HF Space today, which has no mechanism yet to obtain
    trades.db and no Alpaca credentials.

    This function is the `screen_provider` MorningBriefUI re-invokes on
    every demo.load() and every Refresh click -- it is a fresh read each
    call, holding no state and caching nothing, so the screen always
    reflects the adapters' current answer."""
    illustrative_screen = build_mock_morning_brief_screen()
    portfolio_snapshot = illustrative_screen.portfolio_snapshot
    market_mood_regime = illustrative_screen.market_mood_regime
    candidate_screening_summary = illustrative_screen.candidate_screening_summary
    overnight_holdings_news = illustrative_screen.overnight_holdings_news

    legacy_kwargs = legacy_source_kwargs(db_path)

    # ADR-061 Category A / Amendment 1: adapters return ReadResult; unwrap
    # the underlying value for the existing "only replace the illustrative
    # summary when real data is present" logic, and record the section's
    # IntegrationHealth on every path -- including the unavailable fallback,
    # so the view can name the specific reason (ADR-061 A4). Recording
    # health does not change is_available (still keyed on available_summary).
    capital_result = LegacyCapitalSource(**legacy_kwargs).get_capital_summary()
    portfolio_snapshot = replace(portfolio_snapshot, health=capital_result.health)
    if capital_result.value is not None:
        real_capital = capital_result.value
        portfolio_snapshot = replace(
            portfolio_snapshot,
            available_summary=(
                f"Total value ${real_capital.total_value:,.2f} "
                f"(${real_capital.available_cash:,.2f} cash, "
                f"${real_capital.invested_amount:,.2f} invested)."
            ),
        )

    regime_result = LegacyRegimeSource(**legacy_kwargs).get_latest_regime()
    market_mood_regime = replace(market_mood_regime, health=regime_result.health)
    if regime_result.value is not None:
        market_mood_regime = replace(
            market_mood_regime,
            available_summary=f"Current market regime: {regime_result.value}.",
        )

    screening_result = LegacyCandidateScreeningSource(**legacy_kwargs).get_latest_screening()
    candidate_screening_summary = replace(
        candidate_screening_summary, health=screening_result.health
    )
    if screening_result.value is not None:
        candidate_screening_summary = replace(
            candidate_screening_summary,
            available_summary=_format_candidate_screening_summary(screening_result.value),
        )

    positions_result = LegacyPositionSource(**legacy_kwargs).get_open_positions()
    if positions_result.value is not None:
        holdings_symbols = tuple(position.symbol for position in positions_result.value)
        news_result = AlpacaNewsSource().get_overnight_holdings_news(holdings_symbols)
        overnight_holdings_news = replace(
            overnight_holdings_news, health=news_result.health
        )
        if news_result.value is not None:
            overnight_holdings_news = replace(
                overnight_holdings_news,
                available_summary=_format_overnight_holdings_news(
                    news_result.value, holdings_symbols
                ),
            )

    return replace(
        illustrative_screen,
        portfolio_snapshot=portfolio_snapshot,
        market_mood_regime=market_mood_regime,
        candidate_screening_summary=candidate_screening_summary,
        overnight_holdings_news=overnight_holdings_news,
    )


def _build_morning_brief_ui(db_path: Optional[str] = None) -> MorningBriefUI:
    """Wire Morning Brief to fetch its data at render time, from the
    runtime `db_path` snapshot when one was fetched (see
    `snapshot_bound_provider`)."""
    return MorningBriefUI(
        screen_provider=snapshot_bound_provider(_build_morning_brief_screen, db_path)
    )


def _build_portfolio_holdings(
    positions: Tuple[OpenPosition, ...], prices: Dict[str, float],
) -> Tuple[PortfolioHolding, ...]:
    """Combines real open positions with real live prices into
    PortfolioHolding rows -- weight_pct is each holding's share of total
    *holdings* market value (not total portfolio value including cash),
    matching mock_data.py's own existing convention where weight_pct sums
    to 100.0 across holdings. Pure function, no I/O -- both inputs must
    already be real (or this would silently mix real and fabricated
    figures), which is why callers only invoke this after both
    LegacyPositionSource and LivePriceSource have already succeeded."""
    market_values = {position.symbol: prices[position.symbol] * position.quantity for position in positions}
    total_market_value = sum(market_values.values())
    return tuple(
        PortfolioHolding(
            symbol=position.symbol,
            quantity=position.quantity,
            price=prices[position.symbol],
            market_value=market_values[position.symbol],
            weight_pct=(
                (market_values[position.symbol] / total_market_value) * 100
                if total_market_value > 0 else 0.0
            ),
        )
        for position in positions
    )


def _with_alpaca_paper_data(screen: PortfolioScreen) -> PortfolioScreen:
    """Attaches Alpaca's own Paper account/positions to `screen` when both
    are available, leaving it unchanged (alpaca_account stays None --
    unavailable) otherwise. Deliberately independent of every other
    branch in _build_portfolio_intelligence_ui() below: Alpaca is a
    completely separate broker-side source from capital_pools/
    position_state, so its availability must never be gated by whether
    the legacy capital/holdings adapters found data, and vice versa. All
    or nothing, like every other adapter pairing in this product -- a
    real account snapshot next to a failed positions fetch would imply a
    connected-but-empty account when the true state is simply unknown."""
    # ADR-061 Category A / Amendment 1: adapters return ReadResult. The
    # attach-only-when-both-healthy rule is unchanged; the section's
    # IntegrationHealth is recorded on every path (including the
    # unavailable one, where it names the reason).
    alpaca = AlpacaPaperSource()
    account_result = alpaca.get_account()
    if account_result.value is None:
        return replace(screen, alpaca_health=account_result.health)
    positions_result = alpaca.get_positions()
    if positions_result.value is None:
        return replace(screen, alpaca_health=positions_result.health)
    return replace(
        screen,
        alpaca_account=account_result.value,
        alpaca_positions=positions_result.value,
        alpaca_health=account_result.health,
    )


def _with_alpaca_orders_data(screen: PortfolioScreen) -> PortfolioScreen:
    """Attaches Alpaca's own broker-side recent Paper orders to `screen`
    when the read succeeds, leaving it unchanged (alpaca_orders stays
    None -- unavailable) otherwise. Deliberately independent of every
    other branch in _build_portfolio_intelligence_ui() AND of
    _with_alpaca_paper_data(): the recent-orders observation channel is a
    separate Alpaca read from the account/positions one, so its
    availability must never be gated by whether that one found data, or by
    capital_pools/position_state. A read that matched no orders returns an
    empty AlpacaOrdersSnapshot (attached -- a real "no recent orders"
    state); only a None leaves the section unavailable. Read-only
    observation only, never merged with Holdings/Capital Summary and
    carrying no Decision Center linkage -- see
    adapters/alpaca_paper_orders_source.py's own docstring."""
    # ADR-061 Category A / Amendment 1: adapter returns ReadResult. An empty
    # snapshot is still a HEALTHY value (attached); only a non-HEALTHY read
    # leaves the section unavailable. IntegrationHealth is recorded on every
    # path.
    orders_result = AlpacaPaperOrdersSource().get_recent_orders()
    if orders_result.value is None:
        return replace(screen, alpaca_orders_health=orders_result.health)
    return replace(
        screen,
        alpaca_orders=orders_result.value,
        alpaca_orders_health=orders_result.health,
    )


def _build_portfolio_intelligence_screen(db_path: Optional[str] = None) -> PortfolioScreen:
    """Assemble one real-or-unavailable PortfolioScreen from the legacy
    trades.db adapters plus the three read-only Alpaca paper adapters.

    Real Capital Summary/Allocation when the legacy trades.db capital
    pool is available (adapters/legacy_capital_source.py); an explicit
    UNAVAILABLE state (capital=None) otherwise -- never illustrative or
    fabricated figures. Holdings becomes real only when BOTH the real open
    positions (adapters/legacy_position_source.py, a local trades.db read)
    AND real current prices (adapters/live_price_source.py, a live network
    call) are available; a real open-position source reporting zero
    positions is a genuine EMPTY state (holdings=()); any failure in that
    chain leaves Holdings UNAVAILABLE (holdings=None), never a fabricated
    table. In the deployed HF Space today -- no mechanism yet to obtain
    trades.db, and possibly no outbound network to the price provider --
    every section renders its explicit unavailable state.

    Alpaca Paper Account/Positions and recent orders (2026-08-27 units)
    are attached independently on the single return path via
    _with_alpaca_paper_data() and _with_alpaca_orders_data() -- unchanged,
    and entirely separate from the legacy trades.db-based Capital Summary/
    Holdings this function builds. See those adapters' own docstrings for
    the paper-only safety guarantees.

    This function is the `screen_provider` PortfolioIntelligenceUI
    re-invokes on every demo.load() and every Refresh click -- it is a
    fresh read each call, holding no state and caching nothing, so the
    screen always reflects the adapters' current answer."""
    legacy_kwargs = legacy_source_kwargs(db_path)

    # ADR-061 Category A / Amendment 1: adapters return ReadResult; unwrap
    # the underlying value into the existing capital/holdings fields
    # (semantics unchanged -- a real value, an empty tuple for a flat
    # account, or None when unavailable) and record the section's
    # IntegrationHealth alongside it.
    capital_result = LegacyCapitalSource(**legacy_kwargs).get_capital_summary()

    positions_result = LegacyPositionSource(**legacy_kwargs).get_open_positions()
    if positions_result.value is None:
        real_holdings = None
        holdings_health = positions_result.health
    elif len(positions_result.value) == 0:
        real_holdings = ()
        holdings_health = positions_result.health
    else:
        symbols = tuple(position.symbol for position in positions_result.value)
        prices_result = LivePriceSource().get_current_prices(symbols)
        if prices_result.value is not None:
            real_holdings = _build_portfolio_holdings(
                positions_result.value, prices_result.value
            )
        else:
            real_holdings = None
        holdings_health = prices_result.health

    screen = PortfolioScreen(
        capital=capital_result.value,
        capital_health=capital_result.health,
        holdings=real_holdings,
        holdings_health=holdings_health,
    )
    return _with_alpaca_orders_data(_with_alpaca_paper_data(screen))


def _build_portfolio_intelligence_ui(db_path: Optional[str] = None) -> PortfolioIntelligenceUI:
    """Wire Portfolio Intelligence to fetch its data at render time, from
    the runtime `db_path` snapshot when one was fetched (see
    `snapshot_bound_provider`)."""
    return PortfolioIntelligenceUI(
        screen_provider=snapshot_bound_provider(_build_portfolio_intelligence_screen, db_path)
    )


_RISK_STATE_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")


def _format_risk_state_as_of(raw: str) -> str:
    """Presentation-only: convert the `risk_state.updated_at` ISO string
    the adapter returns into the same "%Y-%m-%d %H:%M %Z" America/Chicago
    wall-clock format every other Trading Intelligence timestamp uses. A
    naive value is treated as UTC (that is what bot/db/risk_state.py and
    bot/trust_ledger/risk.py write). If it cannot be parsed at all the raw
    string is passed through unchanged rather than dropped."""
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_RISK_STATE_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")


def _build_risk_intelligence_screen(db_path: Optional[str] = None) -> RiskScreen:
    """Assemble one real-or-unavailable RiskScreen from the operational
    `risk_state` table (Group C, mutable) via the read-only
    LegacyRiskStateSource.

    The only fields that table can supply are the risk governor's most
    recently *observed* classification (NORMAL/WARNING/DEFENSIVE) and the
    time it was written. `trigger_reason` and recommended/actual sizing
    are NOT persisted in `risk_state` -- they live only in the
    hash-chained `risk_evaluation_events` ledger table, which this slice
    deliberately does not read -- so they are left as None and the view
    states they are not recorded in this data source. History is never
    fabricated: it stays empty and the view shows its existing
    "No risk evaluations recorded yet." message.

    None from the adapter (no trades.db -- the deployed HF Space's normal
    state -- missing table/row, or an empty/invalid value) yields an
    unavailable RiskScreen() and the view renders its explicit UNAVAILABLE
    state. Never mock/illustrative data.

    This is the `screen_provider` RiskIntelligenceUI re-invokes on every
    demo.load() and every Refresh click -- a fresh read each call, holding
    no state and caching nothing."""
    # ADR-061 Category A / Amendment 1: adapter returns ReadResult. `current`
    # stays None (UNAVAILABLE render) both when the read failed and when the
    # table simply has no risk_governor_state row; state_health carries
    # which of the two it was.
    state_result = LegacyRiskStateSource(**legacy_source_kwargs(db_path)).get_risk_state()
    if state_result.value is None:
        return RiskScreen(state_health=state_result.health)
    return RiskScreen(
        current=RiskSnapshot(
            state=state_result.value.state,
            as_of=_format_risk_state_as_of(state_result.value.as_of),
        ),
        state_health=state_result.health,
    )


def _build_risk_intelligence_ui(db_path: Optional[str] = None) -> RiskIntelligenceUI:
    """Wire Risk Intelligence to fetch its data at render time, from the
    runtime `db_path` snapshot when one was fetched (see
    `snapshot_bound_provider`)."""
    return RiskIntelligenceUI(
        screen_provider=snapshot_bound_provider(_build_risk_intelligence_screen, db_path)
    )


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

    All six shipped screens are composed here -- Morning Brief, Decision
    Center, Portfolio Intelligence, Risk Intelligence, Performance &
    Learning, and Settings -- each Blocks object unmodified from its own
    build(). This is the complete, frozen six-screen set per
    docs/products/AARA_TRADING_INTELLIGENCE_UI_SPECIFICATION.md Section 1."""
    # ADR-055 Section 2: obtain a read-only, ephemeral local snapshot of the
    # bot's published `trades.db` dataset once per process. ADR-061
    # Category A / Amendment 1: fetch_trades_db_snapshot() now returns a
    # ReadResult; unwrap its value (a local path, or None on any failure --
    # no HF_TOKEN, no network, 404, malformed file). On None the legacy
    # adapters keep their `"trades.db"` default and every section stays on
    # its existing honest-unavailable / illustrative fallback. Only the
    # three legacy-trades.db-backed screens receive it; Decision Center
    # (build_application()) reads no trades.db and is untouched.
    snapshot_db_path = fetch_trades_db_snapshot().value

    morning_brief_blocks = _build_morning_brief_ui(snapshot_db_path).build()
    decision_blocks = build_application().build()
    portfolio_blocks = _build_portfolio_intelligence_ui(snapshot_db_path).build()
    risk_blocks = _build_risk_intelligence_ui(snapshot_db_path).build()
    performance_learning_blocks = PerformanceLearningUI().build()
    settings_blocks = SettingsUI().build()

    merged_css = "\n".join(
        css for css in (
            morning_brief_blocks.css, decision_blocks.css, portfolio_blocks.css,
            risk_blocks.css, performance_learning_blocks.css, settings_blocks.css,
            _TABBED_LAYOUT_CSS,
        )
        if css
    )
    merged_head = "\n".join(
        head for head in (
            morning_brief_blocks.head, decision_blocks.head, portfolio_blocks.head,
            risk_blocks.head, performance_learning_blocks.head, settings_blocks.head,
            _TAB_WARNING_SUPPRESSION_JS, _INNER_NAV_LINK_JS,
        )
        if head
    )

    return gr.TabbedInterface(
        [
            morning_brief_blocks, decision_blocks, portfolio_blocks, risk_blocks,
            performance_learning_blocks, settings_blocks,
        ],
        [
            "Morning Brief", "Decision Center", "Portfolio Intelligence", "Risk Intelligence",
            "Performance & Learning", "Settings",
        ],
        title="AARA Trading Intelligence",
        css=merged_css,
        head=merged_head,
    )
