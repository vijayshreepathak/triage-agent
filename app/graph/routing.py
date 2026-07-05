"""Conditional edge functions.

Routing functions are pure reads of GraphState: they contain **zero
business logic**. The *decision* whether to search is made by the
``search_decision`` node (Phase 3) which writes ``needs_search`` and
``search_decision_reason`` into state; the router merely dispatches on
that flag. This separation means the decision logic is unit-testable as a
node, and the router is a trivial, deterministic function that can never
disagree with what was logged.
"""

from __future__ import annotations

from app.graph.node_names import NodeName
from app.models.state import GraphState
from app.utils.logging import get_logger

logger = get_logger(__name__)


def route_after_search_decision(state: GraphState) -> str:
    """Dispatch to the search node or skip straight to evidence merge.

    Emergencies and common presentations skip search (latency without
    benefit); rare/ambiguous presentations take the search branch. The
    reason was already recorded in state by the decision node — we log it
    here too so the routing event itself is auditable.
    """
    target = NodeName.SEARCH_MEDICAL_SOURCES if state.needs_search else NodeName.MERGE_EVIDENCE
    logger.info(
        "conditional route taken",
        extra={
            "node": NodeName.SEARCH_DECISION,
            "needs_search": state.needs_search,
            "reason": state.search_decision_reason,
            "next_node": str(target),
        },
    )
    return target
