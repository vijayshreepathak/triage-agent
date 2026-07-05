"""Node 8: merge_evidence — the join point of both branches.

Converts filtered ``SearchResult``s into citable ``GroundedSource``s,
deduplicated by URL. Deterministic, no LLM.

Anti-hallucination property: this node is the ONLY producer of
``grounded_sources``, and it only copies URLs verbatim from search
results. The explanation LLM never sees or emits URLs, and the response
builder cites only from this list — fabricated citations are therefore
structurally impossible, not just discouraged by prompt.
"""

from __future__ import annotations

from typing import Any, Final

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.clinical import GroundedSource
from app.models.state import GraphState
from app.utils.timing import traced_node

_MAX_SNIPPET_CHARS: Final[int] = 300


def make_merge_evidence_node() -> NodeFn:
    """Build the evidence merge node (deterministic, no dependencies)."""

    @traced_node(NodeName.MERGE_EVIDENCE)
    async def merge_evidence(state: GraphState) -> dict[str, Any]:
        seen_urls: set[str] = set()
        sources: list[GroundedSource] = []
        for result in state.search_results:
            url = result.url.strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append(
                GroundedSource(
                    title=result.title.strip(),
                    url=url,
                    snippet=result.summary.strip()[:_MAX_SNIPPET_CHARS],
                )
            )
        return {
            "grounded_sources": sources,
            "_result_summary": f"{len(sources)} grounded sources (search branch: {state.needs_search})",
        }

    return merge_evidence
