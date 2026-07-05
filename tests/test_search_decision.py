"""Unit tests for the deterministic search decision ladder."""

from __future__ import annotations

import pytest

from app.models.clinical import ClinicalSignals, UrgencyAssessment
from app.models.enums import SearchDecision
from app.models.state import GraphState
from app.nodes.search_decision import make_search_decision_node

_SIGNALS = ClinicalSignals(symptoms=["cough"], duration="2 weeks", severity="mild")


def _state(**overrides: object) -> GraphState:
    base: dict[str, object] = {
        "patient_id": "p",
        "patient_message": "msg",
        "request_id": "req",
        "normalized_message": "msg",
        "symptoms": ["cough"],
        "clinical_signals": _SIGNALS,
    }
    base.update(overrides)
    return GraphState.model_validate(base)


def _urgency(level: str) -> UrgencyAssessment:
    return UrgencyAssessment(urgency=level, reason="r", supporting_signals=[])


@pytest.mark.asyncio
async def test_emergency_always_skips_search() -> None:
    update = await make_search_decision_node()(_state(urgency=_urgency("emergency")))
    assert update["needs_search"] is False
    assert update["search_decision_reason"] == str(SearchDecision.SKIP_EMERGENCY)
    assert update["search_query"] is None


@pytest.mark.asyncio
async def test_missing_signals_triggers_rare_unknown_search() -> None:
    update = await make_search_decision_node()(
        _state(clinical_signals=None, symptoms=[], urgency=_urgency("moderate"))
    )
    assert update["needs_search"] is True
    assert update["search_decision_reason"] == str(SearchDecision.SEARCH_RARE_OR_UNKNOWN)


@pytest.mark.asyncio
async def test_medication_cue_triggers_search() -> None:
    update = await make_search_decision_node()(
        _state(urgency=_urgency("low"), normalized_message="is there an interaction between my tablets?")
    )
    assert update["needs_search"] is True
    assert update["search_decision_reason"] == str(SearchDecision.SEARCH_MEDICATION_QUESTION)


@pytest.mark.asyncio
async def test_ambiguous_signals_trigger_borderline_search() -> None:
    signals = ClinicalSignals(symptoms=["fatigue"], ambiguity_notes=["very vague"])
    update = await make_search_decision_node()(
        _state(clinical_signals=signals, symptoms=["fatigue"], urgency=_urgency("low"))
    )
    assert update["needs_search"] is True
    assert update["search_decision_reason"] == str(SearchDecision.SEARCH_BORDERLINE)


@pytest.mark.asyncio
async def test_moderate_urgency_searches_low_clear_case_skips() -> None:
    moderate = await make_search_decision_node()(_state(urgency=_urgency("moderate")))
    assert moderate["needs_search"] is True

    low = await make_search_decision_node()(_state(urgency=_urgency("low")))
    assert low["needs_search"] is False
    assert low["search_decision_reason"] == str(SearchDecision.SKIP_COMMON_PRESENTATION)


@pytest.mark.asyncio
async def test_query_includes_symptoms_and_demographics() -> None:
    signals = ClinicalSignals(symptoms=["rash"], is_pregnant=True, age=31)
    update = await make_search_decision_node()(
        _state(clinical_signals=signals, symptoms=["rash"], urgency=_urgency("moderate"))
    )
    query = update["search_query"]
    assert "rash" in query
    assert "during pregnancy" in query
    assert "age 31" in query
