"""Application settings — single source of truth, environment-driven.

pydantic-settings gives typed, validated config at startup: a typo'd
provider name or missing key fails fast at boot, not mid-request.
Injected via FastAPI dependency (see ``app/api/deps.py``) so tests can
override any value without monkeypatching globals.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.enums import LLMProvider, SearchProvider


class Settings(BaseSettings):
    """All runtime configuration. Every value overridable via environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM ---
    llm_provider: LLMProvider = LLMProvider.ANTHROPIC
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_temperature: float = Field(
        default=0.0, ge=0.0, le=1.0, description="0.0 for determinism; never raised in production triage."
    )
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    # --- Search ---
    search_provider: SearchProvider = SearchProvider.DUCKDUCKGO
    tavily_api_key: str = ""
    # MCP search server (SEARCH_PROVIDER=mcp): any MCP server exposing a
    # search-like tool works — the graph only ever sees the SearchTool interface.
    mcp_server_url: str = ""
    mcp_search_tool_name: str = "search"
    search_max_results: int = Field(default=4, ge=1, le=10)
    search_min_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    search_timeout_seconds: float = Field(default=10.0, gt=0)

    # --- Retry policy (exponential backoff: base * 2**attempt) ---
    max_retries: int = Field(default=3, ge=0, le=5)
    retry_base_delay_seconds: float = Field(default=0.5, gt=0)

    # --- Persistence (SQLite default; Postgres: postgresql+asyncpg://user:pass@host/db) ---
    database_url: str = "sqlite+aiosqlite:///./triage.db"

    # --- Auth: "none" (open), "api_key" (X-API-Key header), "clerk" (Bearer JWT) ---
    auth_mode: str = Field(default="none", pattern="^(none|api_key|clerk)$")
    api_keys: str = Field(default="", description="Comma-separated accepted keys for auth_mode=api_key.")
    clerk_publishable_key: str = Field(default="", description="pk_... for the web UI Clerk widget.")
    clerk_secret_key: str = Field(default="", description="sk_... optional; not used for JWT verification.")
    clerk_jwks_url: str = Field(
        default="", description="e.g. https://<slug>.clerk.accounts.dev/.well-known/jwks.json"
    )
    clerk_issuer: str = Field(default="", description="e.g. https://<slug>.clerk.accounts.dev")

    @property
    def clerk_jwks_url_resolved(self) -> str:
        """JWKS URL from env or derived from CLERK_ISSUER."""
        if self.clerk_jwks_url.strip():
            return self.clerk_jwks_url.strip()
        issuer = self.clerk_issuer.strip().rstrip("/")
        if issuer:
            return f"{issuer}/.well-known/jwks.json"
        return ""

    @property
    def clerk_configured(self) -> bool:
        """True when Clerk auth can verify JWTs and the UI can load."""
        return bool(self.clerk_publishable_key.strip() and self.clerk_jwks_url_resolved)

    # --- Rate limiting (per client IP on triage endpoints; 0 disables) ---
    rate_limit_per_minute: int = Field(default=0, ge=0)

    # --- Cost estimation (USD per 1M tokens; 0.0 for free tiers) ---
    cost_per_1m_prompt_tokens: float = Field(default=0.0, ge=0.0)
    cost_per_1m_completion_tokens: float = Field(default=0.0, ge=0.0)

    # --- App ---
    app_env: str = "dev"
    log_level: str = "INFO"
    debug_endpoint_enabled: bool = True
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
        description="Comma-separated origins for the Next.js frontend.",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Cleared in tests via ``get_settings.cache_clear()``."""
    return Settings()
