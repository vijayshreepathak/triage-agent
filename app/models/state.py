"""GraphState — the single shared state flowing through the LangGraph.

Design decisions:

1. Pydantic model (not a plain TypedDict) so that every node write is
   validated. A node that tries to set ``urgency="critical"`` fails loudly
   at the node boundary instead of corrupting downstream logic.

2. Nodes return *partial updates* (dicts containing only the fields they
   own). LangGraph merges them into the state. This enforces the rule
   "never mutate unrelated fields" structurally: a node physically cannot
   clobber a field it does not return.

3. ``execution_trace`` uses an additive reducer so every node appends its
   own trace entry without reading or rewriting previous entries.
"""

from __future__ import annotations

import operator
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.clinical import (
    ClinicalSignals,
    GroundedSource,
    RedFlag,
    SearchResult,
    UrgencyAssessment,
)
from app.models.trace import NodeError, NodeTrace


class GraphState(BaseModel):
    """Complete state of one triage request as it flows through the graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- Input (set once by the API layer, read-only afterwards) ---
    patient_id: str
    patient_message: str
    request_id: str = Field(description="Correlates logs, traces and the HTTP response.")

    # --- Parse / extraction ---
    normalized_message: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    clinical_signals: ClinicalSignals | None = None

    # --- Safety ---
    red_flags: list[RedFlag] = Field(default_factory=list)
    red_flag_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # --- Classification ---
    urgency: UrgencyAssessment | None = None

    # --- Search (conditional branch) ---
    needs_search: bool = False
    search_decision_reason: str | None = None
    search_query: str | None = None
    search_results: list[SearchResult] = Field(default_factory=list)
    grounded_sources: list[GroundedSource] = Field(default_factory=list)

    # --- Synthesis ---
    clinical_reasoning: str | None = Field(
        default=None,
        description="Short user-facing explanation (<=100 words). Never chain-of-thought.",
    )
    confidence: int | None = Field(default=None, ge=0, le=100)
    recommended_action: str | None = None
    disclaimer: list[str] = Field(default_factory=list)

    # --- Observability (append-only reducers: nodes add, never rewrite) ---
    errors: Annotated[list[NodeError], operator.add] = Field(default_factory=list)
    execution_trace: Annotated[list[NodeTrace], operator.add] = Field(default_factory=list)
    metadata: dict[str, str | int | float] = Field(default_factory=dict)
