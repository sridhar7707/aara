"""Gradio shell for the AARA Trading Intelligence Decision Center.

Thin rendering layer only: builds Gradio components, calls
DecisionCenterController methods, and maps the returned DecisionCenterScreen/
DecisionListArea/DecisionDetailArea into Gradio-friendly primitives (strings,
table rows). No repository, service, or event access -- only the controller,
per controller.py's own rule that DecisionCenterController is the only place
in ui/ allowed to call Trading Intelligence services. dashboard/'s existing
Gradio app is separate and ADR-002-protected; this package never imports it.

Known-decision-ids limitation: DecisionCenterController.load_decisions()
takes an explicit decision_ids list -- there is no "list all decisions"
capability anywhere in this read chain (documented, deliberate, not fixed
here; see decision_query_service.py's docstring). This UI is constructed
with the list of ids its composition root already knows about (the ones it
seeded) and refreshes against that same known list.

Row selection: gr.Dataframe's `select` event (Gradio 4.44) passes a
gr.SelectData whose `row_value` is the entire selected row as a 1-D list,
in the same column order as _LIST_HEADERS -- so row_value[0] is the
Decision ID without needing a second lookup against the rendered rows.

Evidence table: DecisionDetailArea.evidence carries plain EvidenceEntry
tuples (evidence_type/source/attached_at) -- this module does the same
List[List[str]] row formatting for them as it already does for the
Decisions list, keeping DecisionDetailArea itself Gradio-independent.
"""
from typing import List, Sequence, Tuple

import gradio as gr

from applications.trading_intelligence.projections.evidence_entry import EvidenceEntry
from applications.trading_intelligence.ui.decision_center.controller import DecisionCenterController
from applications.trading_intelligence.ui.decision_center.screen import (
    DecisionDetailArea,
    DecisionListArea,
)

_LIST_HEADERS = ["Decision ID", "Symbol", "Action", "Status", "Confidence"]
_EVIDENCE_HEADERS = ["Evidence Type", "Source", "Attached At"]
_MISSING_VALUE = "-"

_DetailValues = Tuple[str, str, str, str, str, List[List[str]]]


class DecisionCenterUI:
    def __init__(self, controller: DecisionCenterController, decision_ids: List[str]):
        self._controller = controller
        self._decision_ids = list(decision_ids)

    def build(self) -> gr.Blocks:
        with gr.Blocks(title="AARA Trading Intelligence — Decision Center") as demo:
            gr.Markdown("# Trading Intelligence — Decision Center")

            refresh_button = gr.Button("Refresh")
            list_output = gr.Dataframe(
                headers=_LIST_HEADERS, interactive=False, label="Decisions",
            )

            gr.Markdown("## Decision Detail")
            decision_id_input = gr.Textbox(label="Decision ID")
            view_button = gr.Button("View")
            symbol_output = gr.Textbox(label="Symbol", interactive=False)
            action_output = gr.Textbox(label="Action", interactive=False)
            status_output = gr.Textbox(label="Status", interactive=False)
            confidence_output = gr.Textbox(label="Confidence", interactive=False)
            updated_output = gr.Textbox(label="Last Updated", interactive=False)
            evidence_output = gr.Dataframe(
                headers=_EVIDENCE_HEADERS, interactive=False, label="Evidence",
            )

            detail_outputs = [
                symbol_output, action_output, status_output,
                confidence_output, updated_output, evidence_output,
            ]
            screen_outputs = [list_output] + detail_outputs

            refresh_button.click(fn=self._render_screen, inputs=None, outputs=screen_outputs)
            demo.load(fn=self._render_screen, inputs=None, outputs=screen_outputs)

            view_button.click(
                fn=self._render_detail, inputs=[decision_id_input], outputs=detail_outputs,
            )

            list_output.select(fn=self._on_row_select, inputs=None, outputs=detail_outputs)

        return demo

    def _render_screen(self) -> Tuple[List[List[str]], str, str, str, str, str, List[List[str]]]:
        screen = self._controller.load_screen(self._decision_ids)
        list_rows = self._format_list_rows(screen.list_area)
        detail_values = self._format_detail(screen.detail_area)
        return (list_rows,) + detail_values

    def _render_detail(self, decision_id: str) -> _DetailValues:
        if not decision_id:
            return self._empty_detail()
        detail_area = self._controller.load_decision_detail(decision_id)
        return self._format_detail(detail_area)

    def _on_row_select(self, evt: gr.SelectData) -> _DetailValues:
        if not evt.selected or not evt.row_value:
            return self._empty_detail()
        return self._render_detail(evt.row_value[0])

    @staticmethod
    def _format_list_rows(list_area: DecisionListArea) -> List[List[str]]:
        return [
            [
                view.decision_id,
                view.symbol,
                view.action,
                view.status.value.replace("_", " ").title(),
                f"{view.confidence * 100:.0f}%",
            ]
            for view in list_area.decisions
        ]

    @staticmethod
    def _format_detail(detail_area: DecisionDetailArea) -> _DetailValues:
        if detail_area.is_empty:
            return DecisionCenterUI._empty_detail()
        decision = detail_area.decision
        return (
            decision.symbol,
            decision.action,
            detail_area.status_display,
            detail_area.confidence_display,
            detail_area.timestamp_display,
            DecisionCenterUI._format_evidence_rows(detail_area.evidence),
        )

    @staticmethod
    def _format_evidence_rows(evidence: Sequence[EvidenceEntry]) -> List[List[str]]:
        return [
            [entry.evidence_type, entry.source, entry.attached_at.strftime("%Y-%m-%d %H:%M UTC")]
            for entry in evidence
        ]

    @staticmethod
    def _empty_detail() -> _DetailValues:
        return (
            _MISSING_VALUE, _MISSING_VALUE, _MISSING_VALUE,
            _MISSING_VALUE, _MISSING_VALUE, [],
        )
