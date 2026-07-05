"""Standalone MCP medical-search server.

Run:
    python -m mcp_server.server

Then in .env:
    SEARCH_PROVIDER=mcp
    MCP_SERVER_URL=http://127.0.0.1:8765/mcp
    MCP_SEARCH_TOOL_NAME=search

Returns JSON text content that ``MCPSearchTool`` parses into grounded sources.
Uses DuckDuckGo under the hood — no Tavily key required for the MCP path.
"""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

_HOST = os.getenv("MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("MCP_PORT", "8765"))

mcp = FastMCP("stance-medical-search", host=_HOST, port=_PORT)


def _ddg_search(query: str, max_results: int) -> list[dict[str, Any]]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        rows = list(ddgs.text(query, max_results=max_results))
    results: list[dict[str, Any]] = []
    for rank, row in enumerate(rows):
        url = str(row.get("href", "")).strip()
        if not url:
            continue
        results.append(
            {
                "title": str(row.get("title", "")).strip() or url,
                "summary": str(row.get("body", "")).strip(),
                "url": url,
                "relevance": max(0.3, 0.9 - 0.1 * rank),
            }
        )
    return results


@mcp.tool()
def search(query: str, max_results: int = 4) -> str:
    """Search medical guidance for ambiguous symptom presentations.

    Args:
        query: Clinical search query (symptoms + context).
        max_results: Maximum number of results to return (1-10).

    Returns:
        JSON array of {title, summary, url, relevance} objects.
    """
    capped = max(1, min(max_results, 10))
    payload = _ddg_search(query, capped)
    return json.dumps(payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
