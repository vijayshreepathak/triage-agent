"""Lightweight MCP server reachability check for /health."""

from __future__ import annotations

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)


async def ping_mcp_server(url: str) -> bool:
    """Return True if the MCP HTTP endpoint responds."""
    if not url.strip():
        return False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(url.strip())
            return response.status_code < 500
    except Exception as exc:
        logger.debug("mcp ping failed", extra={"error": repr(exc)})
        return False
