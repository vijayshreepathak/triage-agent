"""Urgency classification prompt.

The LLM proposes a classification; deterministic post-processing in the
node can only ESCALATE it (red-flag rules floor to emergency), never lower
it. The closed vocabulary is stated twice and enforced again by Pydantic
enum validation — an out-of-vocabulary answer triggers the structured
retry, so "never invent another category" holds end to end.
"""

from __future__ import annotations

from app.models.clinical import ClinicalSignals
from app.prompts.base import CLINICAL_SAFETY_PREAMBLE, JSON_ONLY_INSTRUCTION

_SYSTEM = f"""{CLINICAL_SAFETY_PREAMBLE}

Task: triage urgency classification.
Classify urgency as EXACTLY one of: "low", "moderate", "high", "emergency".
No other value is permitted.

Guidance:
- emergency: time-critical, life- or organ-threatening presentations.
- high: needs medical assessment today.
- moderate: should see a doctor within days.
- low: self-care is reasonable.
- Safety first: when genuinely uncertain between two levels, choose the higher one.

{JSON_ONLY_INSTRUCTION}

JSON schema:
{{
  "urgency": "low | moderate | high | emergency",
  "reason": "one sentence, plain language, no internal reasoning steps",
  "supporting_signals": ["the specific symptoms/signals that drove this classification"]
}}"""


def build_urgency_prompt(
    patient_message: str,
    signals: ClinicalSignals | None,
    red_flag_names: list[str],
) -> tuple[str, str]:
    """Return the (system, user) pair for urgency classification."""
    signals_json = signals.model_dump_json() if signals is not None else "unavailable"
    user = (
        f'Patient message:\n"""\n{patient_message}\n"""\n\n'
        f"Structured clinical signals: {signals_json}\n"
        f"Detected red flags: {', '.join(red_flag_names) if red_flag_names else 'none'}"
    )
    return _SYSTEM, user
