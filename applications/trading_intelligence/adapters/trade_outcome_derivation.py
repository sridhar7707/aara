"""Pure BUY -> outcome derivation for the Wave 2A trades-only Decision
Outcome read model.

Every function here is deterministic and free of I/O -- no sqlite,
filesystem, network, clock, or randomness, and no bot / dashboard /
scheduler / database / ledger / sentinel_engine / sentinel import. Input
is the full list of BUY and ``SELL*`` rows from the ``trades`` table
(:class:`TradeOutcomeRow`); output is one :class:`DecisionOutcome` per
BUY plus a list of :class:`ExcludedSell` for ``SELL*`` rows that belong
to no decision.

Settled Wave 2A rules (trades-only):

* A BUY establishes a decision, identified ``"trade-<buy_id>"``.
* Each BUY owns a lifecycle window ``[BUY.timestamp, next BUY for the
  same symbol)`` -- half-open; the last BUY per symbol runs to
  +infinity. Only ``SELL*`` rows inside that window are candidates.
  Symbol-only matching is never performed, so re-entry is isolated by
  the window alone.
* Phantom reconcile suppression is STRUCTURAL: a ``SELL_RECONCILE`` row
  is suppressed when a later *valid bot fill* (``SELL_STOP`` /
  ``SELL_TIME_EXIT`` with a non-null ``order_id``) exists in the same
  window. No hard-coded trade id drives this.
* Quantity match uses an explicit epsilon
  ``max(QTY_EPSILON_FRAC * abs(buy.shares), QTY_EPSILON_ABS)``.
* Realized P&L / % / holding days are copied verbatim from the chosen
  ``SELL*`` row -- never recomputed.
* ``WIN`` / ``LOSS`` / ``FLAT`` is assigned for ``CLOSED`` only.
* An unknown / unsupported ``SELL*`` action, or a ``SELL_STOP`` /
  ``SELL_TIME_EXIT`` with a NULL ``order_id``, is never treated as a bot
  fill: it is left unattributable and surfaced via ``excluded_sells``.
"""
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Set, Tuple

from applications.trading_intelligence.contracts.decision_outcome_contract import (
    DecisionOutcome,
    ExcludedSell,
    ExcludedSellReason,
    ExitBasis,
    OutcomeDirection,
    OutcomeLineage,
    OutcomeStatus,
    PairingConfidence,
    PairingMethod,
)
from applications.trading_intelligence.projections.trade_outcome_row import (
    TradeOutcomeRow,
    decision_id_for,
)

QTY_EPSILON_FRAC = 0.01
QTY_EPSILON_ABS = 1e-6

_RECONCILE_ACTION = "SELL_RECONCILE"
_BOT_EXIT_ACTIONS = frozenset({"SELL_STOP", "SELL_TIME_EXIT"})

_REMAINING_QTY_NOTE = (
    "Remaining quantity after this partial exit is unaccounted; it is not "
    "derivable from the trades table alone."
)


def _sort_key(row: TradeOutcomeRow) -> Tuple[str, int]:
    return (row.timestamp, row.id)


def _in_window(ts: str, start: str, end: Optional[str]) -> bool:
    """Half-open ``[start, end)``; ``end is None`` means +infinity."""
    if ts < start:
        return False
    if end is not None and ts >= end:
        return False
    return True


def _valid_bot_fill(row: TradeOutcomeRow) -> bool:
    return row.action in _BOT_EXIT_ACTIONS and row.order_id is not None


def _exit_basis(row: TradeOutcomeRow) -> Optional[ExitBasis]:
    if _valid_bot_fill(row):
        return ExitBasis.BOT_FILL
    if row.action == _RECONCILE_ACTION:
        return ExitBasis.RECONCILIATION_MARK
    return None


def _direction(realized_pnl: Optional[float]) -> OutcomeDirection:
    if realized_pnl is None:
        return OutcomeDirection.FLAT
    if realized_pnl > 0:
        return OutcomeDirection.WIN
    if realized_pnl < 0:
        return OutcomeDirection.LOSS
    return OutcomeDirection.FLAT


def _epsilon_for(buy_shares: float) -> float:
    return max(QTY_EPSILON_FRAC * abs(buy_shares), QTY_EPSILON_ABS)


def _suppress_phantom_reconciles(
    candidates: List[TradeOutcomeRow],
) -> Tuple[List[TradeOutcomeRow], List[TradeOutcomeRow]]:
    """Return ``(suppressed, survivors)``.

    A ``SELL_RECONCILE`` row is suppressed iff a strictly-later valid bot
    fill exists among the same candidate set. The rule is purely
    structural -- it never consults a trade id.
    """
    suppressed: List[TradeOutcomeRow] = []
    survivors: List[TradeOutcomeRow] = []
    for row in candidates:
        if row.action == _RECONCILE_ACTION and any(
            _valid_bot_fill(other) and other.timestamp > row.timestamp
            for other in candidates
            if other.id != row.id
        ):
            suppressed.append(row)
        else:
            survivors.append(row)
    return suppressed, survivors


def _closed_or_partial(
    buy: TradeOutcomeRow,
    exit_row: TradeOutcomeRow,
    suppressed: List[TradeOutcomeRow],
    base: dict,
) -> DecisionOutcome:
    basis = _exit_basis(exit_row)
    buy_shares = buy.shares or 0.0
    matched = exit_row.shares or 0.0
    epsilon = _epsilon_for(buy_shares)
    full = abs(matched - buy_shares) <= epsilon
    some = (matched > epsilon) and not full

    exit_fields = dict(
        exit_basis=basis,
        exit_trade_id=exit_row.id,
        exit_timestamp=exit_row.timestamp,
        exit_price=exit_row.price,
        exit_shares=exit_row.shares,
        realized_pnl_usd=exit_row.realized_pnl,
        realized_pnl_pct=exit_row.pnl_pct,
        holding_days=exit_row.holding_days,
    )

    if full:
        if basis is ExitBasis.RECONCILIATION_MARK:
            method = PairingMethod.WINDOW_SINGLE_RECONCILE_MARK
            confidence = PairingConfidence.MEDIUM
        elif suppressed:
            method = PairingMethod.WINDOW_BOT_EXIT_AFTER_RECONCILE_SUPPRESSION
            confidence = PairingConfidence.MEDIUM
        else:
            method = PairingMethod.WINDOW_SINGLE_BOT_EXIT
            confidence = PairingConfidence.HIGH
        return DecisionOutcome(
            status=OutcomeStatus.CLOSED,
            pairing_method=method,
            pairing_confidence=confidence,
            outcome_direction=_direction(exit_row.realized_pnl),
            **exit_fields,
            **base,
        )

    if some:
        method = (
            PairingMethod.WINDOW_PARTIAL_RECONCILE_MARK
            if basis is ExitBasis.RECONCILIATION_MARK
            else PairingMethod.WINDOW_PARTIAL_BOT_EXIT
        )
        return DecisionOutcome(
            status=OutcomeStatus.PARTIAL,
            pairing_method=method,
            pairing_confidence=PairingConfidence.LOW,
            outcome_direction=None,
            remaining_qty_note=_REMAINING_QTY_NOTE,
            **exit_fields,
            **base,
        )

    # matched approximately zero -> the row is not an attributable exit.
    return DecisionOutcome(
        status=OutcomeStatus.OPEN,
        pairing_method=PairingMethod.NONE_OPEN,
        pairing_confidence=PairingConfidence.NONE,
        **base,
    )


def _classify_buy(
    buy: TradeOutcomeRow,
    survivors: List[TradeOutcomeRow],
    suppressed: List[TradeOutcomeRow],
    consumed: Set[int],
) -> DecisionOutcome:
    base = dict(
        decision_id=decision_id_for(buy.id),
        symbol=buy.symbol,
        entry_trade_id=buy.id,
        entry_timestamp=buy.timestamp,
        entry_price=buy.price,
        entry_shares=buy.shares,
        entry_ensemble_score=buy.ensemble_score,
        entry_regime=buy.regime,
        suppressed_reconcile_sell_ids=tuple(sorted(s.id for s in suppressed)),
    )

    resolvable = [s for s in survivors if _exit_basis(s) is not None]

    if not resolvable:
        return DecisionOutcome(
            status=OutcomeStatus.OPEN,
            pairing_method=PairingMethod.NONE_OPEN,
            pairing_confidence=PairingConfidence.NONE,
            **base,
        )

    if len(resolvable) >= 2:
        return DecisionOutcome(
            status=OutcomeStatus.AMBIGUOUS,
            pairing_method=PairingMethod.UNRESOLVED_MULTIPLE,
            pairing_confidence=PairingConfidence.NONE,
            candidate_sell_ids=tuple(sorted(s.id for s in resolvable)),
            **base,
        )

    exit_row = resolvable[0]
    outcome = _closed_or_partial(buy, exit_row, suppressed, base)
    if outcome.status in (OutcomeStatus.CLOSED, OutcomeStatus.PARTIAL):
        consumed.add(exit_row.id)
    return outcome


def _has_covering_window(
    sell: TradeOutcomeRow, sym_buys: List[TradeOutcomeRow]
) -> bool:
    for i, buy in enumerate(sym_buys):
        end = sym_buys[i + 1].timestamp if i + 1 < len(sym_buys) else None
        if _in_window(sell.timestamp, buy.timestamp, end):
            return True
    return False


def _collect_excluded(
    sells: List[TradeOutcomeRow],
    buys_by_symbol: Dict[str, List[TradeOutcomeRow]],
    consumed: Set[int],
    suppressed_ids: Set[int],
) -> List[ExcludedSell]:
    out: List[ExcludedSell] = []
    for sell in sells:
        if sell.id in consumed:
            continue
        if sell.id in suppressed_ids:
            reason = ExcludedSellReason.PHANTOM_RECONCILE_SUPPRESSED
        elif _has_covering_window(sell, buys_by_symbol.get(sell.symbol, [])):
            reason = ExcludedSellReason.UNATTRIBUTED_IN_WINDOW
        else:
            reason = ExcludedSellReason.ORPHAN_NO_BUY
        out.append(
            ExcludedSell(
                sell_trade_id=sell.id,
                symbol=sell.symbol,
                timestamp=sell.timestamp,
                action=sell.action,
                reason=reason,
            )
        )
    return out


def derive_outcomes(rows: Sequence[TradeOutcomeRow]) -> OutcomeLineage:
    """Pair every BUY to its trades-only realized outcome.

    Deterministic and order-independent: rows are sorted by
    ``(timestamp, id)`` internally, and the returned decisions are sorted
    by ``entry_trade_id``.
    """
    all_rows = list(rows)
    buys = sorted((r for r in all_rows if r.is_buy), key=_sort_key)
    sells = sorted((r for r in all_rows if r.is_sell), key=_sort_key)

    buys_by_symbol: Dict[str, List[TradeOutcomeRow]] = defaultdict(list)
    for buy in buys:
        buys_by_symbol[buy.symbol].append(buy)
    sells_by_symbol: Dict[str, List[TradeOutcomeRow]] = defaultdict(list)
    for sell in sells:
        sells_by_symbol[sell.symbol].append(sell)

    outcomes: List[DecisionOutcome] = []
    consumed: Set[int] = set()
    suppressed_ids: Set[int] = set()

    for symbol, sym_buys in buys_by_symbol.items():
        sym_sells = sells_by_symbol.get(symbol, [])
        for i, buy in enumerate(sym_buys):
            start = buy.timestamp
            end = sym_buys[i + 1].timestamp if i + 1 < len(sym_buys) else None
            candidates = [
                s
                for s in sym_sells
                if s.id not in consumed and _in_window(s.timestamp, start, end)
            ]
            suppressed, survivors = _suppress_phantom_reconciles(candidates)
            suppressed_ids.update(s.id for s in suppressed)
            outcomes.append(_classify_buy(buy, survivors, suppressed, consumed))

    excluded = _collect_excluded(sells, buys_by_symbol, consumed, suppressed_ids)
    outcomes.sort(key=lambda o: o.entry_trade_id)
    return OutcomeLineage(decisions=tuple(outcomes), excluded_sells=tuple(excluded))
