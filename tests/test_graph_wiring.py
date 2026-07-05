"""Graph wiring tests — Phase 2.

These tests use stub nodes (no LLM, no search, no network) to verify the
orchestration layer in isolation:

1. the linear spine executes in the declared order,
2. the conditional edge takes the search branch when needs_search=True,
3. the conditional edge skips search when needs_search=False,
4. trace entries accumulate additively (reducer behavior),
5. the runner never raises, even when a node explodes.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.graph.builder import NodeBundle, build_triage_graph
from app.graph.node_names import NodeName
from app.graph.runner import TriageGraphRunner
from app.models.state import GraphState
from app.utils.timing import traced_node


def _stub(node_name: str, update: dict[str, Any] | None = None) -> Any:
    """Build a traced stub node that records its visit in state metadata."""

    @traced_node(node_name)
    async def node(state: GraphState) -> dict[str, Any]:
        visited = dict(state.metadata)
        order = str(visited.get("visit_order", ""))
        visited["visit_order"] = f"{order}>{node_name}" if order else node_name
        return {"metadata": visited, **(update or {})}

    return node


def _bundle(*, needs_search: bool, failing_node: str | None = None) -> NodeBundle:
    """Assemble a stub bundle; optionally make one node raise."""

    def make(name: str, update: dict[str, Any] | None = None) -> Any:
        if name == failing_node:

            @traced_node(name)
            async def exploding(state: GraphState) -> dict[str, Any]:
                raise RuntimeError("boom")

            return exploding
        return _stub(name, update)

    return NodeBundle(
        parse_input=make(NodeName.PARSE_INPUT),
        extract_clinical_signals=make(NodeName.EXTRACT_SIGNALS),
        normalize_symptoms=make(NodeName.NORMALIZE_SYMPTOMS),
        red_flag_detection=make(NodeName.RED_FLAG_DETECTION),
        urgency_classification=make(NodeName.URGENCY_CLASSIFICATION),
        search_decision=make(NodeName.SEARCH_DECISION, {"needs_search": needs_search}),
        search_medical_sources=make(NodeName.SEARCH_MEDICAL_SOURCES),
        merge_evidence=make(NodeName.MERGE_EVIDENCE),
        generate_clinical_explanation=make(NodeName.GENERATE_EXPLANATION),
        confidence_scoring=make(NodeName.CONFIDENCE_SCORING),
        build_structured_response=make(NodeName.BUILD_RESPONSE),
    )


async def _run(bundle: NodeBundle) -> GraphState:
    runner = TriageGraphRunner(build_triage_graph(bundle))
    return await runner.run(patient_id="case_test", patient_message="test message", request_id="req-1")


@pytest.mark.asyncio
async def test_search_branch_taken_when_needed() -> None:
    state = await _run(_bundle(needs_search=True))
    order = str(state.metadata["visit_order"]).split(">")
    assert NodeName.SEARCH_MEDICAL_SOURCES in order
    assert order.index(NodeName.SEARCH_MEDICAL_SOURCES) < order.index(NodeName.MERGE_EVIDENCE)
    assert len(state.execution_trace) == 11  # all nodes ran


@pytest.mark.asyncio
async def test_search_branch_skipped_when_not_needed() -> None:
    state = await _run(_bundle(needs_search=False))
    order = str(state.metadata["visit_order"]).split(">")
    assert NodeName.SEARCH_MEDICAL_SOURCES not in order
    assert len(state.execution_trace) == 10  # search node skipped

    expected_spine = [
        NodeName.PARSE_INPUT,
        NodeName.EXTRACT_SIGNALS,
        NodeName.NORMALIZE_SYMPTOMS,
        NodeName.RED_FLAG_DETECTION,
        NodeName.URGENCY_CLASSIFICATION,
        NodeName.SEARCH_DECISION,
        NodeName.MERGE_EVIDENCE,
        NodeName.GENERATE_EXPLANATION,
        NodeName.CONFIDENCE_SCORING,
        NodeName.BUILD_RESPONSE,
    ]
    assert order == [str(n) for n in expected_spine]


@pytest.mark.asyncio
async def test_trace_entries_have_latency_and_status() -> None:
    state = await _run(_bundle(needs_search=False))
    assert all(t.latency_ms >= 0 for t in state.execution_trace)
    assert {t.node_name for t in state.execution_trace} == {
        str(n) for n in NodeName if n != NodeName.SEARCH_MEDICAL_SOURCES
    }


@pytest.mark.asyncio
async def test_node_failure_does_not_crash_graph() -> None:
    state = await _run(_bundle(needs_search=False, failing_node=str(NodeName.URGENCY_CLASSIFICATION)))
    # Graph completed to the end despite the failure...
    assert any(t.node_name == str(NodeName.BUILD_RESPONSE) for t in state.execution_trace)
    # ...the failure is recorded, user-safe, with no stack trace leakage.
    assert len(state.errors) == 1
    assert state.errors[0].node_name == str(NodeName.URGENCY_CLASSIFICATION)
    assert "boom" not in state.errors[0].user_safe_message


@pytest.mark.asyncio
async def test_runner_survives_orchestration_failure() -> None:
    class ExplodingGraph:
        async def ainvoke(self, _state: GraphState) -> dict[str, Any]:
            raise RuntimeError("orchestration bug")

    runner = TriageGraphRunner(ExplodingGraph())  # type: ignore[arg-type]
    state = await runner.run(patient_id="p", patient_message="m", request_id="r")
    assert state.errors[0].node_name == "graph_runner"
    assert "graph_latency_ms" in state.metadata
