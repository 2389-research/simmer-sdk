# ABOUTME: Tests for prompts.py — helper functions and build_board_composition_prompt.
# ABOUTME: Covers _format_criteria, _format_scores, _optional_block, and prompt builder tests.

from simmer_sdk.prompts import (
    _format_criteria,
    _format_scores,
    _optional_block,
    build_board_composition_prompt,
)


class TestBuildBoardCompositionPrompt:
    """Tests for judge_count interpolation in build_board_composition_prompt."""

    _BASE_KWARGS = dict(
        artifact_summary="A test artifact",
        criteria={"clarity": "Is it clear?"},
        problem_class="text",
        has_evaluator=False,
    )

    def test_judge_count_is_interpolated_not_literal(self):
        """The prompt must not contain the literal string '{judge_count}'."""
        result = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=5)
        assert "{judge_count}" not in result

    def test_judge_count_value_appears_in_prompt(self):
        """The numeric value of judge_count must appear in the prompt."""
        result = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=5)
        assert "5" in result

    def test_default_judge_count_not_literal(self):
        """Default judge_count=3 must also be interpolated, not literal."""
        result = build_board_composition_prompt(**self._BASE_KWARGS)
        assert "{judge_count}" not in result

    def test_default_judge_count_value_appears(self):
        """Default judge_count=3 value must appear in the prompt."""
        result = build_board_composition_prompt(**self._BASE_KWARGS)
        assert "3" in result

    def test_different_judge_counts_produce_different_prompts(self):
        """Prompts for different judge_count values must differ."""
        result_3 = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=3)
        result_7 = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=7)
        assert result_3 != result_7

    def _extract_instruction_tail(self, result: str) -> str:
        """Extract only the appended instruction section (from 'Design' onwards)."""
        marker = "\nDesign "
        idx = result.rfind(marker)
        assert idx != -1, "Could not find 'Design' instruction in prompt"
        return result[idx:]

    def test_output_format_example_reflects_judge_count(self):
        """The JUDGE_PANEL output format example should have entries matching judge_count."""
        result = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=2)
        tail = self._extract_instruction_tail(result)
        name_entry_count = tail.count("  - name:")
        assert name_entry_count == 2, (
            f"Expected 2 judge entries in output format tail, got {name_entry_count}"
        )

    def test_output_format_example_five_judges(self):
        """Output format example with judge_count=5 should have 5 entries."""
        result = build_board_composition_prompt(**self._BASE_KWARGS, judge_count=5)
        tail = self._extract_instruction_tail(result)
        name_entry_count = tail.count("  - name:")
        assert name_entry_count == 5, (
            f"Expected 5 judge entries in output format tail, got {name_entry_count}"
        )


# ---------------------------------------------------------------------------
# _format_criteria
# ---------------------------------------------------------------------------


class TestFormatCriteria:
    """Tests for the _format_criteria helper."""

    def test_keys_present_in_output(self):
        """All criterion names must appear in the formatted string."""
        result = _format_criteria({"clarity": "Is it clear?", "depth": "Has depth?"})
        assert "clarity" in result
        assert "depth" in result

    def test_values_present_in_output(self):
        """All criterion descriptions must appear in the formatted string."""
        result = _format_criteria({"clarity": "Is it clear?", "depth": "Has depth?"})
        assert "Is it clear?" in result
        assert "Has depth?" in result

    def test_single_criterion_formats_correctly(self):
        """A single-entry dict should produce exactly one bullet line."""
        result = _format_criteria({"style": "Is it stylish?"})
        assert "style" in result
        assert "Is it stylish?" in result
        # Exactly one bullet
        assert result.count("  - ") == 1

    def test_multiple_criteria_produce_multiple_lines(self):
        """Multiple criteria should produce one line each."""
        result = _format_criteria({"a": "desc_a", "b": "desc_b", "c": "desc_c"})
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_empty_dict_returns_empty_string(self):
        """An empty criteria dict should return an empty string."""
        result = _format_criteria({})
        assert result == ""

    def test_key_and_value_separated_by_colon(self):
        """Each line must use the 'key: value' format."""
        result = _format_criteria({"tone": "Is the tone right?"})
        assert "tone: Is the tone right?" in result


# ---------------------------------------------------------------------------
# _format_scores
# ---------------------------------------------------------------------------


class TestFormatScores:
    """Tests for the _format_scores helper."""

    def test_scores_include_slash_ten_suffix(self):
        """Every score must be rendered as N/10."""
        result = _format_scores({"clarity": 7, "depth": 9})
        assert "7/10" in result
        assert "9/10" in result

    def test_criterion_names_present(self):
        """Criterion names must appear in the output."""
        result = _format_scores({"clarity": 7, "depth": 9})
        assert "clarity" in result
        assert "depth" in result

    def test_single_score_formats_correctly(self):
        """A single-score dict should produce one line with /10."""
        result = _format_scores({"quality": 5})
        assert "quality" in result
        assert "5/10" in result
        assert result.count("/10") == 1

    def test_multiple_scores_produce_multiple_lines(self):
        """Multiple scores should produce one line each."""
        result = _format_scores({"a": 1, "b": 2, "c": 3})
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_zero_score_formats_correctly(self):
        """A score of 0 should still render as 0/10."""
        result = _format_scores({"metric": 0})
        assert "0/10" in result

    def test_ten_score_formats_correctly(self):
        """A perfect score of 10 should render as 10/10."""
        result = _format_scores({"metric": 10})
        assert "10/10" in result


# ---------------------------------------------------------------------------
# _optional_block
# ---------------------------------------------------------------------------


class TestOptionalBlock:
    """Tests for the _optional_block helper."""

    def test_with_value_includes_label(self):
        """When value is provided the label must appear in the output."""
        result = _optional_block("BACKGROUND", "some context here")
        assert "BACKGROUND" in result

    def test_with_value_includes_content(self):
        """When value is provided the content must appear in the output."""
        result = _optional_block("BACKGROUND", "some context here")
        assert "some context here" in result

    def test_with_none_returns_empty_string(self):
        """When value is None the result must be an empty string."""
        result = _optional_block("BACKGROUND", None)
        assert result == ""

    def test_with_empty_string_returns_empty_string(self):
        """When value is an empty string the result must be an empty string."""
        result = _optional_block("BACKGROUND", "")
        assert result == ""

    def test_different_labels_produce_different_outputs(self):
        """Two calls with different labels but same value must differ."""
        result_a = _optional_block("LABEL_A", "shared content")
        result_b = _optional_block("LABEL_B", "shared content")
        assert result_a != result_b

    def test_output_starts_with_newline(self):
        """The returned block should start with a newline to separate from context."""
        result = _optional_block("SECTION", "text")
        assert result.startswith("\n")
