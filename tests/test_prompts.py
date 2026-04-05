from simmer_sdk.prompts import build_board_composition_prompt


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
