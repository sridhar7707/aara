"""Gradio shell for the AARA Wealth Intelligence investor workspace.

Thin rendering layer only: builds Gradio components, calls
InvestorPresenter methods, and maps the returned view models into
Gradio-friendly primitives (strings, table rows). No repository, service,
or event access -- dashboard/'s existing Gradio app is separate and
ADR-002-protected, and this package never imports it.
"""
from typing import List, Optional, Tuple

import gradio as gr

from applications.wealth_intelligence.presentation.investor_presenter import (
    ApprovalSummaryRow,
    GovernanceSummaryRow,
    InvestorPresenter,
)

_MORNING_BRIEF_STATUS_HEADERS = ["Status", "Count"]
_MORNING_BRIEF_ACTIVITY_HEADERS = ["Decision ID", "Status", "Last Activity"]
_EVIDENCE_HEADERS = ["Evidence ID", "Type", "Source", "Attached At"]
_TIMELINE_HEADERS = ["Event", "Timestamp"]

_NOT_YET_EVALUATED = "Not yet evaluated."
_NOT_YET_APPROVED = "Not yet recorded."
_MISSING_VALUE = "—"


class InvestorWorkspaceUI:
    def __init__(self, presenter: InvestorPresenter):
        self._presenter = presenter

    def build(self) -> gr.Blocks:
        with gr.Blocks(title="AARA Wealth Intelligence — Investor Workspace") as demo:
            gr.Markdown("# Investor Workspace")

            with gr.Tab("Morning Brief"):
                refresh_button = gr.Button("Refresh")
                total_decisions_output = gr.Textbox(label="Total Decisions", interactive=False)
                status_summary_output = gr.Dataframe(
                    headers=_MORNING_BRIEF_STATUS_HEADERS, interactive=False, label="Status Summary",
                )
                recent_activity_output = gr.Dataframe(
                    headers=_MORNING_BRIEF_ACTIVITY_HEADERS, interactive=False, label="Recent Activity",
                )

                morning_brief_outputs = [
                    total_decisions_output,
                    status_summary_output,
                    recent_activity_output,
                ]
                refresh_button.click(
                    fn=self._render_morning_brief, inputs=None, outputs=morning_brief_outputs,
                )
                demo.load(fn=self._render_morning_brief, inputs=None, outputs=morning_brief_outputs)

            with gr.Tab("Decision Center"):
                decision_id_input = gr.Textbox(label="Decision ID")
                load_button = gr.Button("Load")
                lifecycle_status_output = gr.Textbox(label="Lifecycle Status", interactive=False)
                symbol_output = gr.Textbox(label="Symbol", interactive=False)
                action_output = gr.Textbox(label="Action", interactive=False)
                evidence_output = gr.Dataframe(
                    headers=_EVIDENCE_HEADERS, interactive=False, label="Evidence",
                )
                governance_output = gr.Textbox(label="Governance", interactive=False)
                approval_output = gr.Textbox(label="Approval", interactive=False)
                timeline_output = gr.Dataframe(
                    headers=_TIMELINE_HEADERS, interactive=False, label="Timeline",
                )

                decision_center_outputs = [
                    lifecycle_status_output,
                    symbol_output,
                    action_output,
                    evidence_output,
                    governance_output,
                    approval_output,
                    timeline_output,
                ]
                load_button.click(
                    fn=self._render_decision_center,
                    inputs=[decision_id_input],
                    outputs=decision_center_outputs,
                )

        return demo

    def _render_morning_brief(self) -> Tuple[str, List[List[str]], List[List[str]]]:
        view = self._presenter.get_morning_brief_view()

        total_decisions_text = str(view.total_decisions)
        status_summary_rows = [
            [status, str(count)] for status, count in view.status_summary.items()
        ]
        recent_activity_rows = [
            [row.decision_id, row.status, row.last_activity_at.isoformat()]
            for row in view.recent_activity_rows
        ]

        return total_decisions_text, status_summary_rows, recent_activity_rows

    def _render_decision_center(
        self, decision_id: str,
    ) -> Tuple[str, str, str, List[List[str]], str, str, List[List[str]]]:
        empty_evidence: List[List[str]] = []
        empty_timeline: List[List[str]] = []

        if not decision_id:
            return (
                "Enter a decision ID.", _MISSING_VALUE, _MISSING_VALUE,
                empty_evidence, _NOT_YET_EVALUATED, _NOT_YET_APPROVED, empty_timeline,
            )

        view = self._presenter.get_decision_center_view(decision_id)
        if view is None:
            return (
                f"No decision found for '{decision_id}'.", _MISSING_VALUE, _MISSING_VALUE,
                empty_evidence, _NOT_YET_EVALUATED, _NOT_YET_APPROVED, empty_timeline,
            )

        evidence_rows = [
            [row.evidence_id, row.evidence_type, row.source, row.attached_at.isoformat()]
            for row in view.evidence_rows
        ]
        timeline_rows = [
            [row.event_type, row.created_at.isoformat()] for row in view.timeline_rows
        ]

        return (
            view.lifecycle_status.value,
            view.symbol or _MISSING_VALUE,
            view.action or _MISSING_VALUE,
            evidence_rows,
            self._format_governance_summary(view.governance_summary),
            self._format_approval_summary(view.approval_summary),
            timeline_rows,
        )

    @staticmethod
    def _format_governance_summary(governance_summary: Optional[GovernanceSummaryRow]) -> str:
        if governance_summary is None:
            return _NOT_YET_EVALUATED
        return (
            f"Policy {governance_summary.policy_id}: "
            f"{'enabled' if governance_summary.enabled else 'disabled'} "
            f"(evaluated {governance_summary.evaluated_at.isoformat()})"
        )

    @staticmethod
    def _format_approval_summary(approval_summary: Optional[ApprovalSummaryRow]) -> str:
        if approval_summary is None:
            return _NOT_YET_APPROVED
        return (
            f"{approval_summary.status.value} by {approval_summary.approved_by} "
            f"(recorded {approval_summary.approved_at.isoformat()})"
        )
