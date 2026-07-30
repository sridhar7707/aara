"""RiskGovernorBadge component (SENTINEL_COMPONENT_CATALOG.md).

Displays current Risk Governor state. 3-state (NORMAL/WARNING/
DEFENSIVE) per the frozen enum in domain/enums.py -- do not add a
CRITICAL visual state here.
"""

import gradio as gr


def render(risk_state_view: dict) -> gr.HTML:
    raise NotImplementedError
