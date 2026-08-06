"""EvidenceCard component (SENTINEL_COMPONENT_CATALOG.md).

Structure only. Displays evidence provenance (provider, version,
data-as-of, recorded-at, confidence) -- role-based payload filtering
happens in the service layer, not here.
"""

import gradio as gr


def render(evidence_view: dict) -> gr.HTML:
    raise NotImplementedError
