"""Deterministic confidence scorer.

The LLM is never asked "how confident are you?". Instead this service
applies the explicit, named weights from ``app/config/scoring.py`` to
facts observable in GraphState. Every adjustment that fired is returned
alongside the score, so the number is fully auditable — a reviewer can
reproduce any score by hand.
"""

from __future__ import annotations

from app.config.scoring import CONFIDENCE_WEIGHTS, ConfidenceWeights
from app.models.enums import SearchDecision
from app.models.state import GraphState
from app.services.red_flag_engine import RULE_SOURCE

_MIN_SCORE = 0
_MAX_SCORE = 100
_MULTIPLE_SOURCES_THRESHOLD = 2
_KNOWN_PATTERN_MIN_SIGNALS = 2


class ConfidenceScorer:
    """Pure function object: score(state) -> (0-100 int, audit trail)."""

    def __init__(self, weights: ConfidenceWeights = CONFIDENCE_WEIGHTS) -> None:
        self._w = weights

    def score(self, state: GraphState) -> tuple[int, list[str]]:
        """Compute the deterministic confidence score for a completed run.

        Returns:
            Tuple of (clamped integer score, list of 'name:+delta' entries
            describing every adjustment that fired, for logging/debugging).
        """
        total = self._w.baseline
        applied: list[str] = [f"baseline:+{self._w.baseline}"]

        def apply(name: str, delta: int, condition: bool) -> None:
            nonlocal total
            if condition:
                total += delta
                applied.append(f"{name}:{'+' if delta >= 0 else ''}{delta}")

        signals = state.clinical_signals
        has_rule_flags = any(f.source == RULE_SOURCE for f in state.red_flags)

        # --- Positive evidence ---
        apply("known_symptoms", self._w.known_symptoms, bool(state.symptoms))
        apply(
            "known_pattern",
            self._w.known_pattern,
            state.urgency is not None and len(state.urgency.supporting_signals) >= _KNOWN_PATTERN_MIN_SIGNALS,
        )
        apply("rule_red_flag_match", self._w.rule_red_flag_match, has_rule_flags)
        apply("reliable_search_evidence", self._w.reliable_search_evidence, bool(state.grounded_sources))
        apply(
            "multiple_agreeing_sources",
            self._w.multiple_agreeing_sources,
            len(state.grounded_sources) >= _MULTIPLE_SOURCES_THRESHOLD,
        )
        apply(
            "clear_description",
            self._w.clear_description,
            signals is not None and signals.duration is not None and signals.severity is not None,
        )

        # --- Negative evidence ---
        ambiguity_notes = list(signals.ambiguity_notes) if signals is not None else []
        apply("ambiguous_wording", self._w.ambiguous_wording, bool(ambiguity_notes))
        apply(
            "contradictory_symptoms",
            self._w.contradictory_symptoms,
            any("contradict" in note.lower() for note in ambiguity_notes),
        )
        apply(
            "rare_presentation",
            self._w.rare_presentation,
            state.search_decision_reason == SearchDecision.SEARCH_RARE_OR_UNKNOWN,
        )
        apply(
            "missing_key_information",
            self._w.missing_key_information,
            signals is None or signals.duration is None or signals.severity is None,
        )

        return max(_MIN_SCORE, min(_MAX_SCORE, total)), applied
