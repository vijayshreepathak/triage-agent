"""Canonical node names.

Single source of truth for graph vertex identifiers — used by the builder,
the routing functions, the tracing decorator, and tests. String literals
scattered across modules would let a typo silently create a dangling edge;
an enum makes that a NameError at import time.
"""

from __future__ import annotations

from enum import StrEnum


class NodeName(StrEnum):
    """Every vertex in the triage graph, in execution order."""

    PARSE_INPUT = "parse_input"
    EXTRACT_SIGNALS = "extract_clinical_signals"
    NORMALIZE_SYMPTOMS = "normalize_symptoms"
    RED_FLAG_DETECTION = "red_flag_detection"
    URGENCY_CLASSIFICATION = "urgency_classification"
    SEARCH_DECISION = "search_decision"
    SEARCH_MEDICAL_SOURCES = "search_medical_sources"
    MERGE_EVIDENCE = "merge_evidence"
    GENERATE_EXPLANATION = "generate_clinical_explanation"
    CONFIDENCE_SCORING = "confidence_scoring"
    BUILD_RESPONSE = "build_structured_response"
