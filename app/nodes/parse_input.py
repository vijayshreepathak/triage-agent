"""Node 1: parse_input.

Deterministic text normalization — collapse whitespace and lowercase into
``normalized_message`` for keyword rule matching. The ORIGINAL message is
preserved untouched in ``patient_message`` because LLM prompts get the raw
text (casing can carry meaning, e.g. drug names, "ER").

Why a whole node for this: it gives the pipeline a single, traced place
where input hygiene happens, so no downstream node ever re-normalizes
(no duplicated logic) and malformed input fails here, visibly.
"""

from __future__ import annotations

from typing import Any

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.state import GraphState
from app.utils.timing import traced_node


def make_parse_input_node() -> NodeFn:
    """Build the parse_input node (no dependencies — fully deterministic)."""

    @traced_node(NodeName.PARSE_INPUT)
    async def parse_input(state: GraphState) -> dict[str, Any]:
        normalized = " ".join(state.patient_message.split()).lower()
        return {
            "normalized_message": normalized,
            "_result_summary": f"normalized {len(normalized)} chars",
        }

    return parse_input
