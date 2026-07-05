"""Tool contracts — the only thing nodes are allowed to depend on.

Nodes receive these Protocols via dependency injection and never import a
concrete provider. Swapping Groq for OpenRouter, or DuckDuckGo for Tavily,
or either for an MCP server later, is a change in the composition root
(``app/api``), not in any node or graph file.

``runtime_checkable`` so tests can assert fakes satisfy the contract.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.models.clinical import SearchResult


class LLMResult(BaseModel):
    """One LLM completion plus usage metadata for metrics/cost tracking."""

    model_config = ConfigDict(frozen=True)

    content: str
    model: str = ""
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)


@runtime_checkable
class LLMClient(Protocol):
    """Minimal completion contract. Temperature/model are the provider's concern."""

    async def complete(self, *, system: str, user: str) -> LLMResult:
        """Return a completion for a system+user prompt pair."""
        ...


@runtime_checkable
class SearchTool(Protocol):
    """Web search contract (Strategy pattern). MCP-ready by design."""

    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier for logs and /health."""
        ...

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        """Return raw results; relevance filtering happens in the node."""
        ...
