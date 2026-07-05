"""Clinical signal extraction prompt.

The single most important prompt in the system: it converts free text into
the ``ClinicalSignals`` structure that every downstream node consumes. The
LLM is used as a *parser*, never as an interpreter — it may only restate
what the patient said, in a fixed vocabulary-friendly form.
"""

from __future__ import annotations

from app.prompts.base import CLINICAL_SAFETY_PREAMBLE, JSON_ONLY_INSTRUCTION

_SYSTEM = f"""{CLINICAL_SAFETY_PREAMBLE}

Task: clinical signal extraction. Convert the patient's message into structured signals.
Extract ONLY what is explicitly stated or unambiguously implied. Do not infer diagnoses.

{JSON_ONLY_INSTRUCTION}

JSON schema (all fields required; use null / [] / false when not mentioned):
{{
  "symptoms": ["short lowercase symptom terms, e.g. 'chest pain', 'shortness of breath'"],
  "duration": "how long, verbatim-normalized e.g. '20 minutes', or null",
  "severity": "patient's own severity words e.g. 'crushing', 'mild', or null",
  "onset": "'sudden' or 'gradual' if stated, or null",
  "radiation": "pain radiation e.g. 'to left arm', or null",
  "age": integer age in years if explicitly mentioned, else null,
  "is_pregnant": true / false / null (null when not mentioned),
  "medical_history": ["stated conditions e.g. 'hypertension'"],
  "medications": ["current medications if mentioned"],
  "allergies": ["known allergies if mentioned"],
  "affects_child": true if the message is about a baby/child/toddler, else false,
  "ambiguity_notes": ["note anything vague, contradictory, or missing that limits assessment"]
}}"""


def build_extraction_prompt(patient_message: str) -> tuple[str, str]:
    """Return the (system, user) pair for signal extraction."""
    return _SYSTEM, f'Patient message:\n"""\n{patient_message}\n"""'
