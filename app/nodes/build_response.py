"""Node 11: build_structured_response — the safety net.

Last node on every path. Guarantees the final state satisfies the response
contract NO MATTER what failed upstream:

- urgency missing        -> derive cautiously from red flags (never 'low')
- reasoning missing      -> hardcoded safe fallback text
- searched but 0 sources -> append "No verified external source found."
- confidence missing     -> conservative floor value
- disclaimer             -> ALWAYS the hardcoded constants, appended here,
                            unconditionally — the one invariant with no code path around it.
"""

from __future__ import annotations

from typing import Any, Final

from app.config.constants import (
    ACTION_BY_URGENCY,
    DISCLAIMERS,
    NO_VERIFIED_SOURCE_MESSAGE,
    SAFE_FALLBACK_REASONING,
)
from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.clinical import UrgencyAssessment
from app.models.enums import UrgencyLevel
from app.models.state import GraphState
from app.services.red_flag_engine import RULE_SOURCE
from app.utils.timing import traced_node

# Confidence when the scorer itself never ran: deliberately low — an
# incomplete pipeline must not look confident.
_DEGRADED_CONFIDENCE: Final[int] = 20


def _fallback_urgency(state: GraphState) -> UrgencyAssessment:
    """Cautious urgency when classification never completed (never 'low')."""
    has_rule_flags = any(f.source == RULE_SOURCE for f in state.red_flags)
    level = UrgencyLevel.EMERGENCY if has_rule_flags else UrgencyLevel.HIGH
    return UrgencyAssessment(
        urgency=level,
        reason="Assessment could not be completed; urgency was set cautiously. Seek medical care.",
        supporting_signals=[f.name for f in state.red_flags],
    )


def make_build_response_node() -> NodeFn:
    """Build the response builder node (deterministic, no dependencies)."""

    @traced_node(NodeName.BUILD_RESPONSE)
    async def build_structured_response(state: GraphState) -> dict[str, Any]:
        urgency = state.urgency if state.urgency is not None else _fallback_urgency(state)

        reasoning = state.clinical_reasoning or SAFE_FALLBACK_REASONING
        if state.needs_search and not state.grounded_sources:
            reasoning = f"{reasoning} {NO_VERIFIED_SOURCE_MESSAGE}"

        return {
            "urgency": urgency,
            "clinical_reasoning": reasoning,
            "confidence": state.confidence if state.confidence is not None else _DEGRADED_CONFIDENCE,
            "recommended_action": ACTION_BY_URGENCY[UrgencyLevel(urgency.urgency)],
            "disclaimer": list(DISCLAIMERS),
            "_result_summary": f"final urgency={urgency.urgency}, degraded={state.urgency is None}",
        }

    return build_structured_response
