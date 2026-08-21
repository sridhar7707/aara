"""Decision Center screen structure -- V1 prototype.

No rendering framework: this project has no frontend toolchain wired into
applications/trading_intelligence/ (dashboard/'s Gradio app is separate and
protected). Screen areas are plain, framework-independent dataclasses,
testable the same way DecisionView/DecisionContract already are, per
docs/products/AARA_TRADING_INTELLIGENCE_DECISION_CENTER_DESIGN.md's layout
(Section 4). No sentinel_engine, bot, dashboard, database, or ledger import.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from applications.trading_intelligence.projections.approval_entry import ApprovalEntry
from applications.trading_intelligence.projections.audit_entry import AuditEntry
from applications.trading_intelligence.projections.decision_view import DecisionView
from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.projections.governance_entry import GovernanceEntry


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
        return self.decision.updated_at.strftime("%Y-%m-%d %H:%M UTC")


@dataclass(frozen=True)
class DecisionCenterScreen:
    list_area: DecisionListArea
    detail_area: DecisionDetailArea
