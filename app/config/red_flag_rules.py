"""Configurable deterministic red-flag rule table.

This is data, not code: the Red Flag Engine (``app/services/red_flag_engine.py``,
Phase 3) iterates this table and matches keyword groups against normalized
text + extracted symptoms. Clinicians can review/extend this file without
reading any Python logic. Regex-free on purpose — keyword groups are easier
to audit and less likely to over-match.

Matching semantics: a rule fires when ANY of its ``any_of`` keyword groups
is fully present (all keywords within one group found).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RedFlagRule(BaseModel):
    """One deterministic rule. ``any_of`` is a list of AND-groups (OR of ANDs)."""

    model_config = ConfigDict(frozen=True)

    name: str
    any_of: list[list[str]] = Field(description="Fires if all keywords in any inner list are present.")
    force_emergency: bool = Field(
        default=False,
        description="If True, urgency is floored to 'emergency' regardless of the LLM classification.",
    )


RED_FLAG_RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule(
        name="chest pain with cardiac features",
        any_of=[
            ["chest pain", "left arm"],
            ["chest pain", "sweat"],
            ["chest pain", "radiat"],
            ["crushing chest"],
        ],
        force_emergency=True,
    ),
    RedFlagRule(
        name="stroke symptoms",
        any_of=[
            ["face", "droop"],
            ["slurred speech"],
            ["arm", "weak", "speech"],
            ["sudden", "weakness", "one side"],
        ],
        force_emergency=True,
    ),
    RedFlagRule(
        name="difficulty breathing",
        any_of=[
            ["can't breathe"],
            ["cannot breathe"],
            ["difficulty breathing"],
            ["lips", "blue"],
            ["struggling to breathe"],
        ],
        force_emergency=True,
    ),
    RedFlagRule(
        name="loss of consciousness",
        any_of=[["unconscious"], ["passed out"], ["fainted"], ["won't wake"], ["not coming round"]],
    ),
    RedFlagRule(
        name="severe bleeding",
        any_of=[["won't stop bleeding"], ["bleeding heavily"], ["severe bleeding"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="high fever in infant or child",
        any_of=[
            ["fever", "baby"],
            ["fever", "infant"],
            ["40", "year-old", "fever"],
            ["fever", "lethargic", "child"],
        ],
    ),
    RedFlagRule(
        name="pregnancy with bleeding or seizure",
        any_of=[["pregnant", "bleeding"], ["pregnant", "seizure"], ["weeks pregnant", "severe pain"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="suicidal ideation or overdose",
        any_of=[["suicid"], ["overdose"], ["took too many", "tablets"], ["took too many", "pills"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="acute confusion",
        any_of=[
            ["confused", "doesn't recognise"],
            ["confused", "doesn't recognize"],
            ["sudden confusion"],
            ["confused", "fever"],
        ],
    ),
    RedFlagRule(
        name="sudden vision loss",
        any_of=[["sudden", "vision loss"], ["curtain", "vision"], ["curtain", "eye"], ["can't see suddenly"]],
    ),
    RedFlagRule(
        name="severe allergic reaction",
        any_of=[["throat", "swell"], ["anaphyla"], ["allerg", "dizzy", "swell"], ["bee", "allergy", "swell"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="thunderclap headache",
        any_of=[["worst headache", "life"], ["thunderclap"], ["sudden", "headache", "stiff", "neck"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="non-blanching rash with fever",
        any_of=[["non-blanching", "rash"], ["purple rash", "fever"]],
        force_emergency=True,
    ),
    RedFlagRule(
        name="prolonged seizure",
        any_of=[["seizure", "5 minutes"], ["seizure", "hasn't stopped"], ["seizure", "continuously"]],
        force_emergency=True,
    ),
)
