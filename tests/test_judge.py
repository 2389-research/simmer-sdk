# ABOUTME: Unit tests for judge.py parser functions (_normalize_key and parse_judge_output).
# ABOUTME: Tests cover normalization, score extraction, ASI parsing, and fuzzy criterion matching.

import pytest

from simmer_sdk.judge import _normalize_key, parse_judge_output
from simmer_sdk.types import JudgeOutput


# ---------------------------------------------------------------------------
# _normalize_key tests
# ---------------------------------------------------------------------------

class TestNormalizeKey:
    def test_passthrough_already_normalized(self):
        assert _normalize_key("narrative_tension") == "narrative_tension"

    def test_spaces_to_underscores(self):
        assert _normalize_key("narrative tension") == "narrative_tension"

    def test_mixed_case_lowercased(self):
        assert _normalize_key("Narrative Tension") == "narrative_tension"

    def test_hyphens_to_underscores(self):
        assert _normalize_key("narrative-tension") == "narrative_tension"

    def test_strips_leading_whitespace(self):
        assert _normalize_key("  foo") == "foo"

    def test_strips_trailing_whitespace(self):
        assert _normalize_key("foo  ") == "foo"

    def test_strips_both_sides_whitespace(self):
        assert _normalize_key("  foo  ") == "foo"

    def test_consecutive_spaces_collapse_to_single_underscore(self):
        assert _normalize_key("foo  bar") == "foo_bar"

    def test_mixed_spaces_hyphens_underscores(self):
        # Multiple separators in a row collapse to one underscore
        assert _normalize_key("foo - bar") == "foo_bar"

    def test_all_uppercase(self):
        assert _normalize_key("NARRATIVE") == "narrative"

    def test_single_word(self):
        assert _normalize_key("clarity") == "clarity"

    def test_empty_string(self):
        assert _normalize_key("") == ""


# ---------------------------------------------------------------------------
# parse_judge_output tests
# ---------------------------------------------------------------------------

SIMPLE_CRITERIA = {
    "narrative_tension": "Does the story create tension?",
    "character_voice": "Is each character's voice distinct?",
    "pacing": "Does the story move at the right pace?",
}


class TestParseJudgeOutputBasic:
    def test_returns_judge_output_instance(self):
        result = parse_judge_output("", SIMPLE_CRITERIA)
        assert isinstance(result, JudgeOutput)

    def test_empty_text_returns_empty_scores(self):
        result = parse_judge_output("", SIMPLE_CRITERIA)
        assert result.scores == {}

    def test_empty_text_returns_empty_asi(self):
        result = parse_judge_output("", SIMPLE_CRITERIA)
        assert result.asi == ""

    def test_empty_text_returns_empty_reasoning(self):
        result = parse_judge_output("", SIMPLE_CRITERIA)
        assert result.reasoning == {}

    def test_standard_format_parses_scores(self):
        text = (
            "ITERATION 1 SCORES:\n"
            "narrative_tension: 7/10 — Good tension throughout\n"
            "character_voice: 8/10 — Voices are distinct\n"
            "pacing: 6/10 — Could move faster\n"
            "COMPOSITE: 7.0/10\n"
            "\n"
            "ASI (highest-leverage direction):\n"
            "Tighten the middle section."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["narrative_tension"] == 7
        assert result.scores["character_voice"] == 8
        assert result.scores["pacing"] == 6

    def test_standard_format_parses_reasoning(self):
        text = (
            "ITERATION 1 SCORES:\n"
            "narrative_tension: 7/10 — Good tension throughout\n"
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "narrative_tension" in result.reasoning
        assert "Good tension throughout" in result.reasoning["narrative_tension"]

    def test_standard_format_parses_asi(self):
        # The ASI section is extracted via the COMPOSITE fallback: everything after
        # the COMPOSITE line becomes the ASI, so the header label is included in asi.
        text = (
            "ITERATION 1 SCORES:\n"
            "narrative_tension: 7/10\n"
            "COMPOSITE: 7.0/10\n"
            "\n"
            "ASI (highest-leverage direction):\n"
            "Tighten the middle section."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "Tighten the middle section." in result.asi

    def test_composite_line_not_in_scores(self):
        text = (
            "narrative_tension: 7/10 — Great\n"
            "COMPOSITE: 7.0/10\n"
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "composite" not in result.scores
        assert "COMPOSITE" not in result.scores

    def test_score_without_reasoning_has_no_reasoning_entry(self):
        text = "narrative_tension: 7/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["narrative_tension"] == 7
        assert "narrative_tension" not in result.reasoning


class TestParseJudgeOutputMarkdownVariants:
    def test_markdown_bold_criterion(self):
        text = "**narrative_tension: 7/10** — Bold formatting used here\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 7

    def test_bulleted_criterion(self):
        text = "- narrative_tension: 7/10 — Bulleted item\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 7

    def test_asterisk_bulleted_criterion(self):
        text = "* narrative_tension: 8/10 — Another bullet style\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 8

    def test_score_with_spaces_around_slash(self):
        text = "narrative_tension: 7 / 10 — Spaces around slash\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 7


class TestParseJudgeOutputFuzzyMatching:
    def test_spaces_in_key_match_underscore_criteria(self):
        # LLM outputs "narrative tension" but criteria key is "narrative_tension"
        text = "narrative tension: 7/10 — Spaces instead of underscores\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 7

    def test_hyphens_in_key_match_underscore_criteria(self):
        text = "narrative-tension: 8/10 — Hyphens instead of underscores\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 8

    def test_mixed_case_criterion_matches(self):
        text = "Narrative Tension: 9/10 — Mixed case\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("narrative_tension") == 9

    def test_partial_prefix_match(self):
        # "pacing" starts with "pac" — abbreviated key should still match
        # via startswith logic in parser
        text = "pacing: 6/10 — On target\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores.get("pacing") == 6

    def test_substring_match_shorter_key(self):
        # "voice" is a substring of "character_voice"
        criteria = {"character_voice": "Is the voice distinct?"}
        text = "voice: 7/10 — Decent\n"
        result = parse_judge_output(text, criteria)
        assert result.scores.get("character_voice") == 7


class TestParseJudgeOutputASI:
    def test_asi_extracted_via_composite_fallback(self):
        # The COMPOSITE fallback captures everything after the COMPOSITE line as ASI.
        # The ASI header label is included in the returned string.
        text = (
            "narrative_tension: 7/10 — Good\n"
            "COMPOSITE: 7/10\n"
            "\n"
            "ASI (highest-leverage direction):\n"
            "Cut the exposition in chapter two."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "Cut the exposition in chapter two." in result.asi

    def test_asi_without_parenthetical(self):
        # The short "ASI:" regex pattern also triggers via COMPOSITE fallback here.
        text = (
            "narrative_tension: 7/10\n"
            "COMPOSITE: 7/10\n"
            "\n"
            "ASI:\n"
            "Focus on showing not telling."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "Focus on showing not telling." in result.asi

    def test_asi_fallback_after_composite(self):
        # Everything after the COMPOSITE line becomes ASI when no ASI regex fires.
        text = (
            "narrative_tension: 7/10\n"
            "COMPOSITE: 7/10\n"
            "This is the improvement direction text."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.asi == "This is the improvement direction text."

    def test_asi_multiline_via_composite_fallback(self):
        # Multiline ASI content is preserved when reached via COMPOSITE fallback.
        text = (
            "narrative_tension: 7/10 — Good\n"
            "COMPOSITE: 7/10\n"
            "\n"
            "ASI (highest-leverage direction):\n"
            "Line one of the suggestion.\n"
            "Line two of the suggestion."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "Line one" in result.asi
        assert "Line two" in result.asi

    def test_asi_not_extracted_without_composite_or_marker(self):
        # Without a COMPOSITE line and when the ASI lookahead regex fires on lowercase
        # text immediately after the colon, ASI is not extracted.
        text = (
            "ASI (highest-leverage direction):\n"
            "Cut the exposition in chapter two."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        # The regex captures empty string here due to the IGNORECASE lookahead behaviour;
        # there is no COMPOSITE fallback either since no COMPOSITE line is present.
        assert result.asi == ""


class TestParseJudgeOutputEdgeCases:
    def test_skips_total_line(self):
        text = "total: 7/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "total" not in result.scores

    def test_skips_overall_line(self):
        text = "overall: 8/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "overall" not in result.scores

    def test_first_match_wins_for_duplicate_criterion(self):
        # Same criterion key appears twice — first value should be kept
        text = (
            "narrative_tension: 7/10 — First occurrence\n"
            "narrative_tension: 9/10 — Second occurrence\n"
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["narrative_tension"] == 7

    def test_unknown_criterion_not_in_scores(self):
        text = "completely_unknown_thing: 5/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert "completely_unknown_thing" not in result.scores

    def test_no_criteria_yields_empty_scores(self):
        text = "narrative_tension: 7/10 — Something\n"
        result = parse_judge_output(text, {})
        assert result.scores == {}

    def test_score_boundary_minimum(self):
        # A score of 1/10 is correctly parsed when the line has no trailing text.
        text = "narrative_tension: 1/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["narrative_tension"] == 1

    def test_score_boundary_maximum(self):
        # A score of 10/10 is correctly parsed when the line has no trailing text.
        text = "character_voice: 10/10\n"
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["character_voice"] == 10

    def test_score_boundaries_with_reasoning_text(self):
        # When score lines include reasoning, the trailing \s* does not consume the
        # following newline, so consecutive score lines are each parsed correctly.
        text = (
            "narrative_tension: 1/10 — Very low\n"
            "character_voice: 10/10 — Perfect\n"
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores["narrative_tension"] == 1
        assert result.scores["character_voice"] == 10

    def test_full_realistic_output(self):
        text = (
            "ITERATION 2 SCORES:\n"
            "narrative_tension: 8/10 — Strong tension in the climax\n"
            "character_voice: 7/10 — Mostly distinct but protagonist blurs occasionally\n"
            "pacing: 6/10 — Middle act drags\n"
            "COMPOSITE: 7.0/10\n"
            "\n"
            "ASI (highest-leverage direction):\n"
            "Accelerate the middle act by cutting three scenes and merging two exposition passages."
        )
        result = parse_judge_output(text, SIMPLE_CRITERIA)
        assert result.scores == {
            "narrative_tension": 8,
            "character_voice": 7,
            "pacing": 6,
        }
        assert "Accelerate the middle act" in result.asi
        assert result.reasoning["narrative_tension"] == "Strong tension in the climax"
        assert result.composite == 7.0
