"""Sentinel settings (IMPLEMENTATION_HANDOFF.md: API Layer Technology Decision).

FastAPI unless implementation constraints require otherwise. No Flask,
Django, or Starlette introduced alongside it.
"""

from dataclasses import dataclass

from sentinel.backend.domain.user_context import DEFAULT_USER


@dataclass(frozen=True)
class Settings:
    default_user: str = DEFAULT_USER
    api_host: str = "127.0.0.1"
    api_port: int = 8000


def get_settings() -> Settings:
    raise NotImplementedError
