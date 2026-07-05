"""In-process metrics registry (Phase 7 observability).

One registry instance lives for the app's lifetime and aggregates:
requests, errors, retries, search usage, per-node latency, graph latency,
token usage, and estimated cost. Exposed via GET /metrics as JSON —
deliberately provider-agnostic (a Prometheus exporter would consume the
same snapshot; swapping the transport requires no changes here).

Thread-safe via a plain lock: cheap, and correct even if the app is ever
run with multiple event-loop workers in one process.
"""

from __future__ import annotations

import threading
from collections import defaultdict

from app.models.state import GraphState
from app.tools.interfaces import LLMResult

_TOKENS_PER_MILLION = 1_000_000


class _LatencyAggregate:
    """Streaming count/sum/max — enough for an ops dashboard without histograms."""

    __slots__ = ("count", "max_ms", "total_ms")

    def __init__(self) -> None:
        self.count = 0
        self.total_ms = 0.0
        self.max_ms = 0.0

    def observe(self, latency_ms: float) -> None:
        self.count += 1
        self.total_ms += latency_ms
        self.max_ms = max(self.max_ms, latency_ms)

    def snapshot(self) -> dict[str, float]:
        avg = self.total_ms / self.count if self.count else 0.0
        return {"count": self.count, "avg_ms": round(avg, 2), "max_ms": round(self.max_ms, 2)}


class MetricsRegistry:
    """Aggregates run- and LLM-level metrics for the /metrics endpoint."""

    def __init__(
        self,
        *,
        cost_per_1m_prompt_tokens: float = 0.0,
        cost_per_1m_completion_tokens: float = 0.0,
    ) -> None:
        self._lock = threading.Lock()
        self._cost_prompt = cost_per_1m_prompt_tokens
        self._cost_completion = cost_per_1m_completion_tokens

        self._requests_total = 0
        self._errors_total = 0
        self._retries_total = 0
        self._searches_total = 0
        self._searches_skipped_total = 0
        self._degraded_runs_total = 0

        self._graph_latency = _LatencyAggregate()
        self._node_latency: dict[str, _LatencyAggregate] = defaultdict(_LatencyAggregate)

        self._prompt_tokens_total = 0
        self._completion_tokens_total = 0
        self._llm_calls_total = 0

    def record_run(self, state: GraphState) -> None:
        """Fold one completed graph run into the aggregates."""
        with self._lock:
            self._requests_total += 1
            self._errors_total += len(state.errors)
            if state.needs_search:
                self._searches_total += 1
            else:
                self._searches_skipped_total += 1
            if state.errors:
                self._degraded_runs_total += 1

            graph_latency = state.metadata.get("graph_latency_ms")
            if isinstance(graph_latency, (int, float)):
                self._graph_latency.observe(float(graph_latency))

            for trace in state.execution_trace:
                self._node_latency[trace.node_name].observe(trace.latency_ms)
                self._retries_total += trace.retry_count

    def record_llm_usage(self, result: LLMResult) -> None:
        """Record token usage from one LLM completion (called by adapters)."""
        with self._lock:
            self._llm_calls_total += 1
            self._prompt_tokens_total += result.prompt_tokens
            self._completion_tokens_total += result.completion_tokens

    def snapshot(self) -> dict[str, object]:
        """Point-in-time export for GET /metrics."""
        with self._lock:
            estimated_cost = (
                self._prompt_tokens_total / _TOKENS_PER_MILLION * self._cost_prompt
                + self._completion_tokens_total / _TOKENS_PER_MILLION * self._cost_completion
            )
            return {
                "requests_total": self._requests_total,
                "errors_total": self._errors_total,
                "degraded_runs_total": self._degraded_runs_total,
                "retries_total": self._retries_total,
                "searches_total": self._searches_total,
                "searches_skipped_total": self._searches_skipped_total,
                "graph_latency_ms": self._graph_latency.snapshot(),
                "node_latency_ms": {name: agg.snapshot() for name, agg in self._node_latency.items()},
                "llm": {
                    "calls_total": self._llm_calls_total,
                    "prompt_tokens_total": self._prompt_tokens_total,
                    "completion_tokens_total": self._completion_tokens_total,
                    "estimated_cost_usd": round(estimated_cost, 6),
                },
            }
