from dataclasses import asdict
from pathlib import Path

import pytest

from simmer_sdk import (
    IterationRecord,
    JudgeDefinition,
    JudgeOutput,
    SetupBrief,
    SimmerResult,
    StableWins,
)


def test_iteration_record_composite():
    record = IterationRecord(
        iteration=1,
        scores={"clarity": 7, "tone": 5, "cta": 4},
        key_change="Rewrote intro",
        asi="better",
        regressed=False,
        judge_mode="auto",
    )
    assert record.composite == 5.3


def test_iteration_record_empty_scores():
    record = IterationRecord(
        iteration=1,
        scores={},
        key_change="",
        asi="neutral",
        regressed=False,
        judge_mode="auto",
    )
    assert record.composite == 0.0


def test_simmer_result_construction():
    trajectory = [
        IterationRecord(
            iteration=1,
            scores={"clarity": 8},
            key_change="Initial",
            asi="better",
            regressed=False,
            judge_mode="auto",
        )
    ]
    result = SimmerResult(
        best_candidate="some text",
        best_iteration=1,
        best_scores={"clarity": 8},
        composite=8.0,
        trajectory=trajectory,
        stable_wins=["clarity"],
        not_working=[],
        output_dir=Path("docs/simmer"),
    )
    assert result.best_candidate == "some text"
    assert result.best_iteration == 1
    assert result.best_scores == {"clarity": 8}
    assert result.composite == 8.0
    assert len(result.trajectory) == 1
    assert result.stable_wins == ["clarity"]
    assert result.not_working == []
    assert result.output_dir == Path("docs/simmer")


def test_setup_brief_defaults():
    brief = SetupBrief(
        artifact="some artifact",
        artifact_type="prompt",
        criteria={"clarity": "Is it clear?"},
        iterations=5,
        mode="refine",
    )
    assert brief.judge_mode == "auto"
    assert brief.output_dir == "docs/simmer"
    assert brief.evaluator is None
    assert brief.primary is None
    assert brief.background is None
    assert brief.output_contract is None
    assert brief.validation_command is None
    assert brief.search_space is None
    assert brief.judge_panel is None
    assert brief.generator_model == "claude-sonnet-4-6"
    assert brief.judge_model == "claude-sonnet-4-6"
    assert brief.clerk_model == "claude-haiku-4-5"


def test_judge_output_construction():
    output = JudgeOutput(
        scores={"clarity": 7, "tone": 6},
        asi="better",
    )
    assert output.scores == {"clarity": 7, "tone": 6}
    assert output.asi == "better"
    assert output.composite == 6.5
    assert output.reasoning == {}
    assert output.deliberation_summary is None
    assert output.panel_working is None
    assert output.panel_not_working is None


def test_judge_definition():
    judge = JudgeDefinition(name="critic", lens="marketing")
    assert judge.name == "critic"
    assert judge.lens == "marketing"
    assert judge.primitives == []


def test_stable_wins_defaults():
    sw = StableWins()
    assert sw.working == []
    assert sw.not_working == []
    assert sw.direction == ""


def test_iteration_record_composite_in_asdict():
    record = IterationRecord(
        iteration=0,
        scores={"a": 7, "b": 9},
        key_change="seed",
        asi="improve",
        regressed=False,
        judge_mode="single",
    )
    d = asdict(record)
    assert "composite" in d
    assert d["composite"] == 8.0
