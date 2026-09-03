"""Read-model types for the Wave 2A trades-only Decision Outcome layer.

Framework-independent, stdlib-only: no bot, dashboard, scheduler,
database, ledger, sentinel_engine, or sentinel import. These types are
what services/decision_outcome_query_service.py returns; nothing here
reads a database or performs pairing.

Wave 2A is deliberately trades-only. An outcome is derived from the
bot's ``trades`` rows alone -- one BUY row plus the ``SELL*`` row(s)
inside that BUY's lifecycle window. Where the exit is a
``SELL_RECONCILE`` row, the exit price, holding period, and realized
P&L it carries are a reconciliation *mark*, not an execution fill --
``exit_basis`` records which, and a consumer must not present a mark as
a fill.

``outcome_direction`` (WIN / LOSS / FLAT) is populated for ``CLOSED``
only; it is never assigned for ``PARTIAL``, ``AMBIGUOUS``, or ``OPEN``.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class OutcomeStatus(Enum):
    CLOSED = "closed"
    PARTIAL = "partial"
    OPEN = "open"
    AMBIGUOUS = "ambiguous"


class PairingMethod(Enum):
    WINDOW_SINGLE_BOT_EXIT = "window_single_bot_exit"
    WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION = (
        "window_bot_exit_after_reconcile_suppression"
    )
    WINDOW_SINGLE_RECONCILE_MARK = "window_single_reconcile_mark"
    WINDOW_PARTIAL_BOT_EXIT = "window_partial_bot_exit"
    WINDOW_PARTIAL_RECONCILE_MARK = "window_partial_reconcile_mark"
    NONE_OPEN = "none_open"
    UNRESOLVED_MULTIPLE = "unresolved_multiple"


class PairingConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ExitBasis(Enum):
    BOT_FILL = "bot_fill"
    RECONCILIATION_MARK = "reconciliation_mark"


class OutcomeDirection(Enum):
    WIN = "win"
    LOSS = "loss"
    FLAT = "flat"


class ExcludedSellReason(Enum):
    PHANTOM_RECONCILE_SUPPRESSED = "phantom_reconcile_suppressed"
    ORPHAN_NO_BUY = "orphan_no_buy"
    UNATTRIBUTED_IN_WINDOW = "unattributed_in_window"


@dataclass(frozen=True)
class DecisionOutcome:
    """One BUY decision plus its trades-only realized outcome.

    Every exit-side field is ``None`` unless ``status`` is ``CLOSED`` or
    ``PARTIAL`` and an exit was actually attributed.
    """

    decision_id: str
    symbol: str
    entry_trade_id: int
    entry_timestamp: str
    entry_price: Optional[float]
    entry_shares: Optional[float]
    status: OutcomeStatus
    pairing_method: PairingMethod
    pairing_confidence: PairingConfidence
    exit_basis: Optional[ExitBasis] = None
    exit_trade_id: Optional[int] = None
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    exit_shares: Optional[float] = None
    realized_pnl_usd: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    holding_days: Optional[int] = None
    outcome_direction: Optional[OutcomeDirection] = None
    entry_ensemble_score: Optional[float] = None
    entry_regime: Optional[str] = None
    suppressed_reconcile_sell_ids: Tuple[int, ...] = ()
    candidate_sell_ids: Tuple[int, ...] = ()
    remaining_qty_note: Optional[str] = None


@dataclass(frozen=True)
class ExcludedSell:
    """A ``SELL*`` row that belongs to no decision outcome."""

    sell_trade_id: int
    symbol: str
    timestamp: str
    action: str
    reason: ExcludedSellReason


@dataclass(frozen=True)
class OutcomeLineage:
    """The whole trades-only outcome projection: one entry per BUY, plus
    every unattributable / suppressed ``SELL*`` row."""

    decisions: Tuple[DecisionOutcome, ...] = ()
    excluded_sells: Tuple[ExcludedSell, ...] = ()
