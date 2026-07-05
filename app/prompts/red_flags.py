"""LLM red-flag augmentation prompt.

The deterministic rule engine runs FIRST and is the source of truth for
known patterns. This prompt only asks the LLM for *additional* candidate
red flags the keyword rules may have missed (unusual phrasings, implied
danger). Its output is unioned with rule hits and clearly labeled
``source="llm"`` so it can never masquerade as a deterministic match.
"""

from __future__ import annotations

from app.prompts.base import CLINICAL_SAFETY_PREAMBLE, JSON_ONLY_INSTRUCTION

_SYSTEM = f"""{CLINICAL_SAFETY_PREAMBLE}

Task: red flag detection. Identify clinically dangerous warning signs present in the
patient's message that require urgent or emergency attention.
Only report red flags actually supported by the message text.

{JSON_ONLY_INSTRUCTION}

JSON schema:
{{
  "red_flags": ["short red flag names, e.g. 'signs of anaphylaxis'"]
}}
Return {{"red_flags": []}} if there are none."""


def build_red_flag_prompt(
    patient_message: str, symptoms: list[str], already_detected: list[str]
) -> tuple[str, str]:
    """Return the (system, user) pair for LLM red-flag augmentation."""
    user = (
        f'Patient message:\n"""\n{patient_message}\n"""\n\n'
        f"Extracted symptoms: {', '.join(symptoms) if symptoms else 'none'}\n"
        f"Already detected by rules (do not repeat): {', '.join(already_detected) if already_detected else 'none'}"
    )
    return _SYSTEM, user
