"""ModelAgreement component (SENTINEL_COMPONENT_CATALOG.md).

Structure only. Displays evidence/model agreement summary. Confidence
intervals, never certainty language (IMPLEMENTATION_HANDOFF.md:
Evidence > Predictions).
"""

import gradio as gr


def render(evidence_assessment_view: dict) -> gr.HTML:
    raise NotImplementedError
