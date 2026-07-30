"""ApprovalControls component (SENTINEL_COMPONENT_CATALOG.md).

Structure only. Approve/Defer/Decline/Escalate buttons. Permission
checks happen at the API layer, not here (GRADIO_IMPLEMENTATION_GUIDE.md:
Gradio Must NOT evaluate approval permissions).
"""

import gradio as gr

from sentinel.frontend.services.api_client import SentinelApiClient


def render(decision_id: str, api_client: SentinelApiClient) -> gr.Row:
    raise NotImplementedError
