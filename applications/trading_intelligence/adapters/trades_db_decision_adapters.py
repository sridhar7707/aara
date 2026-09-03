"""The Decision Center read-side sources for the trades.db-snapshot path.

Each class composes the raw data-access reader
(:class:`TradesDbDecisionReader`, Task 1A) with the pure derivation
functions (``trade_decision_derivation``, Task 1B) behind an EXISTING
read-side contract, so nothing above the adapter layer --
``DecisionQueryService`` / ``DecisionEvidenceQueryService`` /
``DecisionGovernanceQueryService`` / ``DecisionCenterController`` /
``screen.py`` / ``gradio_view.py`` -- changes:

* :class:`TradesDbDecisionSource`      -> ``DecisionSource``
* :class:`TradesDbEvidenceSource`      -> ``EvidenceSource``
* :class:`TradesDbGovernanceSource`    -> ``GovernanceSource``
* :class:`TradesDbAuditSource`         -> duck-typed ``get_audit_trail``
  (a plain class, mirroring ``SentinelAuditSource`` -- the controller holds
  the audit source directly, no ``services/`` wrapper).

Error translation: the reader returns an ADR-061 ``ReadResult``. A
non-HEALTHY result becomes a :class:`TradingIntelligenceReadError` for the
Detail-panel reads (``get_decision`` / evidence / governance / approvals /
audit) -- the controller already catches that type per concern and reports
``ReadStatus.ERROR``. ``list_decisions`` deliberately does NOT translate:
it mirrors ``SentinelProjectionDecisionSource.list_decisions`` (list-path
read-error semantics are out of scope) and simply yields ``[]`` on a
non-HEALTHY read, so the Decision list falls back to its existing
"No decisions recorded yet." empty state.

A derivation-level failure (an unparseable ``trades.timestamp``) raises
``TradingIntelligenceReadError`` from within these methods for the same
reason -- a decision with no valid instant must not be shown with a
fabricated one.

Read-only, additive, no write path, no import of
bot/dashboard/scheduler/database/ledger/sentinel_engine.
"""
from typing import List, Optional

from applications.trading_intelligence.adapters import trade_decision_derivation as _derive
from applications.trading_intelligence.adapters.trades_db_decision_source import (
    TradesDbDecisionReader,
)
from applications.trading_intelligence.contracts.decision_contract import DecisionContract
from applications.trading_intelligence.contracts.read_error import TradingIntelligenceReadError
from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry
from applications.trading_intelligence.projections.trade_decision_row import TradeDecisionRow
from applications.trading_intelligence.services.decision_evidence_query_service import EvidenceSource
from applications.trading_intelligence.services.decision_governance_query_service import (
    GovernanceSource,
)
from applications.trading_intelligence.services.decision_query_service import DecisionSource


def _row_or_raise(
    reader: TradesDbDecisionReader, decision_id: str
) -> Optional[TradeDecisionRow]:
    """One BUY row, or ``None`` for a genuinely absent/unknown id. A
    non-HEALTHY read is a :class:`TradingIntelligenceReadError`."""
    result = reader.get_row(decision_id)
    if not result.health.is_healthy:
        raise TradingIntelligenceReadError(
            f"trades.db decision read failed for {decision_id!r}: "
            f"{result.health.status.name}"
        )
    return result.value


class TradesDbDecisionSource(DecisionSource):
    def __init__(self, reader: TradesDbDecisionReader):
        self._reader = reader

    def get_decision(self, decision_id: str) -> Optional[DecisionContract]:
        row = _row_or_raise(self._reader, decision_id)
        if row is None:
            return None
        return _derive.to_decision_contract(row)

    def list_decisions(self, decision_ids: List[str]) -> List[DecisionContract]:
        result = self._reader.list_rows(decision_ids)
        if not result.health.is_healthy or result.value is None:
            return []
        return [_derive.to_decision_contract(row) for row in result.value]


class TradesDbEvidenceSource(EvidenceSource):
    def __init__(self, reader: TradesDbDecisionReader):
        self._reader = reader

    def get_evidence(self, decision_id: str) -> List[EvidenceEntry]:
        row = _row_or_raise(self._reader, decision_id)
        if row is None:
            return []
        return _derive.to_evidence_entries(row)


class TradesDbGovernanceSource(GovernanceSource):
    def __init__(self, reader: TradesDbDecisionReader):
        self._reader = reader

    def get_governance(self, decision_id: str) -> List[GovernanceEntry]:
        row = _row_or_raise(self._reader, decision_id)
        if row is None:
            return []
        return _derive.to_governance_entries(row)

    def get_approvals(self, decision_id: str) -> List[ApprovalEntry]:
        row = _row_or_raise(self._reader, decision_id)
        if row is None:
            return []
        return _derive.to_approvals(row)


class TradesDbAuditSource:
    """Plain class, not an ABC subclass -- mirrors ``SentinelAuditSource``;
    the controller holds the audit source directly."""

    def __init__(self, reader: TradesDbDecisionReader):
        self._reader = reader

    def get_audit_trail(self, decision_id: str) -> List[AuditEntry]:
        row = _row_or_raise(self._reader, decision_id)
        if row is None:
            return []
        return _derive.to_audit_entries(row)
