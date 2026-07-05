"""Deterministic confidence scoring weights.

The LLM is never asked "how confident are you?" — self-reported confidence
is uncalibrated and hallucination-prone. Instead the scorer starts from a
baseline and applies these explicit, auditable adjustments based on facts
observable in GraphState. Same input state => same score, every time.

Weights live in config (not inline in the node) so they can be tuned or
A/B tested without touching scoring logic, and so tests can assert against
named constants instead of magic numbers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceWeights(BaseModel):
    """Additive adjustments applied to the baseline score, clamped to [0, 100]."""

    model_config = ConfigDict(frozen=True)

    baseline: int = Field(default=40)

    # Positive evidence
    known_symptoms: int = Field(default=15, description="Extractor produced at least one recognized symptom.")
    known_pattern: int = Field(default=20, description="Signals match a well-known clinical presentation.")
    rule_red_flag_match: int = Field(
        default=15, description="Deterministic red-flag rules fired (high-precision signal)."
    )
    reliable_search_evidence: int = Field(
        default=15, description="At least one grounded source above relevance threshold."
    )
    multiple_agreeing_sources: int = Field(default=10, description="Two or more grounded sources.")
    clear_description: int = Field(default=10, description="Duration AND severity both present in signals.")

    # Negative evidence
    ambiguous_wording: int = Field(default=-15, description="Extractor flagged ambiguity notes.")
    contradictory_symptoms: int = Field(default=-10)
    rare_presentation: int = Field(
        default=-10, description="Search branch was taken for a rare/unknown presentation."
    )
    missing_key_information: int = Field(default=-10, description="No duration or no severity available.")


CONFIDENCE_WEIGHTS = ConfidenceWeights()


class RedFlagConfidenceLevels(BaseModel):
    """Deterministic confidence of the red-flag detection step itself.

    Rule hits are high-precision keyword matches; LLM-only findings are
    plausible but unverified, so they score lower. 'None detected' is not
    1.0 — absence of evidence is weaker than positive rule agreement.
    """

    model_config = ConfigDict(frozen=True)

    rule_and_llm_agree: float = Field(default=0.9, ge=0.0, le=1.0)
    rule_only: float = Field(default=0.85, ge=0.0, le=1.0)
    llm_only: float = Field(default=0.6, ge=0.0, le=1.0)
    none_detected: float = Field(default=0.7, ge=0.0, le=1.0)


RED_FLAG_CONFIDENCE = RedFlagConfidenceLevels()
