"""Chain of Custody workspace (PHASE_2_UI_UX_REQUIREMENTS_FORMAL.md).

Structure only. Composes ChainTimeline + AuditFingerprint for a
decision's full lineage.
"""

import gradio as gr

from sentinel.frontend.components import audit_fingerprint, chain_timeline
from sentinel.frontend.services.api_client import SentinelApiClient


def build(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError
