"""Node 2: extract_clinical_signals.

The LLM-as-parser node: converts free text into the strict
``ClinicalSignals`` structure. This is the only place the LLM reads the
raw patient message for interpretation — everything downstream consumes
the typed structure, which is what keeps the rest of the pipeline
deterministic and testable.

Degradation: if the LLM output is still malformed after the corrective
retry, the node records a RECOVERABLE error and continues with
``clinical_signals=None``. Downstream nodes treat missing signals as
"missing key information" (confidence penalty) and the search decision
treats it as an unknown presentation (search branch) — the pipeline
degrades toward caution, never toward silence.
"""

from __future__ import annotations

from typing import Any

from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.clinical import ClinicalSignals
from app.models.enums import NodeStatus
from app.models.state import GraphState
from app.models.trace import NodeError
from app.prompts.extraction import build_extraction_prompt
from app.services.structured_llm import StructuredLLMCaller, StructuredOutputError
from app.utils.timing import traced_node


def make_extract_signals_node(caller: StructuredLLMCaller) -> NodeFn:
    """Build the extraction node with its LLM gateway injected."""

    @traced_node(NodeName.EXTRACT_SIGNALS)
    async def extract_clinical_signals(state: GraphState) -> dict[str, Any]:
        system, user = build_extraction_prompt(state.patient_message)
        try:
            signals, retries = await caller.call(
                system=system, user=user, schema=ClinicalSignals, operation="extract_signals"
            )
        except StructuredOutputError as exc:
            return {
                "clinical_signals": None,
                "_status": NodeStatus.RECOVERABLE_ERROR,
                "_result_summary": "extraction failed; continuing without structured signals",
                "errors": [
                    NodeError(
                        request_id=state.request_id,
                        node_name=NodeName.EXTRACT_SIGNALS,
                        error_type=type(exc).__name__,
                        root_cause=str(exc),
                        user_safe_message="Symptom details could not be fully analysed.",
                    )
                ],
            }
        return {
            "clinical_signals": signals,
            "symptoms": list(signals.symptoms),
            "_retry_count": retries,
            "_result_summary": f"{len(signals.symptoms)} symptoms, {len(signals.ambiguity_notes)} ambiguity notes",
        }

    return extract_clinical_signals
