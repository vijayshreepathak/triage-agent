"""Unit tests for the StructuredLLMCaller (parse, validate, retry-once)."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from app.services.structured_llm import StructuredLLMCaller, StructuredOutputError, extract_json_object
from app.tools.interfaces import LLMResult


class _Schema(BaseModel):
    value: int


class SequenceLLM:
    """Returns scripted completions in order; records call count."""

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls = 0

    async def complete(self, *, system: str, user: str) -> LLMResult:
        content = self._contents[self.calls]
        self.calls += 1
        return LLMResult(content=content, model="seq")


def test_extract_json_strips_code_fences() -> None:
    assert extract_json_object('```json\n{"value": 5}\n```') == {"value": 5}


def test_extract_json_tolerates_surrounding_prose() -> None:
    assert extract_json_object('Here you go: {"value": 7} hope that helps') == {"value": 7}


def test_extract_json_rejects_non_object() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_json_object("[1, 2, 3]")


@pytest.mark.asyncio
async def test_valid_first_attempt_no_retry() -> None:
    llm = SequenceLLM(['{"value": 1}'])
    result, retries = await StructuredLLMCaller(llm).call(
        system="s", user="u", schema=_Schema, operation="op"
    )
    assert result.value == 1
    assert retries == 0
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_malformed_then_valid_retries_exactly_once() -> None:
    llm = SequenceLLM(["not json at all", '{"value": 2}'])
    result, retries = await StructuredLLMCaller(llm).call(
        system="s", user="u", schema=_Schema, operation="op"
    )
    assert result.value == 2
    assert retries == 1
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_persistently_malformed_raises_after_one_retry() -> None:
    llm = SequenceLLM(["garbage", '{"value": "not an int at all"}'])
    with pytest.raises(StructuredOutputError):
        await StructuredLLMCaller(llm).call(system="s", user="u", schema=_Schema, operation="op")
    assert llm.calls == 2  # exactly one corrective retry, never more


@pytest.mark.asyncio
async def test_transport_failure_wrapped_not_leaked() -> None:
    class DeadLLM:
        async def complete(self, *, system: str, user: str) -> LLMResult:
            raise TimeoutError("socket timeout")

    with pytest.raises(StructuredOutputError):
        await StructuredLLMCaller(DeadLLM()).call(system="s", user="u", schema=_Schema, operation="op")
