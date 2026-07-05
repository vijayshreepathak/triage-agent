"""MCP-backed SearchTool (Strategy pattern, MCP edition).

Connects to any MCP server over streamable HTTP and calls a configured
search-like tool. Because it implements the same ``SearchTool`` Protocol
as Tavily/DuckDuckGo, the graph, nodes, and factory wiring are untouched —
this is the "swap in an MCP server with zero graph changes" requirement
made concrete.

Expected tool result contract (tolerant by design — MCP servers vary):
each text content item is parsed as JSON; results are read from a
top-level list, or from a "results" key. Each row may use
title / url|href|link / summary|content|snippet|body / score|relevance.
Rows without a URL are dropped — an uncitable result is useless to us.
"""

from __future__ import annotations

import json
from typing import Any

from app.config.settings import Settings
from app.models.clinical import SearchResult
from app.utils.logging import get_logger
from app.utils.retry import retry_async

logger = get_logger(__name__)

_DEFAULT_RELEVANCE = 0.7  # servers that return no score still passed our tool-name contract


def parse_mcp_rows(rows: list[dict[str, Any]]) -> list[SearchResult]:
    """Map heterogeneous MCP result rows onto our SearchResult model."""
    results: list[SearchResult] = []
    for row in rows:
        url = str(row.get("url") or row.get("href") or row.get("link") or "").strip()
        if not url:
            continue
        raw_score = row.get("score", row.get("relevance", _DEFAULT_RELEVANCE))
        try:
            relevance = min(1.0, max(0.0, float(raw_score)))
        except (TypeError, ValueError):
            relevance = _DEFAULT_RELEVANCE
        results.append(
            SearchResult(
                title=str(row.get("title", "")).strip() or url,
                summary=str(
                    row.get("summary") or row.get("content") or row.get("snippet") or row.get("body") or ""
                ).strip(),
                url=url,
                relevance=relevance,
            )
        )
    return results


def parse_mcp_content(text_payloads: list[str]) -> list[SearchResult]:
    """Extract result rows from MCP text content items (JSON, tolerant)."""
    rows: list[dict[str, Any]] = []
    for payload in text_payloads:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue  # non-JSON text item: nothing citable in it
        if isinstance(data, list):
            rows.extend(r for r in data if isinstance(r, dict))
        elif isinstance(data, dict):
            inner = data.get("results", data)
            if isinstance(inner, list):
                rows.extend(r for r in inner if isinstance(r, dict))
            elif isinstance(inner, dict):
                rows.append(inner)
    return parse_mcp_rows(rows)


class MCPSearchTool:
    """SearchTool implementation backed by a remote MCP server."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.mcp_server_url
        self._tool_name = settings.mcp_search_tool_name
        self._settings = settings

    @property
    def provider_name(self) -> str:
        return f"mcp:{self._tool_name}"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        """Call the MCP tool and normalize its output.

        A fresh session per call keeps the adapter stateless (matching every
        other strategy); connection pooling is a later optimization if MCP
        search becomes the primary provider.
        """

        async def _call() -> list[str]:
            # Local imports: the mcp package is only needed when this
            # strategy is actually selected.
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(self._url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        self._tool_name, {"query": query, "max_results": max_results}
                    )
                    return [
                        item.text
                        for item in result.content
                        if getattr(item, "type", "") == "text" and getattr(item, "text", "")
                    ]

        payloads, _ = await retry_async(
            _call,
            operation_name=f"search:{self.provider_name}",
            max_retries=self._settings.max_retries,
            base_delay_seconds=self._settings.retry_base_delay_seconds,
        )
        results = parse_mcp_content(payloads)
        logger.info(
            "mcp search completed",
            extra={"tool": self._tool_name, "raw_payloads": len(payloads), "results": len(results)},
        )
        return results[:max_results]
