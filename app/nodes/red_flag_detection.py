"""Node 4: red_flag_detection.

Two-layer detection, by design:

1. Deterministic rule engine (source of truth, auditable, cannot hallucinate).
2. LLM augmentation for phrasings the keyword table misses.

Union + dedupe, provenance preserved. Detection confidence is a
deterministic mapping (config-driven) of which layers found what — never
an LLM self-report. If the LLM layer fails, the node degrades gracefully
to rule-only results: safety rules never depend on the LLM being up.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config.scoring import RED_FLAG_CONFIDENCE
from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.enums import NodeStatus
from app.models.state import GraphState
from app.prompts.red_flags import build_red_flag_prompt
from app.services.red_flag_engine import RedFlagEngine
from app.services.structured_llm import StructuredLLMCaller, StructuredOutputError
from app.utils.timing import traced_node


class _LLMRedFlags(BaseModel):
    """Schema for the LLM augmentation output."""

    red_flags: list[str] = Field(default_factory=list)


def _detection_confidence(rule_count: int, llm_count: int) -> float:
    """Deterministic confidence of the detection step (config-driven levels)."""
    if rule_count and llm_count:
        return RED_FLAG_CONFIDENCE.rule_and_llm_agree
    if rule_count:
        return RED_FLAG_CONFIDENCE.rule_only
    if llm_count:
        return RED_FLAG_CONFIDENCE.llm_only
    return RED_FLAG_CONFIDENCE.none_detected


def make_red_flag_detection_node(engine: RedFlagEngine, caller: StructuredLLMCaller) -> NodeFn:
    """Build the red-flag node with the rule engine and LLM gateway injected."""

    @traced_node(NodeName.RED_FLAG_DETECTION)
    async def red_flag_detection(state: GraphState) -> dict[str, Any]:
        text = state.normalized_message or state.patient_message.lower()
        rule_flags = engine.detect(text)

        llm_names: list[str] = []
        status = NodeStatus.SUCCESS
        retries = 0
        try:
            system, user = build_red_flag_prompt(
                state.patient_message, state.symptoms, [f.name for f in rule_flags]
            )
            llm_output, retries = await caller.call(
                system=system, user=user, schema=_LLMRedFlags, operation="red_flag_llm"
            )
            llm_names = llm_output.red_flags
        except StructuredOutputError:
            # Rule layer already ran — degrade to deterministic-only detection.
            status = NodeStatus.RECOVERABLE_ERROR

        merged = RedFlagEngine.merge(rule_flags, llm_names)
        return {
            "red_flags": merged,
            "red_flag_confidence": _detection_confidence(len(rule_flags), len(llm_names)),
            "_status": status,
            "_retry_count": retries,
            "_result_summary": f"{len(rule_flags)} rule + {len(llm_names)} llm -> {len(merged)} merged",
        }

    return red_flag_detection
