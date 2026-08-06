"""Governance Review workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes GovernanceBadge + ApprovalControls for
escalated/CRO-level review (DEFENSIVE state decisions).
"""

import gradio as gr

from sentinel.frontend.components import approval_controls, governance_badge
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
