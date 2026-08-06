"""Tax Intelligence workspace (repository tree per IMPLEMENTATION_HANDOFF.md).

Structure only. No dedicated functional requirement section was found
for this workspace in PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md or
SENTINEL_PRODUCT_REQUIREMENTS_DOCUMENT.md's 7 core modules -- kept as
an empty composable workspace since it is named explicitly in the
handoff doc's frozen repository tree.
"""

import gradio as gr

from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
