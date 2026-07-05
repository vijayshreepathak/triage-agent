"""Public runtime config for the web UI (no secrets)."""

from __future__ import annotations

from pydantic import BaseModel


class AppConfigResponse(BaseModel):
    """GET /config — everything the frontend needs to boot."""

    app_name: str = "Stance Triage"
    auth_mode: str
    clerk_publishable_key: str = ""
    clerk_configured: bool = False
    search_provider: str
    llm_provider: str
    debug_enabled: bool
