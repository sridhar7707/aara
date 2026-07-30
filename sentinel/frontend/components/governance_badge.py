"""GovernanceBadge component (SENTINEL_COMPONENT_CATALOG.md).

Structure only -- no business logic. Displays governance status
(status, checks, policy_version) received from a projection view.
"""

import gradio as gr


def render(governance_view: dict) -> gr.HTML:
    raise NotImplementedError
