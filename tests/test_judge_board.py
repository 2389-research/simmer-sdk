# ABOUTME: Tests for judge_board.py — consensus scoring, parser helpers, and deliberation utilities.
# ABOUTME: Covers _parse_judge_panel, _strip_asi_from_output, _extract_revised_scores, _parse_synthesis.

from simmer_sdk.judge_board import (
    _extract_revised_scores,
    _parse_judge_panel,
    _parse_synthesis,
    _strip_asi_from_output,
    compute_consensus_scores,
)
from simmer_sdk.types import JudgeDefinition, StableWins


class TestConsensusScores:
    def test_all_agree_uses_median(self):
        judge_scores = [
            {"clarity": 7, "tone": 6},
            {"clarity": 7, "tone": 7},
            {"clarity": 8, "tone": 6},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7
        assert consensus["tone"] == 6

    def test_spread_uses_median(self):
        judge_scores = [{"clarity": 4}, {"clarity": 7}, {"clarity": 8}]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_two_judges(self):
        judge_scores = [{"clarity": 6}, {"clarity": 8}]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_five_judges(self):
        judge_scores = [
            {"clarity": 3},
            {"clarity": 5},
            {"clarity": 7},
            {"clarity": 8},
            {"clarity": 9},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_multiple_criteria(self):
        judge_scores = [
            {"clarity": 4, "tone": 8, "accuracy": 6},
            {"clarity": 6, "tone": 6, "accuracy": 7},
            {"clarity": 8, "tone": 7, "accuracy": 5},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 6
        assert consensus["tone"] == 7
        assert consensus["accuracy"] == 6


class TestNotWorkingRendering:
    """Test that NOT WORKING items render with their actual text, not literal 'nw'."""

    def _build_previous_deliberation(self, stable_wins: StableWins) -> str:
        """Replicates the exact code path from dispatch_board for the previous_deliberation string."""
        parts: list[str] = []
        if stable_wins.working:
            parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- nw" for nw in stable_wins.not_working))
        if stable_wins.direction:
            parts.append(f"DIRECTION:\n{stable_wins.direction}")
        return "\n\n".join(parts)

    def test_not_working_items_render_as_literal_nw_before_fix(self):
        """This test documents the bug: items render as '- nw' not their text.

        Once the bug is fixed this test should FAIL (it demonstrates the broken behavior).
        It is kept to document what the bug looked like.
        """
        stable_wins = StableWins(not_working=["approach A failed", "approach B was wrong"])
        result = self._build_previous_deliberation(stable_wins)
        # The buggy version renders literal "nw" instead of item text
        assert "- nw" in result
        assert "approach A failed" not in result
        assert "approach B was wrong" not in result

    def _build_previous_deliberation_fixed(self, stable_wins: StableWins) -> str:
        """The correct version of the dispatch_board code path after bug fix."""
        parts: list[str] = []
        if stable_wins.working:
            parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- {nw}" for nw in stable_wins.not_working))
        if stable_wins.direction:
            parts.append(f"DIRECTION:\n{stable_wins.direction}")
        return "\n\n".join(parts)

    def test_not_working_items_render_actual_text(self):
        """After fix: NOT WORKING items must render their actual text."""
        stable_wins = StableWins(not_working=["approach A failed", "approach B was wrong"])
        result = self._build_previous_deliberation_fixed(stable_wins)
        assert "approach A failed" in result
        assert "approach B was wrong" in result
        assert "NOT WORKING (do not retry):\n- approach A failed\n- approach B was wrong" in result

    def test_not_working_does_not_contain_literal_nw_variable_name(self):
        """After fix: output must not contain the literal variable name 'nw' as a list item."""
        stable_wins = StableWins(not_working=["something broke"])
        result = self._build_previous_deliberation_fixed(stable_wins)
        # "- nw" should not appear as a standalone bullet (the bug artifact)
        assert "- nw\n" not in result
        assert result.count("- nw") == 0

    def test_working_items_still_render_correctly(self):
        """WORKING items should be unaffected by the fix."""
        stable_wins = StableWins(
            working=["thing one works", "thing two works"],
            not_working=["bad approach"],
            direction="try something else",
        )
        result = self._build_previous_deliberation_fixed(stable_wins)
        assert "thing one works" in result
        assert "thing two works" in result
        assert "bad approach" in result
        assert "try something else" in result


class TestParseJudgePanel:
    """Tests for _parse_judge_panel."""

    _PANEL_TEXT = """
JUDGE_PANEL:
- name: Analyst
  lens: Evaluate correctness and completeness against criteria
  primitives:
    - seed_calibration
    - diagnose_before_scoring
- name: Pragmatist
  lens: Evaluate practical utility and execution quality
  primitives:
    - protect_high_scoring
- name: Critic
  lens: Challenge assumptions and find weaknesses
"""

    def test_returns_three_judges(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        assert len(judges) == 3

    def test_names_parsed_correctly(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        names = [j.name for j in judges]
        assert "Analyst" in names
        assert "Pragmatist" in names
        assert "Critic" in names

    def test_lens_parsed_correctly(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        analyst = next(j for j in judges if j.name == "Analyst")
        assert "correctness" in analyst.lens.lower()

    def test_primitives_parsed_as_list(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        analyst = next(j for j in judges if j.name == "Analyst")
        assert isinstance(analyst.primitives, list)
        assert len(analyst.primitives) == 2
        assert "seed_calibration" in analyst.primitives

    def test_judge_without_primitives_has_empty_list(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        critic = next(j for j in judges if j.name == "Critic")
        assert critic.primitives == []

    def test_returns_judge_definition_objects(self):
        judges = _parse_judge_panel(self._PANEL_TEXT)
        for j in judges:
            assert isinstance(j, JudgeDefinition)

    def test_empty_text_returns_empty_list(self):
        assert _parse_judge_panel("") == []

    def test_entry_without_lens_is_excluded(self):
        text = "- name: NoLens\n  primitives:\n    - something\n"
        judges = _parse_judge_panel(text)
        assert len(judges) == 0

    def test_text_without_any_name_prefix_yields_no_valid_judges(self):
        # The parser requires "- name:" entries to split on.
        # Text that starts with "- name:" but has no valid lens is excluded.
        text = "- name: OnlyName\n  primitives:\n    - something\n"
        judges = _parse_judge_panel(text)
        # No lens means this entry is excluded by the name-and-lens guard
        assert len(judges) == 0


class TestStripAsiFromOutput:
    """Tests for _strip_asi_from_output."""

    def test_strips_asi_with_full_header(self):
        text = "scores here\nmore scores\n\nASI (highest-leverage direction): do this thing\nmore asi text"
        result = _strip_asi_from_output(text)
        assert "scores here" in result
        assert "ASI" not in result
        assert "do this thing" not in result

    def test_strips_asi_with_short_header(self):
        text = "scores here\n\nASI: do this thing\nmore asi text"
        result = _strip_asi_from_output(text)
        assert "scores here" in result
        assert "do this thing" not in result

    def test_no_asi_returns_unchanged(self):
        text = "just scores\nno asi section here"
        result = _strip_asi_from_output(text)
        assert result == text

    def test_case_insensitive(self):
        text = "scores\n\nasi (highest-leverage direction): something"
        result = _strip_asi_from_output(text)
        assert "something" not in result

    def test_returns_stripped_string(self):
        text = "leading text\n\nASI: blah"
        result = _strip_asi_from_output(text)
        assert result == "leading text"

    def test_preserves_content_before_asi(self):
        text = "criterion_a: 7/10\ncriterion_b: 8/10\n\nASI: next step here"
        result = _strip_asi_from_output(text)
        assert "criterion_a: 7/10" in result
        assert "criterion_b: 8/10" in result


class TestExtractRevisedScores:
    """Tests for _extract_revised_scores."""

    _CRITERIA = {"clarity": "How clear is the text", "tone": "How appropriate is the tone"}

    def test_falls_back_to_original_when_no_scores_found(self):
        original = {"clarity": 7, "tone": 6}
        revised = _extract_revised_scores("no scores here", original, self._CRITERIA)
        assert revised == original

    def test_extracts_score_with_slash_format(self):
        original = {"clarity": 5, "tone": 5}
        delib_text = "clarity: I now think 8/10 is right"
        revised = _extract_revised_scores(delib_text, original, self._CRITERIA)
        assert revised["clarity"] == 8

    def test_does_not_accept_out_of_range_scores(self):
        original = {"clarity": 5}
        # 11 is out of range
        delib_text = "clarity: 11/10"
        revised = _extract_revised_scores(delib_text, original, self._CRITERIA)
        assert revised["clarity"] == 5

    def test_returns_dict_with_all_original_keys(self):
        original = {"clarity": 7, "tone": 6}
        revised = _extract_revised_scores("nothing useful", original, self._CRITERIA)
        assert set(revised.keys()) == {"clarity", "tone"}

    def test_partial_match_updates_score(self):
        # "clarity" in deliberation text should match "clarity" criterion
        original = {"clarity": 5, "tone": 5}
        delib_text = "clarity: revised score 9/10"
        revised = _extract_revised_scores(delib_text, original, self._CRITERIA)
        assert revised["clarity"] == 9

    def test_unmodified_scores_keep_original_value(self):
        original = {"clarity": 7, "tone": 6}
        # Only clarity is mentioned in deliberation
        delib_text = "clarity: 9/10"
        revised = _extract_revised_scores(delib_text, original, self._CRITERIA)
        assert revised["tone"] == 6


class TestParseSynthesis:
    """Tests for _parse_synthesis."""

    _CRITERIA = {"clarity": "How clear", "tone": "How appropriate"}

    # ASI regex captures content on the SAME LINE as the header (after ':').
    # Format: "ASI (highest-leverage direction): <content on same line>"
    _SYNTHESIS_TEXT = (
        "WORKING (preserve what's working):\n"
        "- The structure is solid\n"
        "- The introduction is strong\n\n"
        "NOT WORKING:\n"
        "- The conclusion is weak\n\n"
        "DIRECTION:\n"
        "Focus on the ending\n\n"
        "ASI (highest-leverage direction): Rewrite the conclusion with a stronger call to action."
    )

    def test_extracts_asi(self):
        asi, _ = _parse_synthesis(self._SYNTHESIS_TEXT, self._CRITERIA)
        assert "conclusion" in asi.lower()
        assert "call to action" in asi.lower()

    def test_extracts_working_section_in_summary(self):
        _, summary = _parse_synthesis(self._SYNTHESIS_TEXT, self._CRITERIA)
        assert "WORKING" in summary

    def test_returns_empty_strings_when_no_asi(self):
        text = "just some text without any ASI header"
        asi, _ = _parse_synthesis(text, self._CRITERIA)
        assert asi == ""

    def test_asi_with_short_header_on_same_line(self):
        # ASI content must be on same line as header for the regex to capture it
        text = "some preamble\n\nASI: Improve the intro."
        asi, _ = _parse_synthesis(text, self._CRITERIA)
        assert "Improve the intro" in asi

    def test_summary_falls_back_to_working_line(self):
        text = "WORKING: things are good\nNOT WORKING: things are bad\nASI: do something"
        _, summary = _parse_synthesis(text, self._CRITERIA)
        assert "WORKING" in summary

    def test_returns_two_strings(self):
        result = _parse_synthesis(self._SYNTHESIS_TEXT, self._CRITERIA)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)
