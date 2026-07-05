"""Node 7: search_medical_sources (conditional branch).

Only runs when the routing edge selected it. Depends exclusively on the
``SearchTool`` Protocol — this node cannot name Tavily, DuckDuckGo, or a
future MCP server. Relevance filtering happens HERE (not in the tool) so
the quality bar is uniform across providers and configured in one place.

A search failure is RECOVERABLE by definition: triage proceeds without
external evidence, and the response builder will surface
"No verified external source found." rather than fabricating anything.
"""

from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.enums import NodeStatus
from app.models.state import GraphState
from app.models.trace import NodeError
from app.tools.interfaces import SearchTool
from app.utils.timing import traced_node


def make_search_medical_sources_node(search_tool: SearchTool, settings: Settings) -> NodeFn:
    """Build the search node with the search strategy and settings injected."""

    @traced_node(NodeName.SEARCH_MEDICAL_SOURCES)
    async def search_medical_sources(state: GraphState) -> dict[str, Any]:
        if not state.search_query:
            # Defensive: routing should prevent this; treat as a skipped search.
            return {
                "search_results": [],
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": "no query present",
            }

        try:
            results = await search_tool.search(state.search_query, max_results=settings.search_max_results)
        except Exception as exc:
            return {
                "search_results": [],
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": f"search failed via {search_tool.provider_name}",
                "errors": [
                    NodeError(
                        request_id=state.request_id,
                        node_name=NodeName.SEARCH_MEDICAL_SOURCES,
                        error_type=type(exc).__name__,
                        root_cause=str(exc),
                        user_safe_message="External medical sources were unavailable for this assessment.",
                    )
                ],
            }

        kept = [r for r in results if r.relevance >= settings.search_min_relevance]
        return {
            "search_results": kept,
            "_result_summary": f"{len(kept)}/{len(results)} results kept (provider={search_tool.provider_name})",
        }

    return search_medical_sources
