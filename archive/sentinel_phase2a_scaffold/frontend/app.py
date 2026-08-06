"""Sentinel Gradio application entry point (GRADIO_IMPLEMENTATION_GUIDE.md).

Structure only. Composes the 9 workspaces into tabs. Gradio is the
only frontend framework -- no React/Vue/Angular. CSS variables carry
design system tokens (styles/theme.css).
"""

import gradio as gr

from sentinel.frontend.services.api_client import SentinelApiClient
from sentinel.frontend.workspaces import (
    chain_of_custody,
    decision_history,
    decision_quality,
    decision_review,
    evidence_explorer,
    governance_review,
    governance_status,
    portfolio_health,
    tax_intelligence,
)


def build_app(api_client: SentinelApiClient) -> gr.Blocks:
    raise NotImplementedError


if __name__ == "__main__":
    raise NotImplementedError
