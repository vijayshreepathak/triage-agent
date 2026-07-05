"""Node 10: confidence_scoring.

Thin adapter around the deterministic ``ConfidenceScorer`` service. The
scoring logic lives in the service (unit-testable without a graph); the
node's job is only to run it against the current state and record the
audit trail of applied adjustments into metadata.
"""

from __future__ import annotations

from typing import Any

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.state import GraphState
from app.services.confidence_scorer import ConfidenceScorer
from app.utils.timing import traced_node


def make_confidence_scoring_node(scorer: ConfidenceScorer) -> NodeFn:
    """Build the confidence node with the deterministic scorer injected."""

    @traced_node(NodeName.CONFIDENCE_SCORING)
    async def confidence_scoring(state: GraphState) -> dict[str, Any]:
        score, applied = scorer.score(state)
        metadata = dict(state.metadata)
        metadata["confidence_adjustments"] = ", ".join(applied)
        return {
            "confidence": score,
            "metadata": metadata,
            "_result_summary": f"confidence={score} ({len(applied)} adjustments)",
        }

    return confidence_scoring
