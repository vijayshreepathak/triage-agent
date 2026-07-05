"""Node 5: urgency_classification.

LLM proposes, deterministic rules dispose — and rules can only ESCALATE:

1. The LLM classifies into the closed vocabulary (enum-validated; an
   out-of-vocabulary answer fails Pydantic validation and triggers the
   structured retry, so a fifth category is impossible).
2. Post-processing floors: force_emergency rule flags => emergency;
   any rule flag with an LLM verdict of 'low' => high.
3. If the LLM fails entirely, the fallback is derived from red flags and
   is never 'low' — uncertainty must escalate, not reassure.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.clinical import UrgencyAssessment
from app.models.enums import URGENCY_RANK, NodeStatus, UrgencyLevel
from app.models.state import GraphState
from app.models.trace import NodeError
from app.prompts.urgency import build_urgency_prompt
from app.services.red_flag_engine import RULE_SOURCE, RedFlagEngine
from app.services.structured_llm import StructuredLLMCaller, StructuredOutputError
from app.utils.logging import get_logger
from app.utils.timing import traced_node

logger = get_logger(__name__)


class _LLMUrgency(BaseModel):
    """LLM output schema. ``urgency: UrgencyLevel`` enforces the closed vocabulary."""

    urgency: UrgencyLevel
    reason: str = Field(min_length=1)
    supporting_signals: list[str] = Field(default_factory=list)


def _escalate(
    proposed: UrgencyLevel, *, forces_emergency: bool, has_rule_flags: bool
) -> tuple[UrgencyLevel, str | None]:
    """Apply escalation-only safety floors. Returns (level, escalation note)."""
    if forces_emergency and URGENCY_RANK[proposed] < URGENCY_RANK[UrgencyLevel.EMERGENCY]:
        return UrgencyLevel.EMERGENCY, "escalated to emergency by deterministic red-flag rule"
    if has_rule_flags and proposed == UrgencyLevel.LOW:
        return UrgencyLevel.HIGH, "escalated from low: red flags present"
    return proposed, None


def make_urgency_classification_node(caller: StructuredLLMCaller, engine: RedFlagEngine) -> NodeFn:
    """Build the urgency node with LLM gateway and rule engine injected."""

    @traced_node(NodeName.URGENCY_CLASSIFICATION)
    async def urgency_classification(state: GraphState) -> dict[str, Any]:
        forces = engine.forces_emergency(state.red_flags)
        has_rule_flags = any(f.source == RULE_SOURCE for f in state.red_flags)
        flag_names = [f.name for f in state.red_flags]

        try:
            system, user = build_urgency_prompt(state.patient_message, state.clinical_signals, flag_names)
            llm_out, retries = await caller.call(
                system=system, user=user, schema=_LLMUrgency, operation="urgency_classification"
            )
        except StructuredOutputError as exc:
            # Fail-safe fallback: derived from deterministic evidence, never 'low'.
            level = (
                UrgencyLevel.EMERGENCY
                if forces
                else (UrgencyLevel.HIGH if has_rule_flags else UrgencyLevel.MODERATE)
            )
            return {
                "urgency": UrgencyAssessment(
                    urgency=level,
                    reason="Automated classification was unavailable; level set cautiously from detected warning signs.",
                    supporting_signals=flag_names,
                ),
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": f"llm failed; fallback={level}",
                "errors": [
                    NodeError(
                        request_id=state.request_id,
                        node_name=NodeName.URGENCY_CLASSIFICATION,
                        error_type=type(exc).__name__,
                        root_cause=str(exc),
                        user_safe_message="Urgency was estimated conservatively due to an internal issue.",
                    )
                ],
            }

        final_level, note = _escalate(llm_out.urgency, forces_emergency=forces, has_rule_flags=has_rule_flags)
        if note is not None:
            logger.info(
                "urgency escalated",
                extra={
                    "node": NodeName.URGENCY_CLASSIFICATION,
                    "from": llm_out.urgency,
                    "to": final_level,
                    "note": note,
                },
            )
        reason = llm_out.reason if note is None else f"{llm_out.reason} ({note})"

        return {
            "urgency": UrgencyAssessment(
                urgency=final_level, reason=reason, supporting_signals=llm_out.supporting_signals
            ),
            "_retry_count": retries,
            "_result_summary": f"urgency={final_level}" + (" (escalated)" if note else ""),
        }

    return urgency_classification
