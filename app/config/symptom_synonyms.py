"""Symptom normalization table.

Maps colloquial phrasings to canonical clinical terms so the red-flag
engine, search-query builder, and confidence scorer all operate on a
stable vocabulary. Data, not code — extend freely without touching logic.
"""

from __future__ import annotations

from typing import Final

SYMPTOM_SYNONYMS: Final[dict[str, str]] = {
    # Respiratory
    "shortness of breath": "dyspnea",
    "short of breath": "dyspnea",
    "can't breathe": "dyspnea",
    "cannot breathe": "dyspnea",
    "difficulty breathing": "dyspnea",
    "trouble breathing": "dyspnea",
    "can't catch my breath": "dyspnea",
    # Cardiac
    "chest tightness": "chest pain",
    "crushing chest pain": "chest pain",
    "chest hurts": "chest pain",
    "heart racing": "palpitations",
    "racing heart": "palpitations",
    "fluttering": "palpitations",
    # GI
    "stomach ache": "abdominal pain",
    "tummy ache": "abdominal pain",
    "belly pain": "abdominal pain",
    "throwing up": "vomiting",
    "feel sick": "nausea",
    "nauseous": "nausea",
    "feel nauseous": "nausea",
    # Neuro
    "dizzy": "dizziness",
    "lightheaded": "dizziness",
    "passed out": "syncope",
    "fainted": "syncope",
    "pins and needles": "paresthesia",
    "numbness": "paresthesia",
    "slurred speech": "speech disturbance",
    "trouble speaking": "speech disturbance",
    # General
    "high temperature": "fever",
    "temperature": "fever",
    "sweating a lot": "diaphoresis",
    "sweating": "diaphoresis",
}
