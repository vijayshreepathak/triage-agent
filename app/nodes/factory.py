"""Node bundle factory — the composition root for graph logic.

The ONLY place where nodes meet their dependencies. Given the two external
tools (LLM client and search tool, both as Protocols) plus settings, it
assembles the full ``NodeBundle`` the graph builder consumes.

Swap-ability in practice:
- different LLM provider  -> pass a different LLMClient, nothing else changes
- MCP-backed search       -> pass an MCP SearchTool adapter, nothing else changes
- unit tests              -> pass fakes, get a fully offline graph
"""

from __future__ import annotations

from app.config.settings import Settings
from app.graph.builder import NodeBundle
from app.nodes.build_response import make_build_response_node
from app.nodes.confidence_scoring import make_confidence_scoring_node
from app.nodes.extract_signals import make_extract_signals_node
from app.nodes.generate_explanation import make_generate_explanation_node
from app.nodes.merge_evidence import make_merge_evidence_node
from app.nodes.normalize_symptoms import make_normalize_symptoms_node
from app.nodes.parse_input import make_parse_input_node
from app.nodes.red_flag_detection import make_red_flag_detection_node
from app.nodes.search_decision import make_search_decision_node
from app.nodes.search_medical_sources import make_search_medical_sources_node
from app.nodes.urgency_classification import make_urgency_classification_node
from app.services.confidence_scorer import ConfidenceScorer
from app.services.red_flag_engine import RedFlagEngine
from app.services.structured_llm import StructuredLLMCaller
from app.tools.interfaces import LLMClient, SearchTool


def build_node_bundle(*, llm: LLMClient, search_tool: SearchTool, settings: Settings) -> NodeBundle:
    """Wire all nodes with their dependencies and return the bundle."""
    caller = StructuredLLMCaller(llm)
    engine = RedFlagEngine()
    scorer = ConfidenceScorer()

    return NodeBundle(
        parse_input=make_parse_input_node(),
        extract_clinical_signals=make_extract_signals_node(caller),
        normalize_symptoms=make_normalize_symptoms_node(),
        red_flag_detection=make_red_flag_detection_node(engine, caller),
        urgency_classification=make_urgency_classification_node(caller, engine),
        search_decision=make_search_decision_node(),
        search_medical_sources=make_search_medical_sources_node(search_tool, settings),
        merge_evidence=make_merge_evidence_node(),
        generate_clinical_explanation=make_generate_explanation_node(caller),
        confidence_scoring=make_confidence_scoring_node(scorer),
        build_structured_response=make_build_response_node(),
    )
