"""Governance Status workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes GovernanceBadge + RiskGovernorBadge. Callbacks
delegate to the API client; no business logic here.
"""

import gradio as gr

from sentinel.frontend.components import governance_badge, risk_governor_badge
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
