from __future__ import annotations

import copy

import pytest

from simmer_sdk.types import SetupBrief
from simmer_sdk.setup import (
    classify_problem,
    auto_select_judge_mode,
    resolve_brief,
)


def make_brief(**kwargs) -> SetupBrief:
    """Helper to build a SetupBrief with sensible defaults."""
    defaults = dict(
        artifact="some artifact",
        artifact_type="prompt",
        criteria={"clarity": "Is it clear?"},
        iterations=3,
        mode="refine",
    )
    defaults.update(kwargs)
    return SetupBrief(**defaults)


class TestClassifyProblem:
    def test_workspace_with_evaluator_is_pipeline_engineering(self):
        brief = make_brief(artifact_type="workspace", evaluator="python eval.py")
        assert classify_problem(brief) == "pipeline/engineering"

    def test_workspace_mode_with_evaluator_is_pipeline_engineering(self):
        brief = make_brief(mode="from-workspace", evaluator="python eval.py")
        assert classify_problem(brief) == "pipeline/engineering"

    def test_code_with_evaluator_is_code_testable(self):
        brief = make_brief(artifact_type="prompt", evaluator="python eval.py")
        assert classify_problem(brief) == "code/testable"

    def test_file_with_evaluator_is_code_testable(self):
        brief = make_brief(artifact_type="file", evaluator="./run_tests.sh")
        assert classify_problem(brief) == "code/testable"

    def test_seedless_prose_no_evaluator_is_text_creative(self):
        brief = make_brief(artifact_type="text", mode="seedless", evaluator=None)
        assert classify_problem(brief) == "text/creative"

    def test_file_without_evaluator_is_text_creative(self):
        brief = make_brief(artifact_type="file", evaluator=None)
        assert classify_problem(brief) == "text/creative"

    def test_default_brief_is_text_creative(self):
        brief = make_brief()
        assert classify_problem(brief) == "text/creative"

    def test_workspace_type_without_evaluator_is_text_creative(self):
        brief = make_brief(artifact_type="workspace", evaluator=None)
        assert classify_problem(brief) == "text/creative"

    def test_workspace_mode_without_evaluator_is_text_creative(self):
        brief = make_brief(mode="from-workspace", evaluator=None)
        assert classify_problem(brief) == "text/creative"


class TestAutoSelectJudgeMode:
    def test_workspace_problem_returns_board(self):
        assert auto_select_judge_mode("pipeline/engineering", 1, None) == "board"

    def test_code_testable_returns_board(self):
        assert auto_select_judge_mode("code/testable", 2, None) == "board"

    def test_text_creative_two_criteria_returns_single(self):
        assert auto_select_judge_mode("text/creative", 2, None) == "single"

    def test_text_creative_one_criterion_returns_single(self):
        assert auto_select_judge_mode("text/creative", 1, None) == "single"

    def test_text_creative_three_criteria_returns_board(self):
        assert auto_select_judge_mode("text/creative", 3, None) == "board"

    def test_text_creative_many_criteria_returns_board(self):
        assert auto_select_judge_mode("text/creative", 5, None) == "board"

    def test_user_override_single_wins_over_workspace(self):
        assert auto_select_judge_mode("pipeline/engineering", 10, "single") == "single"

    def test_user_override_board_wins_over_text_creative_single(self):
        assert auto_select_judge_mode("text/creative", 1, "board") == "board"

    def test_user_override_single_wins_over_code_testable(self):
        assert auto_select_judge_mode("code/testable", 5, "single") == "single"

    def test_user_override_board_wins_for_text_creative_two(self):
        assert auto_select_judge_mode("text/creative", 2, "board") == "board"


class TestResolveBrief:
    def test_auto_judge_mode_gets_resolved_to_single(self):
        brief = make_brief(
            criteria={"clarity": "clear?"},
            judge_mode="auto",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode in ("single", "board")
        assert resolved.judge_mode != "auto"

    def test_auto_judge_mode_text_creative_two_criteria_resolves_to_single(self):
        brief = make_brief(
            criteria={"clarity": "clear?", "tone": "right tone?"},
            judge_mode="auto",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "single"

    def test_auto_judge_mode_text_creative_three_criteria_resolves_to_board(self):
        brief = make_brief(
            criteria={
                "clarity": "clear?",
                "tone": "right tone?",
                "structure": "well structured?",
            },
            judge_mode="auto",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "board"

    def test_auto_judge_mode_with_evaluator_resolves_to_board(self):
        brief = make_brief(
            criteria={"accuracy": "accurate?"},
            evaluator="python eval.py",
            judge_mode="auto",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "board"

    def test_explicit_single_judge_mode_preserved(self):
        brief = make_brief(
            criteria={"c1": "a", "c2": "b", "c3": "c"},
            judge_mode="single",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "single"

    def test_explicit_board_judge_mode_preserved(self):
        brief = make_brief(
            criteria={"clarity": "clear?"},
            judge_mode="board",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "board"

    def test_resolve_brief_returns_deep_copy(self):
        brief = make_brief(judge_mode="auto")
        resolved = resolve_brief(brief)
        # Mutating the original does not affect the resolved copy
        original_criteria = brief.criteria
        brief.criteria["new_key"] = "new_value"
        assert "new_key" not in resolved.criteria

    def test_resolve_brief_does_not_mutate_original(self):
        brief = make_brief(judge_mode="auto")
        resolve_brief(brief)
        assert brief.judge_mode == "auto"
