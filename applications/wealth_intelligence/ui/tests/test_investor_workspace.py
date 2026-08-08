"""Tests for applications.wealth_intelligence.ui.investor_workspace.InvestorWorkspaceUI.

Covers construction with a fake InvestorPresenter, that Gradio callbacks
delegate to presenter methods only (view models in, primitives out), and a
structural AST scan proving the ui/ package never imports repositories,
services, events, dashboard, bot, or database modules -- mirroring the
import-boundary test already established in
applications/trading_intelligence/ui/tests/test_ui_structure.py.
"""
import ast
import datetime
import importlib
import pathlib

import gradio as gr

from applications.wealth_intelligence.ui.investor_workspace import InvestorWorkspaceUI
from sentinel_engine.domain.decision_state import DecisionState
from sentinel_engine.governance.approval_status import ApprovalStatus
from sentinel_engine.presentation.investor_presenter import (
    ApprovalSummaryRow,
    DecisionCenterViewModel,
    EvidenceRow,
    GovernanceSummaryRow,
    MorningBriefView,
    RecentActivityRow,
    TimelineRow,
)

_UI_ROOT = pathlib.Path(__file__).resolve().parent.parent


class _FakePresenter:
    def __init__(self, morning_brief_view=None, decision_center_view=None):
        self._morning_brief_view = morning_brief_view
        self._decision_center_view = decision_center_view
        self.morning_brief_calls = 0
        self.received_decision_id = None

    def get_morning_brief_view(self):
        self.morning_brief_calls += 1
        return self._morning_brief_view

    def get_decision_center_view(self, decision_id):
        self.received_decision_id = decision_id
        return self._decision_center_view


def _make_morning_brief_view():
    return MorningBriefView(
        total_decisions=2,
        status_summary={DecisionState.DECISION_CREATED: 1, DecisionState.APPROVAL_RECORDED: 1},
        recent_activity_rows=[
            RecentActivityRow(
                decision_id="dec-001",
                status=DecisionState.APPROVAL_RECORDED,
                last_activity_at=datetime.datetime(2026, 8, 6, 12, 3, 0),
            )
        ],
    )


def _make_decision_center_view():
    return DecisionCenterViewModel(
        decision_id="dec-001",
        lifecycle_status=DecisionState.APPROVAL_RECORDED,
        symbol="AAPL",
        action="BUY",
        evidence_rows=[
            EvidenceRow(
                evidence_id="ev-001",
                evidence_type="NEWS_SENTIMENT",
                source="newsapi",
                attached_at=datetime.datetime(2026, 8, 6, 12, 1, 0),
            )
        ],
        governance_summary=GovernanceSummaryRow(
            policy_id="pol-001",
            enabled=True,
            evaluated_at=datetime.datetime(2026, 8, 6, 12, 2, 0),
        ),
        approval_summary=ApprovalSummaryRow(
            approval_id="apr-001",
            status=ApprovalStatus.APPROVED,
            approved_by="risk_officer",
            approved_at=datetime.datetime(2026, 8, 6, 12, 3, 0),
        ),
        timeline_rows=[
            TimelineRow(event_type="DECISION_CREATED", created_at=datetime.datetime(2026, 8, 6, 12, 0, 0)),
            TimelineRow(event_type="APPROVAL_RECORDED", created_at=datetime.datetime(2026, 8, 6, 12, 3, 0)),
        ],
    )


def test_investor_workspace_ui_can_be_constructed_with_fake_presenter():
    presenter = _FakePresenter()

    ui = InvestorWorkspaceUI(presenter)
    demo = ui.build()

    assert isinstance(demo, gr.Blocks)


def test_render_morning_brief_calls_presenter_and_maps_view_model():
    presenter = _FakePresenter(morning_brief_view=_make_morning_brief_view())
    ui = InvestorWorkspaceUI(presenter)

    total_decisions_text, status_summary_rows, recent_activity_rows = ui._render_morning_brief()

    assert presenter.morning_brief_calls == 1
    assert total_decisions_text == "2"
    assert ["DECISION_CREATED", "1"] in status_summary_rows
    assert ["APPROVAL_RECORDED", "1"] in status_summary_rows
    assert recent_activity_rows == [["dec-001", "APPROVAL_RECORDED", "2026-08-06T12:03:00"]]


def test_render_decision_center_passes_decision_id_and_maps_view_model():
    presenter = _FakePresenter(decision_center_view=_make_decision_center_view())
    ui = InvestorWorkspaceUI(presenter)

    (
        lifecycle_status,
        symbol,
        action,
        evidence_rows,
        governance_text,
        approval_text,
        timeline_rows,
    ) = ui._render_decision_center("dec-001")

    assert presenter.received_decision_id == "dec-001"
    assert lifecycle_status == "APPROVAL_RECORDED"
    assert symbol == "AAPL"
    assert action == "BUY"
    assert evidence_rows == [["ev-001", "NEWS_SENTIMENT", "newsapi", "2026-08-06T12:01:00"]]
    assert governance_text == "Policy pol-001: enabled (evaluated 2026-08-06T12:02:00)"
    assert approval_text == "APPROVED by risk_officer (recorded 2026-08-06T12:03:00)"
    assert timeline_rows == [
        ["DECISION_CREATED", "2026-08-06T12:00:00"],
        ["APPROVAL_RECORDED", "2026-08-06T12:03:00"],
    ]


def test_render_decision_center_renders_plain_strings_through_gradio_textbox():
    """Regression test for a real bug: DecisionState/ApprovalStatus are
    (str, Enum) members whose __str__ (all Python versions) and __format__
    (3.12+) render as "DecisionState.APPROVAL_RECORDED" /
    "ApprovalStatus.APPROVED" instead of the bare value. The handler-return
    `==` assertions above pass regardless of this bug (enum `==` compares
    equal to the plain string), so they cannot catch it -- this test
    exercises gr.Textbox's actual postprocess() (which calls str() on the
    value) for the lifecycle status, and checks the approval-summary text
    for the literal class-qualification artifact that a raw f-string
    embedding of the enum (without .value) would produce.
    """
    presenter = _FakePresenter(decision_center_view=_make_decision_center_view())
    ui = InvestorWorkspaceUI(presenter)

    lifecycle_status, _, _, _, _, approval_text, _ = ui._render_decision_center("dec-001")

    rendered_lifecycle_status = gr.Textbox().postprocess(lifecycle_status)
    assert rendered_lifecycle_status == "APPROVAL_RECORDED"
    assert "DecisionState." not in rendered_lifecycle_status

    assert isinstance(approval_text, str)
    assert "ApprovalStatus." not in approval_text
    assert "DecisionState." not in approval_text
    assert approval_text == "APPROVED by risk_officer (recorded 2026-08-06T12:03:00)"


def test_render_decision_center_handles_missing_decision_gracefully():
    presenter = _FakePresenter(decision_center_view=None)
    ui = InvestorWorkspaceUI(presenter)

    result = ui._render_decision_center("missing-decision")

    assert presenter.received_decision_id == "missing-decision"
    assert result[0] == "No decision found for 'missing-decision'."
    assert result[3] == []
    assert result[6] == []


def test_render_decision_center_handles_blank_decision_id_without_calling_presenter():
    presenter = _FakePresenter(decision_center_view=_make_decision_center_view())
    ui = InvestorWorkspaceUI(presenter)

    result = ui._render_decision_center("")

    assert presenter.received_decision_id is None
    assert result[0] == "Enter a decision ID."


def test_ui_package_imports_cleanly():
    importlib.import_module("applications.wealth_intelligence")
    importlib.import_module("applications.wealth_intelligence.ui")
    importlib.import_module("applications.wealth_intelligence.ui.investor_workspace")


def test_ui_does_not_import_repositories_services_events_dashboard_bot_or_database():
    forbidden_prefixes = (
        "sentinel_engine.repositories",
        "sentinel_engine.services",
        "sentinel_engine.events",
        "dashboard",
        "bot",
        "database",
    )
    py_files = [
        path
        for path in _UI_ROOT.rglob("*.py")
        if "tests" not in path.relative_to(_UI_ROOT).parts
        and "__pycache__" not in path.parts
    ]
    assert py_files, "expected at least one production .py file under applications/wealth_intelligence/ui/"

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"{path}: forbidden import {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), (
                    f"{path}: forbidden import from {module!r}"
                )
