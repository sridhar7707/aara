"""Decision Review workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes DecisionCard + ModelAgreement + ApprovalControls.
No auto-execute; every approval action is explicit.
"""

import gradio as gr

from sentinel.frontend.components import approval_controls, decision_card, model_agreement
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
