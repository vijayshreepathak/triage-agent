"""Graph execution service.

The runner is the only object the API layer talks to (routes call
``runner.run(...)`` and nothing else). It owns request-scoped concerns
that don't belong in any single node:

- generating the ``graph_execution_id`` and binding logging contextvars,
- constructing the initial GraphState,
- timing the whole graph run,
- the last-resort catch: if the graph itself fails (not a node — nodes
  contain their own failures via ``@traced_node``), the runner returns a
  degraded-but-valid state instead of raising, honoring the
  "never crash, never expose stack traces" contract.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from langgraph.graph.state import CompiledStateGraph

from app.models.state import GraphState
from app.models.trace import NodeError
from app.utils.logging import (
    get_logger,
    graph_execution_id_var,
    patient_id_var,
    request_id_var,
)

logger = get_logger(__name__)


class TriageGraphRunner:
    """Executes the compiled triage graph for one request at a time.

    Stateless between calls — safe to share a single instance across all
    requests (it is wired once at app startup and injected into routes).
    """

    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph

    async def run(self, *, patient_id: str, patient_message: str, request_id: str) -> GraphState:
        """Run the full triage graph and return the final validated state.

        Never raises: any orchestration-level failure is folded into the
        returned state's ``errors`` so the API layer can still produce a
        safe, disclaimer-bearing response.
        """
        graph_execution_id = uuid.uuid4().hex
        request_id_var.set(request_id)
        patient_id_var.set(patient_id)
        graph_execution_id_var.set(graph_execution_id)

        initial_state = GraphState(
            patient_id=patient_id,
            patient_message=patient_message,
            request_id=request_id,
            metadata={"graph_execution_id": graph_execution_id},
        )

        logger.info("graph execution started", extra={"message_length": len(patient_message)})
        start = time.perf_counter()
        try:
            raw_final = await self._graph.ainvoke(initial_state)
            # ainvoke returns a plain dict of state values; re-validate into
            # GraphState so downstream code keeps full type safety.
            final_state = GraphState.model_validate(raw_final)
        except Exception as exc:
            # Node-level failures never reach here (traced_node contains them);
            # this guards orchestration bugs and state-validation failures.
            logger.error("graph execution failed", extra={"error": repr(exc)}, exc_info=True)
            final_state = initial_state.model_copy(
                update={
                    "errors": [
                        NodeError(
                            timestamp=datetime.now(UTC),
                            request_id=request_id,
                            node_name="graph_runner",
                            error_type=type(exc).__name__,
                            root_cause=str(exc),
                            user_safe_message="Triage could not be completed. If symptoms are severe, seek emergency care.",
                        )
                    ],
                }
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        final_state.metadata["graph_latency_ms"] = round(elapsed_ms, 2)
        logger.info(
            "graph execution finished",
            extra={
                "graph_latency_ms": round(elapsed_ms, 2),
                "nodes_executed": len(final_state.execution_trace),
                "error_count": len(final_state.errors),
                "needs_search": final_state.needs_search,
            },
        )
        return final_state
