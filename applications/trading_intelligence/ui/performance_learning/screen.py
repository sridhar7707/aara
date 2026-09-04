"""Performance & Learning screen structure.

Framework-independent dataclasses (no gradio import). Two of the three
frozen IA areas -- Attribution Breakdown, Model Confidence Calibration --
still have no wired data source and stay on a fixed, honest unavailable
message (Wave 2A produces no attribution or calibration data and none is
fabricated here).

Wave 2B wires the first real source into the third area, **Outcome
History**: the verified trades-only decision-outcome lineage produced by
`services/decision_outcome_query_service.DecisionOutcomeQueryService`
(Wave 2A, frozen and consumed unchanged). The composition root
(bootstrap.py) reads that lineage and maps each `DecisionOutcome` to an
`OutcomeHistoryRow` here -- a P&L-owned presentation shape, never the
Wave 2A contract type itself, so this UI stays decoupled from the
contract's enums. Nothing here recomputes P&L, holding period, exit
price, or outcome direction; Wave 2A owns those semantics.

Area titles are exact string literals matching the frozen IA's own
"Required information" wording verbatim.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from applications.platform.integrations import IntegrationHealth
from applications.trading_intelligence.contracts.candidate_decision_inspection_contract import (
    CandidateDecisionInspection,
    LedgerFunnelSummary,
)

OUTCOME_HISTORY_TITLE = "Outcome History"
ATTRIBUTION_BREAKDOWN_TITLE = "Attribution Breakdown"
MODEL_CONFIDENCE_CALIBRATION_TITLE = "Model Confidence Calibration"

# Wave 3C (ADR-064): an additive section fed by the Wave 3A read-side
# source + Wave 3B query service through the composition root. Decision-time
# inspection only -- no outcome / P&L / trade linkage on this surface.
DECISION_LEDGER_INSPECTION_TITLE = "Decision Ledger Inspection"
_LEDGER_EMPTY_MESSAGE = "No decision ledger records available."
_LEDGER_UNAVAILABLE_FALLBACK = (
    "The decision ledger snapshot is not available in this environment."
)

_OUTCOME_HISTORY_EMPTY_MESSAGE = (
    "No BUY decisions are present in the current trades snapshot."
)


@dataclass(frozen=True)
class PerformanceLearningSection:
    title: str
    unavailable_message: str


@dataclass(frozen=True)
class OutcomeHistoryRow:
    """One Outcome History table row -- the P&L-owned presentation shape
    for one Wave 2A ``DecisionOutcome``.

    Every field is a display string the composition root formatted from
    the frozen ``DecisionOutcome``; nothing here is recomputed. An empty
    string means "not applicable to this outcome's state" (e.g. the exit
    columns of an OPEN decision, or ``direction`` for anything other than
    CLOSED), never "unknown".
    """

    decision: str
    entry_date: str
    status: str
    exit_date: str
    holding_days: str
    realized_pnl_usd: str
    realized_pnl_pct: str
    exit_basis: str
    pairing_method: str
    pairing_confidence: str
    direction: str


@dataclass(frozen=True)
class PerformanceLearningScreen:
    outcome_history: PerformanceLearningSection
    attribution_breakdown: PerformanceLearningSection
    model_confidence_calibration: PerformanceLearningSection
    # Wave 2B: populated by the composition root from the Wave 2A
    # OutcomeLineage. `outcome_health` carries the DecisionOutcomeQueryService
    # ReadResult health (None only in a standalone no-provider build);
    # `outcome_rows` is one row per DecisionOutcome; `summary` is the
    # factual count line derived from the lineage.
    outcome_rows: Tuple[OutcomeHistoryRow, ...] = ()
    outcome_health: Optional[IntegrationHealth] = None
    summary: Optional[str] = None
    # Wave 3C (ADR-064): the composition root reads the published Trust
    # Ledger snapshot through the Wave 3A source + Wave 3B query service and
    # attaches the result here. `ledger_health` carries the
    # CandidateDecisionQueryService ReadResult health (None only in a
    # standalone no-provider build); `ledger_inspection` is the frozen
    # grouped inspection (None on a non-HEALTHY read). Nothing outcome /
    # P&L / trade-linked is carried -- decision-time inspection only.
    ledger_health: Optional[IntegrationHealth] = None
    ledger_inspection: Optional[CandidateDecisionInspection] = None
    # Wave 3D (ADR-064, no scope expansion): the composition root also
    # attaches the count-only funnel aggregation derived from the same
    # inspection (`build_ledger_funnel_summary`). None on a non-HEALTHY
    # read, or in a standalone build with no provider. Factual counts
    # only -- no percentage, ratio, causal claim, outcome, or trade field.
    ledger_funnel_summary: Optional[LedgerFunnelSummary] = None

    @property
    def sections(self) -> Tuple[PerformanceLearningSection, ...]:
        """Fixed display order, matching the frozen IA's own section order."""
        return (
            self.outcome_history,
            self.attribution_breakdown,
            self.model_confidence_calibration,
        )

    @property
    def outcome_history_available(self) -> bool:
        """True only when a HEALTHY outcome read produced this screen. Rows
        may still be empty (HEALTHY, but no BUY decisions in the snapshot)."""
        return self.outcome_health is not None and self.outcome_health.is_healthy

    @property
    def outcome_history_is_empty(self) -> bool:
        return len(self.outcome_rows) == 0

    @property
    def outcome_history_empty_message(self) -> str:
        return _OUTCOME_HISTORY_EMPTY_MESSAGE

    @property
    def is_empty(self) -> bool:
        """True when no Outcome History table is shown -- either the source
        was non-HEALTHY (unavailable state) or it was HEALTHY with zero BUY
        decisions (empty state). Attribution and Model Confidence
        Calibration are always unavailable and never make this False."""
        return (not self.outcome_history_available) or self.outcome_history_is_empty

    # --- Wave 3C: Decision Ledger Inspection state (ADR-064 Section 2.11) ---

    @property
    def ledger_available(self) -> bool:
        """True only when a HEALTHY Wave 3B inspection produced this screen.
        The inspection may still be empty (HEALTHY, zero candidate rows)."""
        return self.ledger_health is not None and self.ledger_health.is_healthy

    @property
    def ledger_is_empty(self) -> bool:
        """True on a HEALTHY read that held no candidate rows."""
        inspection = self.ledger_inspection
        return inspection is None or inspection.is_empty

    @property
    def ledger_empty_message(self) -> str:
        return _LEDGER_EMPTY_MESSAGE

    @property
    def ledger_unavailable_fallback(self) -> str:
        return _LEDGER_UNAVAILABLE_FALLBACK

    @property
    def ledger_funnel_available(self) -> bool:
        """True when a factual funnel summary can be shown: a HEALTHY,
        non-empty inspection with its derived summary attached."""
        return (
            self.ledger_available
            and not self.ledger_is_empty
            and self.ledger_funnel_summary is not None
        )

    @property
    def empty_state_message(self) -> str:
        return "Performance & Learning has no wired data sources yet."
