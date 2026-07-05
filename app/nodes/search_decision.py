"""Node 6: search_decision.

Fully deterministic — no LLM. An ordered rule ladder maps the current
state to a search decision, and the FIRST matching rule wins, so the
decision is reproducible and each reason is logged:

1. Emergency               -> skip (time-critical; search adds latency, no value)
2. Unknown presentation    -> search (no extracted signals/symptoms to reason from)
3. Medication question     -> search (dosing/interaction facts benefit from sources)
4. Ambiguous presentation  -> search (extractor flagged vagueness/contradiction)
5. Moderate urgency        -> search (borderline zone where evidence helps most)
6. Otherwise (low / high)  -> skip (common presentation; action already clear)

The node also builds the search query deterministically from canonical
symptoms + demographic qualifiers — the LLM never invents queries.
"""

from __future__ import annotations

from typing import Any, Final

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.enums import SearchDecision, UrgencyLevel
from app.models.state import GraphState
from app.utils.timing import traced_node

_MEDICATION_CUES: Final[tuple[str, ...]] = ("interaction", "side effect", "dosage", "dose of")
_MAX_QUERY_SYMPTOMS: Final[int] = 4


def _build_query(state: GraphState) -> str:
    """Deterministic search query from canonical symptoms + demographics."""
    parts = list(state.symptoms[:_MAX_QUERY_SYMPTOMS])
    signals = state.clinical_signals
    if signals is not None:
        if signals.affects_child:
            parts.append("in child")
        if signals.is_pregnant:
            parts.append("during pregnancy")
        if signals.age is not None:
            parts.append(f"age {signals.age}")
    symptom_text = ", ".join(parts) if parts else state.patient_message[:120]
    return f"{symptom_text} — possible causes and medical urgency guidance"


def make_search_decision_node() -> NodeFn:
    """Build the search decision node (deterministic, no dependencies)."""

    @traced_node(NodeName.SEARCH_DECISION)
    async def search_decision(state: GraphState) -> dict[str, Any]:
        urgency = state.urgency.urgency if state.urgency is not None else None
        signals = state.clinical_signals
        message = state.normalized_message or ""

        needs_search: bool
        reason: SearchDecision
        if urgency == UrgencyLevel.EMERGENCY:
            needs_search, reason = False, SearchDecision.SKIP_EMERGENCY
        elif signals is None or not state.symptoms:
            needs_search, reason = True, SearchDecision.SEARCH_RARE_OR_UNKNOWN
        elif any(cue in message for cue in _MEDICATION_CUES):
            needs_search, reason = True, SearchDecision.SEARCH_MEDICATION_QUESTION
        elif signals.ambiguity_notes:
            needs_search, reason = True, SearchDecision.SEARCH_BORDERLINE
        elif urgency == UrgencyLevel.MODERATE:
            needs_search, reason = True, SearchDecision.SEARCH_BORDERLINE
        else:
            needs_search, reason = False, SearchDecision.SKIP_COMMON_PRESENTATION

        return {
            "needs_search": needs_search,
            "search_decision_reason": str(reason),
            "search_query": _build_query(state) if needs_search else None,
            "_result_summary": f"needs_search={needs_search} ({reason})",
        }

    return search_decision
