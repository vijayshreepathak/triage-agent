"""Triage graph construction.

Design decisions:

1. **Dependency injection of nodes.** ``build_triage_graph`` receives a
   ``NodeBundle`` — a frozen container of node callables — instead of
   importing node modules directly. Consequences:
   - The graph layer has zero knowledge of LLMs, search tools, or prompts.
   - Wiring is testable today with stub nodes (no API keys, no network).
   - Swapping a node (e.g. an MCP-backed search node later) is a change to
     the bundle factory, not to the graph.

2. **Topology mirrors the spec exactly** — one straight spine with a single
   conditional branch after ``search_decision``:

       START -> parse_input -> extract_clinical_signals -> normalize_symptoms
             -> red_flag_detection -> urgency_classification -> search_decision
             -> [needs_search?] -> search_medical_sources -> merge_evidence
                              \\-> merge_evidence
             -> generate_clinical_explanation -> confidence_scoring
             -> build_structured_response -> END

   ``merge_evidence`` is the join point of both branches, so downstream
   nodes never care whether search happened — they read grounded_sources,
   which is simply empty when search was skipped.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.node_names import NodeName
from app.graph.routing import route_after_search_decision
from app.models.state import GraphState

# A node consumes validated state and returns a partial update dict.
NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class NodeBundle:
    """All node implementations the graph needs, injected as one unit.

    Frozen dataclass rather than a dict so a missing node is a construction
    error (fail fast at startup), not a KeyError mid-request.
    """

    parse_input: NodeFn
    extract_clinical_signals: NodeFn
    normalize_symptoms: NodeFn
    red_flag_detection: NodeFn
    urgency_classification: NodeFn
    search_decision: NodeFn
    search_medical_sources: NodeFn
    merge_evidence: NodeFn
    generate_clinical_explanation: NodeFn
    confidence_scoring: NodeFn
    build_structured_response: NodeFn


def build_triage_graph(nodes: NodeBundle) -> CompiledStateGraph:
    """Wire and compile the triage StateGraph.

    Args:
        nodes: Injected node implementations (real or test stubs).

    Returns:
        A compiled, immutable graph ready for ``ainvoke``.
    """
    graph: StateGraph = StateGraph(GraphState)

    graph.add_node(NodeName.PARSE_INPUT, nodes.parse_input)
    graph.add_node(NodeName.EXTRACT_SIGNALS, nodes.extract_clinical_signals)
    graph.add_node(NodeName.NORMALIZE_SYMPTOMS, nodes.normalize_symptoms)
    graph.add_node(NodeName.RED_FLAG_DETECTION, nodes.red_flag_detection)
    graph.add_node(NodeName.URGENCY_CLASSIFICATION, nodes.urgency_classification)
    graph.add_node(NodeName.SEARCH_DECISION, nodes.search_decision)
    graph.add_node(NodeName.SEARCH_MEDICAL_SOURCES, nodes.search_medical_sources)
    graph.add_node(NodeName.MERGE_EVIDENCE, nodes.merge_evidence)
    graph.add_node(NodeName.GENERATE_EXPLANATION, nodes.generate_clinical_explanation)
    graph.add_node(NodeName.CONFIDENCE_SCORING, nodes.confidence_scoring)
    graph.add_node(NodeName.BUILD_RESPONSE, nodes.build_structured_response)

    # Linear spine up to the branch point.
    graph.add_edge(START, NodeName.PARSE_INPUT)
    graph.add_edge(NodeName.PARSE_INPUT, NodeName.EXTRACT_SIGNALS)
    graph.add_edge(NodeName.EXTRACT_SIGNALS, NodeName.NORMALIZE_SYMPTOMS)
    graph.add_edge(NodeName.NORMALIZE_SYMPTOMS, NodeName.RED_FLAG_DETECTION)
    graph.add_edge(NodeName.RED_FLAG_DETECTION, NodeName.URGENCY_CLASSIFICATION)
    graph.add_edge(NodeName.URGENCY_CLASSIFICATION, NodeName.SEARCH_DECISION)

    # The single conditional edge: search selectively, never by default.
    graph.add_conditional_edges(
        NodeName.SEARCH_DECISION,
        route_after_search_decision,
        {
            NodeName.SEARCH_MEDICAL_SOURCES: NodeName.SEARCH_MEDICAL_SOURCES,
            NodeName.MERGE_EVIDENCE: NodeName.MERGE_EVIDENCE,
        },
    )
    graph.add_edge(NodeName.SEARCH_MEDICAL_SOURCES, NodeName.MERGE_EVIDENCE)

    # Join point onward: identical path regardless of the search branch.
    graph.add_edge(NodeName.MERGE_EVIDENCE, NodeName.GENERATE_EXPLANATION)
    graph.add_edge(NodeName.GENERATE_EXPLANATION, NodeName.CONFIDENCE_SCORING)
    graph.add_edge(NodeName.CONFIDENCE_SCORING, NodeName.BUILD_RESPONSE)
    graph.add_edge(NodeName.BUILD_RESPONSE, END)

    return graph.compile()
