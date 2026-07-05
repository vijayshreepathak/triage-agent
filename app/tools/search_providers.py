"""Search provider strategies + factory (Strategy pattern).

Three implementations of the ``SearchTool`` Protocol:

- TavilySearchTool     — preferred; returns real relevance scores.
- DuckDuckGoSearchTool — keyless fallback; no scores, so relevance is a
                         deterministic rank-decay heuristic (top result
                         0.9, each subsequent -0.1, floor 0.3).
- NullSearchTool       — SEARCH_PROVIDER=none; always empty. The graph
                         then reports "No verified external source found."
                         instead of pretending to have evidence.

An MCP-backed implementation later is just a fourth class here — the
graph, nodes, and factory signature all stay untouched.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from app.config.settings import Settings
from app.models.clinical import SearchResult
from app.models.enums import SearchProvider
from app.tools.errors import ToolConfigurationError
from app.tools.interfaces import SearchTool
from app.utils.logging import get_logger
from app.utils.retry import retry_async

logger = get_logger(__name__)

_DDG_TOP_RELEVANCE = 0.9
_DDG_RANK_DECAY = 0.1
_DDG_MIN_RELEVANCE = 0.3


class NullSearchTool:
    """No-op search for keyless/offline operation."""

    @property
    def provider_name(self) -> str:
        return "none"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        logger.info("search disabled; returning no results", extra={"query": query})
        return []


class TavilySearchTool:
    """Tavily adapter — native relevance scores, async client."""

    def __init__(self, api_key: str, settings: Settings) -> None:
        from tavily import AsyncTavilyClient  # local import: optional dependency path

        self._client = AsyncTavilyClient(api_key=api_key)
        self._settings = settings

    @property
    def provider_name(self) -> str:
        return "tavily"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        async def _call() -> dict[str, Any]:
            return await self._client.search(query=query, max_results=max_results, search_depth="basic")

        response, _ = await retry_async(
            _call,
            operation_name="search:tavily",
            max_retries=self._settings.max_retries,
            base_delay_seconds=self._settings.retry_base_delay_seconds,
        )
        results: list[SearchResult] = []
        for row in response.get("results", []):
            url = str(row.get("url", "")).strip()
            if not url:
                continue  # a result without a URL can never be a citable source
            results.append(
                SearchResult(
                    title=str(row.get("title", "")).strip() or url,
                    summary=str(row.get("content", "")).strip(),
                    url=url,
                    relevance=min(1.0, max(0.0, float(row.get("score", 0.0)))),
                )
            )
        return results


class DuckDuckGoSearchTool:
    """DuckDuckGo adapter — keyless; sync library bridged via a worker thread.

    ``ddgs_factory`` is injectable so tests can substitute a fake without
    network access or monkeypatching module internals.
    """

    def __init__(self, settings: Settings, ddgs_factory: Callable[[], Any] | None = None) -> None:
        self._settings = settings
        if ddgs_factory is None:
            from ddgs import DDGS

            ddgs_factory = DDGS
        self._ddgs_factory = ddgs_factory

    @property
    def provider_name(self) -> str:
        return "duckduckgo"

    @staticmethod
    def rank_relevance(rank: int) -> float:
        """Deterministic rank-decay relevance for a scoreless provider."""
        return max(_DDG_MIN_RELEVANCE, _DDG_TOP_RELEVANCE - _DDG_RANK_DECAY * rank)

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        def _sync_search() -> list[dict[str, str]]:
            with self._ddgs_factory() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        async def _call() -> list[dict[str, str]]:
            return await asyncio.to_thread(_sync_search)

        rows, _ = await retry_async(
            _call,
            operation_name="search:duckduckgo",
            max_retries=self._settings.max_retries,
            base_delay_seconds=self._settings.retry_base_delay_seconds,
        )
        results: list[SearchResult] = []
        for rank, row in enumerate(rows):
            url = str(row.get("href", "")).strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=str(row.get("title", "")).strip() or url,
                    summary=str(row.get("body", "")).strip(),
                    url=url,
                    relevance=self.rank_relevance(rank),
                )
            )
        return results


def create_search_tool(settings: Settings) -> SearchTool:
    """Factory: build the configured search strategy. Fails fast on bad config."""
    if settings.search_provider == SearchProvider.NONE:
        return NullSearchTool()
    if settings.search_provider == SearchProvider.TAVILY:
        if not settings.tavily_api_key:
            raise ToolConfigurationError("SEARCH_PROVIDER=tavily but TAVILY_API_KEY is not set")
        return TavilySearchTool(settings.tavily_api_key, settings)
    if settings.search_provider == SearchProvider.DUCKDUCKGO:
        return DuckDuckGoSearchTool(settings)
    if settings.search_provider == SearchProvider.MCP:
        if not settings.mcp_server_url:
            raise ToolConfigurationError("SEARCH_PROVIDER=mcp but MCP_SERVER_URL is not set")
        from app.tools.mcp_search import MCPSearchTool  # local import: optional dependency path

        return MCPSearchTool(settings)
    raise ToolConfigurationError(f"Unknown search provider: {settings.search_provider}")
