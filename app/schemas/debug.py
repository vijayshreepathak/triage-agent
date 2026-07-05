"""Debug endpoint contract.

Exposes the execution trace and USER-SAFE error fields only — ``root_cause``
never crosses the HTTP boundary even in debug mode, because debug endpoints
have a way of ending up reachable in production.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.triage import TriageResponse


class NodeTraceOut(BaseModel):
    """One node execution, as exposed by POST /debug."""

    node_name: str
    latency_ms: float
    status: str
    result_summary: str
    retry_count: int
    errors: list[str]


class NodeErrorOut(BaseModel):
    """User-safe projection of a NodeError (no root cause, no stack)."""

    timestamp: datetime
    node_name: str
    error_type: str
    user_safe_message: str


class DebugResponse(BaseModel):
    """POST /debug response: the triage result plus full observability data."""

    triage: TriageResponse
    search_decision_reason: str | None
    search_query: str | None
    execution_trace: list[NodeTraceOut] = Field(default_factory=list)
    errors: list[NodeErrorOut] = Field(default_factory=list)
    metadata: dict[str, str | int | float] = Field(default_factory=dict)
