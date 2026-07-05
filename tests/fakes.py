"""Shared test doubles. No network, no API keys, fully deterministic.

The FakeLLM dispatches on stable markers in each prompt's system text —
the same mechanism a canned-response cache would use — so tests exercise
the real prompt->parse->validate path without a provider.
"""

from __future__ import annotations

import json

from app.models.clinical import SearchResult
from app.tools.interfaces import LLMResult


class FakeLLM:
    """Returns canned JSON per prompt type; records every call for assertions."""

    def __init__(self, responses: dict[str, dict[str, object]]) -> None:
        """``responses`` maps a system-prompt marker substring -> JSON payload."""
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    async def complete(self, *, system: str, user: str) -> LLMResult:
        self.calls.append((system, user))
        for marker, payload in self._responses.items():
            if marker in system:
                return LLMResult(
                    content=json.dumps(payload), model="fake", prompt_tokens=10, completion_tokens=10
                )
        raise AssertionError(f"FakeLLM has no response for system prompt: {system[:80]}...")


def emergency_case_responses() -> dict[str, dict[str, object]]:
    """Canned LLM payloads for a case_001-style emergency (shared by suites)."""
    return {
        "clinical signal extraction": {
            "symptoms": ["chest pain", "sweating", "nausea"],
            "duration": "20 minutes",
            "severity": "crushing",
            "onset": "sudden",
            "radiation": "to left arm",
            "age": None,
            "is_pregnant": None,
            "medical_history": [],
            "medications": [],
            "allergies": [],
            "affects_child": False,
            "ambiguity_notes": [],
        },
        "red flag detection": {"red_flags": ["possible myocardial infarction presentation"]},
        "urgency classification": {
            "urgency": "emergency",
            "reason": "Classic acute coronary syndrome red flags.",
            "supporting_signals": ["chest pain", "radiation to left arm", "diaphoresis"],
        },
        "explanation of a triage decision": {
            "explanation": "Your symptoms match warning signs of a heart problem and need immediate emergency care."
        },
    }


class FakeSearchTool:
    """Returns canned results; records queries for assertions."""

    def __init__(self, results: list[SearchResult] | None = None, *, fail: bool = False) -> None:
        self._results = results or []
        self._fail = fail
        self.queries: list[str] = []

    @property
    def provider_name(self) -> str:
        return "fake-search"

    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        self.queries.append(query)
        if self._fail:
            raise ConnectionError("search backend down")
        return self._results[:max_results]
