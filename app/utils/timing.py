"""Node timing decorator — the single place execution traces are produced.

Every graph node is wrapped with ``@traced_node``. The decorator:

1. Records start/finish timestamps and latency with a monotonic clock.
2. Logs node entry/exit as structured JSON (node transitions requirement).
3. Converts *any* uncaught exception into a NodeError + FATAL trace entry
   instead of crashing the graph — the "graph never crashes" guarantee is
   enforced here once, not re-implemented in every node.

Nodes therefore contain only domain logic and return partial state updates;
observability and crash-safety are composed in, not inherited.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from app.models.enums import NodeStatus
from app.models.state import GraphState
from app.models.trace import NodeError, NodeTrace
from app.utils.logging import get_logger

logger = get_logger(__name__)

NodeFunc = Callable[[GraphState], Awaitable[dict[str, Any]]]


def traced_node(node_name: str) -> Callable[[NodeFunc], NodeFunc]:
    """Wrap a graph node with timing, logging, and crash containment.

    The wrapped node must return a partial-state dict. On success the
    decorator appends a SUCCESS NodeTrace; on unhandled exception it
    swallows the error into ``errors`` + a FATAL_ERROR trace so downstream
    nodes (and ultimately the safe response builder) still run.
    """

    def decorator(func: NodeFunc) -> NodeFunc:
        @wraps(func)
        async def wrapper(state: GraphState) -> dict[str, Any]:
            started_at = datetime.now(UTC)
            start = time.perf_counter()
            logger.info("node started", extra={"node": node_name})
            try:
                update = await func(state)
                latency_ms = (time.perf_counter() - start) * 1000
                trace = NodeTrace(
                    node_name=node_name,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    latency_ms=latency_ms,
                    status=NodeStatus(update.pop("_status", NodeStatus.SUCCESS)),
                    result_summary=str(update.pop("_result_summary", "")),
                    retry_count=int(update.pop("_retry_count", 0)),
                )
                logger.info(
                    "node finished",
                    extra={"node": node_name, "latency_ms": round(latency_ms, 2), "status": trace.status},
                )
                update["execution_trace"] = [trace]
                return update
            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "node failed",
                    extra={"node": node_name, "latency_ms": round(latency_ms, 2), "error": repr(exc)},
                    exc_info=True,
                )
                error = NodeError(
                    request_id=state.request_id,
                    node_name=node_name,
                    error_type=type(exc).__name__,
                    root_cause=str(exc),
                    user_safe_message="An internal step failed; results may be partial.",
                )
                trace = NodeTrace(
                    node_name=node_name,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    latency_ms=latency_ms,
                    status=NodeStatus.FATAL_ERROR,
                    errors=[type(exc).__name__],
                )
                return {"errors": [error], "execution_trace": [trace]}

        return wrapper

    return decorator
