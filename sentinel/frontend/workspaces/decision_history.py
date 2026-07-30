"""Decision History workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes DecisionCard list for CLOSED/REVIEWED
decisions -- read-only, derived projection views.
"""

import gradio as gr

from sentinel.frontend.components import decision_card
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
