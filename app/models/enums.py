"""Closed vocabularies used across the system.

Enums (not free strings) so that invalid values fail at validation time,
not at runtime deep inside a node. The LLM output is coerced into these
enums; anything outside the vocabulary is rejected and retried.
"""

from __future__ import annotations

from enum import StrEnum


class UrgencyLevel(StrEnum):
    """The only four urgency levels the system may ever emit.

    Safety note: ordering matters — comparisons use ``URGENCY_RANK`` below,
    and escalation logic always moves toward EMERGENCY, never away from it.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EMERGENCY = "emergency"


URGENCY_RANK: dict[UrgencyLevel, int] = {
    UrgencyLevel.LOW: 0,
    UrgencyLevel.MODERATE: 1,
    UrgencyLevel.HIGH: 2,
    UrgencyLevel.EMERGENCY: 3,
}


class NodeStatus(StrEnum):
    """Outcome envelope for every node execution.

    The graph never crashes: nodes report one of these statuses and the
    orchestrator decides whether to continue, retry, or short-circuit to a
    safe response.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    RECOVERABLE_ERROR = "recoverable_error"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"


class SearchDecision(StrEnum):
    """Why the search node ran or was skipped. Logged for auditability."""

    SKIP_EMERGENCY = "skip_emergency_time_critical"
    SKIP_COMMON_PRESENTATION = "skip_common_presentation"
    SEARCH_RARE_OR_UNKNOWN = "search_rare_or_unknown_presentation"
    SEARCH_MEDICATION_QUESTION = "search_medication_question"
    SEARCH_BORDERLINE = "search_borderline_ambiguous"


class LLMProvider(StrEnum):
    """Supported LLM backends (Factory pattern in ``tools/llm``)."""

    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OPENROUTER = "openrouter"


class SearchProvider(StrEnum):
    """Supported search backends (Strategy pattern in ``tools/search``)."""

    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    MCP = "mcp"
    NONE = "none"
