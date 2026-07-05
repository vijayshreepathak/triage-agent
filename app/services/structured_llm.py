"""Structured LLM calling — one implementation for every LLM-touching node.

Responsibilities (and nothing else):
1. Send the prompt through the injected ``LLMClient``.
2. Extract and parse JSON from the completion (tolerating stray fences).
3. Validate against the caller's Pydantic schema.
4. On malformed output: retry ONCE with a corrective instruction (per spec).

Transport-level retries (timeouts, 429s) belong to the provider adapters in
``app/tools`` — mixing the two retry ladders here would multiply attempts
(2 parse retries x 4 transport attempts is intended, not accidental).
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.prompts.base import RETRY_CORRECTION_SUFFIX
from app.tools.interfaces import LLMClient
from app.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_PARSE_ATTEMPTS = 2  # initial call + exactly one corrective retry, per spec


class StructuredOutputError(Exception):
    """The LLM call failed to produce valid structured output.

    Raised for BOTH malformed output (after the corrective retry) and
    transport-level failures (after the provider adapter exhausted its own
    retries). Nodes handle exactly one exception type and degrade the same
    way regardless of *why* the LLM was unusable — the deterministic parts
    of the pipeline must survive either case.
    """


def extract_json_object(content: str) -> dict[str, object]:
    """Pull the first JSON object out of a completion, tolerating fences.

    Models occasionally wrap output in ```json fences despite instructions;
    stripping them deterministically is cheaper and safer than a retry.
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("no JSON object found in completion", text, 0)
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("top-level JSON value is not an object", text, 0)
    return parsed


class StructuredLLMCaller:
    """Validated-JSON gateway to the LLM. Injected into every LLM node."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def call(self, *, system: str, user: str, schema: type[T], operation: str) -> tuple[T, int]:
        """Run the prompt and return (validated model, retry_count).

        Raises:
            StructuredOutputError: When output is still malformed after the
                one corrective retry. Nodes decide how to degrade.
        """
        last_error: Exception | None = None
        for attempt in range(_PARSE_ATTEMPTS):
            prompt_user = user if attempt == 0 else f"{user}\n\n{RETRY_CORRECTION_SUFFIX}"
            try:
                result = await self._llm.complete(system=system, user=prompt_user)
            except Exception as exc:
                # Transport failure: the provider adapter already retried at
                # its level; re-calling here would multiply retry ladders.
                logger.error(
                    "llm transport failure",
                    extra={"operation": operation, "error": type(exc).__name__},
                )
                raise StructuredOutputError(f"{operation}: LLM unavailable: {exc!r}") from exc
            logger.debug(
                "llm completion received",
                extra={
                    "operation": operation,
                    "attempt": attempt,
                    "model": result.model,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                },
            )
            try:
                data = extract_json_object(result.content)
                return schema.model_validate(data), attempt
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning(
                    (
                        "malformed structured output, retrying"
                        if attempt == 0
                        else "malformed structured output, giving up"
                    ),
                    extra={"operation": operation, "attempt": attempt, "error": type(exc).__name__},
                )
        raise StructuredOutputError(f"{operation}: output failed validation after retry: {last_error!r}")
