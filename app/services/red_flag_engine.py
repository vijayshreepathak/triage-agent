"""Deterministic Red Flag Engine.

Pure function over the configurable rule table in
``app/config/red_flag_rules.py`` — no LLM, no I/O, no randomness. Same
text in, same flags out, every time. This is the safety backbone: the LLM
may ADD candidate flags (labeled ``source="llm"``), but rule hits are the
only flags allowed to force-escalate urgency.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.config.red_flag_rules import RED_FLAG_RULES, RedFlagRule
from app.models.clinical import RedFlag

RULE_SOURCE = "rule"
LLM_SOURCE = "llm"


class RedFlagEngine:
    """Keyword-group matcher over a rule table (injectable for tests)."""

    def __init__(self, rules: Sequence[RedFlagRule] = RED_FLAG_RULES) -> None:
        self._rules = tuple(rules)
        self._force_emergency_names = frozenset(r.name for r in self._rules if r.force_emergency)

    def detect(self, normalized_text: str) -> list[RedFlag]:
        """Return one RedFlag per matched rule (first matching group wins)."""
        flags: list[RedFlag] = []
        for rule in self._rules:
            for group in rule.any_of:
                if all(keyword in normalized_text for keyword in group):
                    flags.append(RedFlag(name=rule.name, source=RULE_SOURCE, matched_text=" + ".join(group)))
                    break  # one hit per rule is enough; keep output stable
        return flags

    def forces_emergency(self, flags: Sequence[RedFlag]) -> bool:
        """True when any RULE-sourced flag belongs to a force_emergency rule.

        LLM-sourced flags deliberately cannot force escalation: an LLM
        hallucination must never be able to flip the system into emergency
        mode on its own — only auditable deterministic rules can.
        """
        return any(f.source == RULE_SOURCE and f.name in self._force_emergency_names for f in flags)

    @staticmethod
    def merge(rule_flags: Sequence[RedFlag], llm_flag_names: Sequence[str]) -> list[RedFlag]:
        """Union rule and LLM flags, deduplicated case-insensitively by name.

        Rule flags win ties so provenance is never downgraded from
        'rule' to 'llm' for the same finding.
        """
        merged: dict[str, RedFlag] = {f.name.strip().lower(): f for f in rule_flags}
        for name in llm_flag_names:
            key = name.strip().lower()
            if key and key not in merged:
                merged[key] = RedFlag(name=name.strip(), source=LLM_SOURCE)
        return list(merged.values())
