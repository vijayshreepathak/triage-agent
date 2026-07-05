"""Execution trace and error models.

Every node execution — success or failure — produces exactly one
``NodeTrace``. This gives the /debug endpoint and structured logs a full,
ordered picture of the graph run: which nodes ran, which were skipped,
how long each took, and what went wrong.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NodeStatus


class NodeError(BaseModel):
    """A single node-level error. User-safe by construction.

    ``root_cause`` is logged server-side but never serialized into the API
    response — only ``user_safe_message`` crosses the HTTP boundary.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: str
    node_name: str
    error_type: str = Field(description="Exception class name or domain error code.")
    root_cause: str = Field(description="Internal detail for logs. Never exposed to clients.")
    user_safe_message: str = Field(description="What (if anything) the client may see.")


class NodeTrace(BaseModel):
    """Timing and outcome record for one node execution."""

    model_config = ConfigDict(frozen=True)

    node_name: str
    started_at: datetime
    finished_at: datetime
    latency_ms: float = Field(ge=0.0)
    status: NodeStatus
    result_summary: str = Field(
        default="", description="One-line, non-sensitive summary of what the node produced."
    )
    retry_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(
        default_factory=list, description="Error type names only; details live in NodeError/logs."
    )
