"""API client (GRADIO_IMPLEMENTATION_GUIDE.md: Callback Safety Rules).

Only path from Gradio to the backend. No SQLite imports, no direct
service imports, in Gradio code -- everything routes through here.
"""

from typing import Any


class SentinelApiClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def get_decision(self, decision_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_pending_decisions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_evidence(self, decision_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def approve_decision(self, decision_id: str, *, reason: str) -> dict[str, Any]:
        raise NotImplementedError

    def defer_decision(self, decision_id: str, *, reason: str) -> dict[str, Any]:
        raise NotImplementedError

    def decline_decision(self, decision_id: str, *, reason: str) -> dict[str, Any]:
        raise NotImplementedError

    def get_governance_state(self) -> dict[str, Any]:
        raise NotImplementedError

    def get_portfolio_health(self) -> dict[str, Any]:
        raise NotImplementedError
