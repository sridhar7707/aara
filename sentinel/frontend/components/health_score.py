"""HealthScore component (SENTINEL_COMPONENT_CATALOG.md).

Structure only. Renders the pre-calculated portfolio health score from
portfolio_health_projection.py -- no calculation in Gradio.
"""

import gradio as gr


def render(portfolio_health_view: dict) -> gr.HTML:
    raise NotImplementedError
