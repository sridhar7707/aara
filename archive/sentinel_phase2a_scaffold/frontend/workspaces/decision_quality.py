"""Decision Quality workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Displays decision process quality (governance
adherence, evidence, process) -- tracked independently from investment
outcome per IMPLEMENTATION_HANDOFF.md principle 6.
"""

import gradio as gr

from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
