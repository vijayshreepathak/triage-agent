"""Node 9: generate_clinical_explanation.

Produces the only LLM prose the user ever sees: a <=100-word explanation
of the decision. Chain-of-thought never leaves the system — the prompt
forbids it AND this node enforces a deterministic word cap as a hard
guard (prompts are requests; truncation is a guarantee).

Failure degrades to a hardcoded safe fallback text; the triage decision
itself is unaffected because it was made by earlier nodes.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, Field

from app.config.constants import SAFE_FALLBACK_REASONING
from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.enums import NodeStatus
from app.models.state import GraphState
from app.prompts.explanation import build_explanation_prompt
from app.services.structured_llm import StructuredLLMCaller, StructuredOutputError
from app.utils.logging import get_logger
from app.utils.timing import traced_node

logger = get_logger(__name__)

_MAX_WORDS: Final[int] = 100


def _enforce_word_cap(text: str) -> str:
    """Deterministic guard for the 100-word limit."""
    words = text.split()
    if len(words) <= _MAX_WORDS:
        return text.strip()
    logger.warning(
        "explanation exceeded word cap; truncated",
        extra={"node": NodeName.GENERATE_EXPLANATION, "words": len(words)},
    )
    return " ".join(words[:_MAX_WORDS]).rstrip(",;: ") + "."


class _LLMExplanation(BaseModel):
    """Schema for the explanation output."""

    explanation: str = Field(min_length=1)


def make_generate_explanation_node(caller: StructuredLLMCaller) -> NodeFn:
    """Build the explanation node with its LLM gateway injected."""

    @traced_node(NodeName.GENERATE_EXPLANATION)
    async def generate_clinical_explanation(state: GraphState) -> dict[str, Any]:
        if state.urgency is None:
            # Classification failed upstream; a generated explanation would
            # have nothing truthful to explain. Use the safe fallback.
            return {
                "clinical_reasoning": SAFE_FALLBACK_REASONING,
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": "no urgency available; fallback text used",
            }

        system, user = build_explanation_prompt(
            urgency=str(state.urgency.urgency),
            urgency_reason=state.urgency.reason,
            symptoms=state.symptoms,
            red_flag_names=[f.name for f in state.red_flags],
            sources=state.grounded_sources,
            search_was_used=state.needs_search and bool(state.grounded_sources),
        )
        try:
            output, retries = await caller.call(
                system=system, user=user, schema=_LLMExplanation, operation="generate_explanation"
            )
        except StructuredOutputError:
            return {
                "clinical_reasoning": SAFE_FALLBACK_REASONING,
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": "llm failed; fallback text used",
            }

        return {
            "clinical_reasoning": _enforce_word_cap(output.explanation),
            "_retry_count": retries,
            "_result_summary": f"{len(output.explanation.split())} words",
        }

    return generate_clinical_explanation
