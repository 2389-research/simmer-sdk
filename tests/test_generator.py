# ABOUTME: Tests for generator.py — specifically _parse_generator_output parser logic.
# ABOUTME: Verifies candidate, report, and files_modified extraction from subagent result text.

from simmer_sdk.generator import GeneratorOutput, _parse_generator_output
from simmer_sdk.types import SetupBrief


def _make_brief() -> SetupBrief:
    """Return a minimal SetupBrief for use in tests."""
    return SetupBrief(
        artifact="test_artifact.txt",
        artifact_type="text",
        criteria={"clarity": "How clear is the text"},
        iterations=3,
        mode="single",
    )


class TestParseGeneratorOutput:
    """Tests for _parse_generator_output."""

    def test_returns_generator_output_instance(self):
        brief = _make_brief()
        result = _parse_generator_output("some result text", brief)
        assert isinstance(result, GeneratorOutput)

    def test_candidate_is_full_result_text(self):
        brief = _make_brief()
        result_text = "Here is the generated content for the artifact."
        result = _parse_generator_output(result_text, brief)
        assert result.candidate == result_text

    def test_report_defaults_to_first_500_chars(self):
        brief = _make_brief()
        result_text = "A" * 600
        result = _parse_generator_output(result_text, brief)
        # Report is either matched or truncated — must not exceed 500
        assert len(result.report) <= 500

    def test_report_extracted_from_report_section(self):
        brief = _make_brief()
        result_text = "Some preamble.\n\nReport: I changed the introduction to be clearer.\n\nOther text."
        result = _parse_generator_output(result_text, brief)
        assert "introduction" in result.report

    def test_report_extracted_from_summary_section(self):
        brief = _make_brief()
        result_text = "Summary: The main change was improving the tone.\n\nDone."
        result = _parse_generator_output(result_text, brief)
        assert "tone" in result.report

    def test_report_extracted_from_changes_section(self):
        brief = _make_brief()
        result_text = "Changes: rewrote paragraphs 1 and 3.\n\nEnd of output."
        result = _parse_generator_output(result_text, brief)
        assert "paragraphs" in result.report

    def test_files_modified_empty_when_not_mentioned(self):
        brief = _make_brief()
        result = _parse_generator_output("just text, no file mentions", brief)
        assert result.files_modified == []

    def test_files_modified_extracted_by_newline(self):
        brief = _make_brief()
        result_text = "Files modified:\n- foo.py\n- bar.py\n\nDone."
        result = _parse_generator_output(result_text, brief)
        assert "foo.py" in result.files_modified
        assert "bar.py" in result.files_modified

    def test_files_modified_extracted_by_comma(self):
        brief = _make_brief()
        result_text = "Files changed: foo.py, bar.py\n\nDone."
        result = _parse_generator_output(result_text, brief)
        assert "foo.py" in result.files_modified
        assert "bar.py" in result.files_modified

    def test_files_modified_strips_bullet_chars(self):
        brief = _make_brief()
        result_text = "Files modified:\n* foo.py\n- bar.py\n\nEnd."
        result = _parse_generator_output(result_text, brief)
        # Bullet chars should be stripped
        assert all(not f.startswith(("-", "*")) for f in result.files_modified)

    def test_empty_result_text_returns_empty_report(self):
        brief = _make_brief()
        result = _parse_generator_output("", brief)
        assert result.report == ""

    def test_empty_result_text_candidate_is_empty(self):
        brief = _make_brief()
        result = _parse_generator_output("", brief)
        assert result.candidate == ""

    def test_files_modified_is_list(self):
        brief = _make_brief()
        result = _parse_generator_output("Files updated: only.py\n\nDone.", brief)
        assert isinstance(result.files_modified, list)

    def test_report_capped_at_500_chars(self):
        brief = _make_brief()
        long_summary = "Summary: " + "x" * 1000 + "\n\nEnd."
        result = _parse_generator_output(long_summary, brief)
        assert len(result.report) <= 500
