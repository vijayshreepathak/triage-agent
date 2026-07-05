"""Unit tests for the deterministic confidence scorer."""

from __future__ import annotations

from app.models.clinical import ClinicalSignals, GroundedSource, RedFlag, UrgencyAssessment
from app.models.enums import SearchDecision
from app.models.state import GraphState
from app.services.confidence_scorer import ConfidenceScorer


def _state(**overrides: object) -> GraphState:
    base: dict[str, object] = {
        "patient_id": "case_test",
        "patient_message": "msg",
        "request_id": "req",
    }
    base.update(overrides)
    return GraphState.model_validate(base)


def test_strong_evidence_clamps_at_100() -> None:
    state = _state(
        symptoms=["chest pain", "dyspnea"],
        clinical_signals=ClinicalSignals(symptoms=["chest pain"], duration="20 minutes", severity="crushing"),
        red_flags=[RedFlag(name="chest pain with cardiac features", source="rule")],
        urgency=UrgencyAssessment(urgency="emergency", reason="r", supporting_signals=["a", "b"]),
        grounded_sources=[
            GroundedSource(title="A", url="https://a.example", snippet="s"),
            GroundedSource(title="B", url="https://b.example", snippet="s"),
        ],
    )
    score, applied = ConfidenceScorer().score(state)
    # 40 +15 +20 +15 +15 +10 +10 = 125 -> clamped
    assert score == 100
    assert any(a.startswith("known_pattern") for a in applied)


def test_empty_state_gets_missing_information_penalty() -> None:
    score, applied = ConfidenceScorer().score(_state())
    # baseline 40, missing key info -10
    assert score == 30
    assert "missing_key_information:-10" in applied


def test_ambiguity_and_rarity_penalties_apply() -> None:
    state = _state(
        symptoms=["fatigue"],
        clinical_signals=ClinicalSignals(
            symptoms=["fatigue"],
            duration="1 month",
            severity="mild",
            ambiguity_notes=["vague, contradictory description"],
        ),
        search_decision_reason=str(SearchDecision.SEARCH_RARE_OR_UNKNOWN),
    )
    score, applied = ConfidenceScorer().score(state)
    # 40 +15(symptoms) +10(clear) -15(ambiguous) -10(contradictory) -10(rare) = 30
    assert score == 30
    assert "ambiguous_wording:-15" in applied
    assert "contradictory_symptoms:-10" in applied
    assert "rare_presentation:-10" in applied


def test_score_is_deterministic_and_integer() -> None:
    state = _state(symptoms=["cough"])
    scorer = ConfidenceScorer()
    first, _ = scorer.score(state)
    second, _ = scorer.score(state)
    assert first == second
    assert isinstance(first, int)
    assert 0 <= first <= 100
