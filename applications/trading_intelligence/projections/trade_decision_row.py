"""Typed, raw view of one ``trades`` table row from the bot's execution
history -- the "decision record" the Decision Center's trades.db-snapshot
path is built from.

Framework-independent: no bot, dashboard, scheduler, database, ledger, or
sentinel_engine import. This is a plain data-access shape produced by
adapters/trades_db_decision_source.py; it carries NO derivation -- the raw
``feature_drivers`` JSON string and ``ai_reasoning`` text pass through
untouched, and every model score stays exactly as stored (or ``None``).
Mapping this into DecisionContract / EvidenceEntry / GovernanceEntry /
AuditEntry is the separate, pure job of adapters/trade_decision_derivation.py.

The ``decision_id`` string scheme (``"trade-<id>"``) lives here as two
helpers so the data-access layer (id enumeration / lookup parsing) and the
derivation layer (DecisionContract.decision_id) share one definition
without either importing the other.
"""
from dataclasses import dataclass
from typing import Optional

_DECISION_ID_PREFIX = "trade-"


def decision_id_for(trade_id: int) -> str:
    """The stable Decision Center id for a ``trades.id`` primary key.

    ``trades.id`` is an ``INTEGER PRIMARY KEY AUTOINCREMENT`` (see
    bot/_main_db.py) -- monotonic and never reused -- so this mapping is
    stable across snapshot refreshes.
    """
    return f"{_DECISION_ID_PREFIX}{trade_id}"


def trade_id_from_decision_id(decision_id: str) -> Optional[int]:
    """Inverse of :func:`decision_id_for`. Returns ``None`` for any string
    that is not exactly ``"trade-<non-negative-int>"`` -- callers treat that
    as "no such decision" (a HEALTHY, empty read), never an error."""
    if not isinstance(decision_id, str) or not decision_id.startswith(_DECISION_ID_PREFIX):
        return None
    suffix = decision_id[len(_DECISION_ID_PREFIX):]
    if not suffix.isdigit():
        return None
    return int(suffix)


@dataclass(frozen=True)
class TradeDecisionRow:
    """One BUY row from ``trades``, columns copied verbatim.

    ``timestamp`` is the raw stored string (naive, UTC by the bot's
    convention) -- it is NOT parsed here. Every ``Optional[float]`` field is
    ``None`` when the column was ``NULL``; it is never coerced to ``0.0``.
    """

    trade_id: int
    timestamp: str
    symbol: str
    action: str
    ensemble_score: Optional[float]
    xgb_prob: Optional[float]
    lstm_prob: Optional[float]
    sentiment_score: Optional[float]
    macro_score: Optional[float]
    regime: Optional[str]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward_ratio: Optional[float]
    feature_drivers_raw: Optional[str]
    ai_reasoning: Optional[str]

    @property
    def decision_id(self) -> str:
        return decision_id_for(self.trade_id)
