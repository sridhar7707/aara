"""Evidence Explorer workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes EvidenceCard list for a decision. Evidence is
immutable after recording; historical evidence available for
comparison.
"""

import gradio as gr

from sentinel.frontend.components import evidence_card
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
