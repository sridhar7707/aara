"""Portfolio Health workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes HealthScore. Phase 2A: mock/simulated
portfolio data only.
"""

import gradio as gr

from sentinel.frontend.components import health_score
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
