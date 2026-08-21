"""Decision Center screen structure -- V1 prototype.

No rendering framework: this project has no frontend toolchain wired into
applications/trading_intelligence/ (dashboard/'s Gradio app is separate and
protected). Screen areas are plain, framework-independent dataclasses,
testable the same way DecisionView/DecisionContract already are, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md's layout
(Section 4). No sentinel_engine, bot, dashboard, database, or ledger import.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry

# P1 UI-only timestamp fix (GOOGL/dec-seed-004 timestamp audit): every
# timestamp this application stores or reads -- Decision.timestamp,
# Evidence.collected_at, Approval.timestamp, and GovernanceService's own
# internal datetime.utcnow() stamp -- is a naive datetime whose implicit
# meaning is UTC; there is no tz-aware datetime anywhere in the read chain
# (sentinel_engine/projections/decision_projection.py through
# DecisionContract/DecisionView all carry naive datetimes unchanged). This
# converts that naive-UTC value to America/Chicago for display only, DST-
# aware (CST/CDT) via the stdlib zoneinfo module -- it does not touch the
# stored value, sort order (callers still sort/compare the original naive
# datetime), or any sentinel_engine/contracts/projections code. Both
# gradio_view.py and this module's own timestamp_display below call this
# one function so every Decision Center timestamp (list, detail header,
# Evidence, Governance, Approval, Audit Trail) converts identically.
_DISPLAY_TIMEZONE = ZoneInfo("America/Chicago")
_NAIVE_SOURCE_TIMEZONE = ZoneInfo("UTC")


def format_display_timestamp(moment: datetime) -> str:
    """Formats a naive-but-UTC datetime for display in America/Chicago,
    e.g. "2026-08-21 14:45 CDT" (summer) or "2026-01-08 09:40 CST"
    (winter) -- %Z renders whichever abbreviation applies via zoneinfo's
    own DST rules, never a fixed offset."""
    aware = moment.replace(tzinfo=_NAIVE_SOURCE_TIMEZONE)
    return aware.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M %Z")


class ReadStatus(Enum):
    """Distinguishes a successful read (possibly empty) from a read that
    could not be completed. AVAILABLE-vs-EMPTY is never ambiguous here --
    an empty tuple already means that -- so this only needs two members,
    not a three-way split."""
    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True)
class DecisionListArea:
    decisions: List[DecisionView]

    @property
    def is_empty(self) -> bool:
        return len(self.decisions) == 0

    @property
    def empty_state_message(self) -> Optional[str]:
        return "No decisions recorded yet." if self.is_empty else None


@dataclass(frozen=True)
class DecisionDetailArea:
    decision: Optional[DecisionView]
    decision_status: ReadStatus = ReadStatus.OK
    # Raw, opaque, unresolved pointer values from DecisionContract -- not
    # part of DecisionView (which deliberately excludes them). Displayed
    # verbatim in the detail header; never interpreted, resolved, or
    # validated here.
    evidence_reference: Optional[str] = None
    risk_reference: Optional[str] = None
    evidence: Tuple[EvidenceEntry, ...] = field(default=())
    evidence_status: ReadStatus = ReadStatus.OK
    governance: Tuple[GovernanceEntry, ...] = field(default=())
    governance_status: ReadStatus = ReadStatus.OK
    approvals: Tuple[ApprovalEntry, ...] = field(default=())
    approvals_status: ReadStatus = ReadStatus.OK
    audit_trail: Tuple[AuditEntry, ...] = field(default=())
    audit_trail_status: ReadStatus = ReadStatus.OK

    @property
    def is_empty(self) -> bool:
        return self.decision is None

    @property
    def confidence_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return f"{self.decision.confidence * 100:.0f}%"

    @property
    def status_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return self.decision.status.replace("_", " ").title()

    @property
    def timestamp_display(self) -> Optional[str]:
        if self.decision is None:
            return None
        return format_display_timestamp(self.decision.updated_at)


@dataclass(frozen=True)
class DecisionCenterScreen:
    list_area: DecisionListArea
    detail_area: DecisionDetailArea
