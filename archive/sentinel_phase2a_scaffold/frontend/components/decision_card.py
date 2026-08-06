"""DecisionCard component (SENTINEL_COMPONENT_CATALOG.md).

Structure only. Renders a Decision projection view (asset, action,
thesis, status) -- never raw ledger state.
"""

import gradio as gr


def render(decision_view: dict) -> gr.HTML:
    raise NotImplementedError
