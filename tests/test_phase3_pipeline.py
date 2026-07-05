"""Phase 3 end-to-end pipeline tests with fakes (no network).

Two canonical scenarios from the dataset:
1. case_001-style emergency (crushing chest pain) — search must be SKIPPED,
   urgency must be emergency, disclaimer + red flags present.
2. case_088-style ambiguous presentation (tremor + swallowing trouble) —
   search must RUN, sources must be grounded verbatim, confidence lower.
Plus degradation: LLM down entirely -> safe, escalated, disclaimer intact.
"""

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.graph.builder import build_triage_graph
from app.graph.node_names import NodeName
from app.graph.runner import TriageGraphRunner
from app.models.clinical import SearchResult
from app.models.enums import SearchDecision, UrgencyLevel
from app.models.state import GraphState
from app.nodes.factory import build_node_bundle
from tests.fakes import FakeLLM, FakeSearchTool

# Markers present in each prompt's system text.
EXTRACTION = "clinical signal extraction"
RED_FLAGS = "red flag detection"
URGENCY = "urgency classification"
EXPLANATION = "explanation of a triage decision"

SETTINGS = Settings(search_min_relevance=0.5, search_max_results=4)


def _runner(llm: FakeLLM, search: FakeSearchTool) -> TriageGraphRunner:
    bundle = build_node_bundle(llm=llm, search_tool=search, settings=SETTINGS)
    return TriageGraphRunner(build_triage_graph(bundle))


async def _run(runner: TriageGraphRunner, patient_id: str, message: str) -> GraphState:
    return await runner.run(patient_id=patient_id, patient_message=message, request_id="req-test")


@pytest.mark.asyncio
async def test_emergency_case_skips_search_and_escalates() -> None:
    llm = FakeLLM(
        {
            EXTRACTION: {
                "symptoms": ["chest pain", "sweating", "nausea"],
                "duration": "20 minutes",
                "severity": "crushing",
                "onset": "sudden",
                "radiation": "to left arm",
                "age": None,
                "is_pregnant": None,
                "medical_history": [],
                "medications": [],
                "allergies": [],
                "affects_child": False,
                "ambiguity_notes": [],
            },
            RED_FLAGS: {"red_flags": ["possible myocardial infarction presentation"]},
            URGENCY: {
                "urgency": "emergency",
                "reason": "Classic acute coronary syndrome red flags.",
                "supporting_signals": ["chest pain", "radiation to left arm", "diaphoresis"],
            },
            EXPLANATION: {
                "explanation": "Your symptoms — crushing chest pain radiating to the left arm with sweating — match warning signs that need immediate emergency care."
            },
        }
    )
    search = FakeSearchTool()
    state = await _run(
        _runner(llm, search),
        "case_001",
        "I've been having crushing chest pain for the past 20 minutes that radiates to my left arm. "
        "I'm sweating a lot and feel nauseous.",
    )

    assert state.urgency is not None and state.urgency.urgency == UrgencyLevel.EMERGENCY
    assert state.needs_search is False
    assert state.search_decision_reason == str(SearchDecision.SKIP_EMERGENCY)
    assert search.queries == []  # search tool never touched
    assert any(f.source == "rule" for f in state.red_flags)  # deterministic engine fired
    assert state.disclaimer  # hardcoded disclaimer present
    assert state.confidence is not None and state.confidence >= 70  # strong deterministic evidence
    assert "chest pain" in state.symptoms


@pytest.mark.asyncio
async def test_ambiguous_case_searches_and_grounds_sources() -> None:
    llm = FakeLLM(
        {
            EXTRACTION: {
                "symptoms": ["hand tremor", "difficulty swallowing"],
                "duration": "2 weeks",
                "severity": None,
                "onset": "gradual",
                "radiation": None,
                "age": 58,
                "is_pregnant": None,
                "medical_history": [],
                "medications": [],
                "allergies": [],
                "affects_child": False,
                "ambiguity_notes": ["unusual symptom combination, cause unclear"],
            },
            RED_FLAGS: {"red_flags": []},
            URGENCY: {
                "urgency": "moderate",
                "reason": "Progressive neurological symptoms warrant assessment.",
                "supporting_signals": ["tremor", "dysphagia"],
            },
            EXPLANATION: {
                "explanation": "A gradually worsening tremor with occasional swallowing difficulty can be associated with several neurological conditions and should be assessed by a doctor soon."
            },
        }
    )
    search = FakeSearchTool(
        results=[
            SearchResult(
                title="Tremor - NHS",
                summary="Overview of tremor causes.",
                url="https://www.nhs.uk/conditions/tremor",
                relevance=0.9,
            ),
            SearchResult(
                title="Low quality blog", summary="???", url="https://spam.example.com", relevance=0.2
            ),
        ]
    )
    state = await _run(
        _runner(llm, search), "case_088", "My hands tremble and I sometimes struggle to swallow solids."
    )

    assert state.needs_search is True
    assert len(search.queries) == 1
    assert "hand tremor" in search.queries[0]
    # Relevance filter dropped the 0.2 result; grounded source URL is verbatim.
    assert [s.url for s in state.grounded_sources] == ["https://www.nhs.uk/conditions/tremor"]
    assert state.urgency is not None and state.urgency.urgency == UrgencyLevel.MODERATE
    # Ambiguity penalty applied -> lower confidence than the clear emergency case.
    assert state.confidence is not None and state.confidence < 70


@pytest.mark.asyncio
async def test_total_llm_failure_degrades_safely() -> None:
    class DeadLLM:
        async def complete(self, *, system: str, user: str):  # noqa: ANN202
            raise ConnectionError("provider down")

    search = FakeSearchTool()
    bundle = build_node_bundle(llm=DeadLLM(), search_tool=search, settings=SETTINGS)
    runner = TriageGraphRunner(build_triage_graph(bundle))
    state = await runner.run(
        patient_id="case_003",
        patient_message="My face feels droopy on the left side and I'm having trouble speaking clearly.",
        request_id="req-dead",
    )

    # Deterministic stroke rule fired even with the LLM completely down...
    assert any("stroke" in f.name for f in state.red_flags)
    # ...and the fallback classification escalated to emergency, never low.
    assert state.urgency is not None and state.urgency.urgency == UrgencyLevel.EMERGENCY
    # Full contract still satisfied: reasoning, action, disclaimer, low confidence.
    assert state.clinical_reasoning
    assert state.recommended_action
    assert state.disclaimer
    assert state.confidence is not None and state.confidence <= 60
    # Graph reached the end.
    assert any(t.node_name == str(NodeName.BUILD_RESPONSE) for t in state.execution_trace)
