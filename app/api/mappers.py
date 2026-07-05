"""GraphState -> API response translation.

The only place internal state meets the external contract. Routes stay
logic-free; nodes never know the HTTP shape. Defensive fallbacks here are
belt-and-braces only — ``build_structured_response`` already guarantees a
complete state on every path.
"""

from __future__ import annotations

from app.config.constants import ACTION_BY_URGENCY, DISCLAIMERS, SAFE_FALLBACK_REASONING
from app.models.enums import UrgencyLevel
from app.models.state import GraphState
from app.schemas.debug import DebugResponse, NodeErrorOut, NodeTraceOut
from app.schemas.triage import TriageResponse

_DEGRADED_CONFIDENCE = 20


def state_to_response(state: GraphState) -> TriageResponse:
    """Project the final graph state onto the public triage contract."""
    urgency_level = UrgencyLevel(state.urgency.urgency) if state.urgency is not None else UrgencyLevel.HIGH
    triage_decision = state.urgency.reason if state.urgency is not None else SAFE_FALLBACK_REASONING

    return TriageResponse(
        patient_message_id=state.patient_id,
        urgency_level=urgency_level,
        red_flags=[flag.name for flag in state.red_flags],
        triage_decision=triage_decision,
        confidence=state.confidence if state.confidence is not None else _DEGRADED_CONFIDENCE,
        reasoning=state.clinical_reasoning or SAFE_FALLBACK_REASONING,
        disclaimers=list(state.disclaimer) or list(DISCLAIMERS),
        recommended_action=state.recommended_action or ACTION_BY_URGENCY[urgency_level],
        sources=[source.url for source in state.grounded_sources],
        request_id=state.request_id,
    )


def state_to_debug_response(state: GraphState) -> DebugResponse:
    """Project the final graph state onto the debug contract (user-safe fields only)."""
    return DebugResponse(
        triage=state_to_response(state),
        search_decision_reason=state.search_decision_reason,
        search_query=state.search_query,
        execution_trace=[
            NodeTraceOut(
                node_name=t.node_name,
                latency_ms=round(t.latency_ms, 2),
                status=str(t.status),
                result_summary=t.result_summary,
                retry_count=t.retry_count,
                errors=t.errors,
            )
            for t in state.execution_trace
        ],
        errors=[
            NodeErrorOut(
                timestamp=e.timestamp,
                node_name=e.node_name,
                error_type=e.error_type,
                user_safe_message=e.user_safe_message,
            )
            for e in state.errors
        ],
        metadata=state.metadata,
    )
