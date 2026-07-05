"""Shared prompt fragments.

Defined once so no prompt duplicates the JSON-only contract or the safety
preamble — "no duplicated prompts" is enforced by composition.
"""

from __future__ import annotations

from typing import Final

JSON_ONLY_INSTRUCTION: Final[str] = (
    "Respond with a single valid JSON object and nothing else. "
    "No markdown code fences, no commentary, no text before or after the JSON."
)

CLINICAL_SAFETY_PREAMBLE: Final[str] = (
    "You are a component inside a clinical triage system. "
    "Never invent symptoms, diagnoses, or facts that are not supported by the input you are given. "
    "If information is absent, represent it as absent (null or empty) rather than guessing."
)

RETRY_CORRECTION_SUFFIX: Final[str] = (
    "IMPORTANT: your previous response was not valid JSON matching the required schema. "
    "Respond again with ONLY the valid JSON object."
)
