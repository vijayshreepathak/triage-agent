"""Node 3: normalize_symptoms.

Deterministic vocabulary normalization: maps colloquial phrasings to
canonical clinical terms using the config table, and additionally scans
the normalized message for synonym phrases the extractor may have missed
(belt-and-braces — a purely mechanical recall boost, no interpretation).

Sorted output => byte-identical state for identical inputs, which keeps
downstream behavior (and tests) deterministic.
"""

from __future__ import annotations

from typing import Any

from app.config.symptom_synonyms import SYMPTOM_SYNONYMS
from app.graph.builder import NodeFn
from app.graph.node_names import NodeName
from app.models.state import GraphState
from app.utils.timing import traced_node


def make_normalize_symptoms_node() -> NodeFn:
    """Build the symptom normalization node (deterministic, no dependencies)."""

    @traced_node(NodeName.NORMALIZE_SYMPTOMS)
    async def normalize_symptoms(state: GraphState) -> dict[str, Any]:
        canonical: set[str] = set()

        # Normalize what the extractor produced.
        for symptom in state.symptoms:
            term = symptom.strip().lower()
            if term:
                canonical.add(SYMPTOM_SYNONYMS.get(term, term))

        # Recall pass: catch synonym phrases present verbatim in the message.
        message = state.normalized_message or ""
        for phrase, canon in SYMPTOM_SYNONYMS.items():
            if phrase in message:
                canonical.add(canon)

        return {
            "symptoms": sorted(canonical),
            "_result_summary": f"{len(canonical)} canonical symptoms",
        }

    return normalize_symptoms
