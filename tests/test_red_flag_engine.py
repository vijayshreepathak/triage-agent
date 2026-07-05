"""Unit tests for the deterministic Red Flag Engine (no LLM, no I/O)."""

from __future__ import annotations

from app.config.red_flag_rules import RedFlagRule
from app.models.clinical import RedFlag
from app.services.red_flag_engine import LLM_SOURCE, RULE_SOURCE, RedFlagEngine


def test_detects_cardiac_chest_pain_from_dataset_case_001() -> None:
    engine = RedFlagEngine()
    text = (
        "i've been having crushing chest pain for the past 20 minutes that radiates "
        "to my left arm. i'm sweating a lot and feel nauseous."
    )
    flags = engine.detect(text)
    names = [f.name for f in flags]
    assert "chest pain with cardiac features" in names
    assert all(f.source == RULE_SOURCE for f in flags)
    assert engine.forces_emergency(flags) is True


def test_detects_stroke_symptoms_from_dataset_case_003() -> None:
    engine = RedFlagEngine()
    flags = engine.detect("my face feels droopy on the left side and my left arm is very weak")
    assert any("stroke" in f.name for f in flags)


def test_no_flags_for_benign_text() -> None:
    engine = RedFlagEngine()
    assert engine.detect("i have a small paper cut on my thumb from opening an envelope") == []


def test_detection_is_deterministic() -> None:
    engine = RedFlagEngine()
    text = "sudden worst headache of my life and my neck feels stiff"
    assert engine.detect(text) == engine.detect(text)


def test_merge_deduplicates_case_insensitively_and_keeps_rule_provenance() -> None:
    rule_flags = [RedFlag(name="Chest Pain", source=RULE_SOURCE)]
    merged = RedFlagEngine.merge(rule_flags, ["chest pain", "new llm finding", "  "])
    assert len(merged) == 2
    by_name = {f.name.lower(): f for f in merged}
    assert by_name["chest pain"].source == RULE_SOURCE  # rule wins the tie
    assert by_name["new llm finding"].source == LLM_SOURCE


def test_llm_flags_can_never_force_emergency() -> None:
    engine = RedFlagEngine()
    llm_only = [RedFlag(name="chest pain with cardiac features", source=LLM_SOURCE)]
    assert engine.forces_emergency(llm_only) is False


def test_custom_rule_table_is_injectable() -> None:
    rules = [RedFlagRule(name="test flag", any_of=[["magic", "words"]], force_emergency=True)]
    engine = RedFlagEngine(rules)
    assert engine.detect("some magic words here")[0].name == "test flag"
    assert engine.detect("only magic") == []  # AND semantics within a group
