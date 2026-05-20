# ABOUTME: Tests for generator.py — _parse_generator_output and split-generator routing.
# ABOUTME: Verifies candidate, report, and files_modified extraction from subagent result text.

import pytest

from simmer_sdk.generator import GeneratorOutput, _parse_generator_output, _split_generate
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


# ---------------------------------------------------------------------------
# _split_generate routing — regression for Bedrock-Converse fallback gate.
# Prior bug: any model id not matching is_anthropic_model() was routed to
# Bedrock Converse, including Gemini IDs. The gate must require api_provider
# == "bedrock" before that fallback fires.
# ---------------------------------------------------------------------------


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeUsage:
    def __init__(self, in_tok=10, out_tok=20):
        self.input_tokens = in_tok
        self.output_tokens = out_tok


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, recorder):
        self._rec = recorder

    async def create(self, **kwargs):
        self._rec.append(kwargs)
        # Architect call returns a "contract", executor returns final candidate
        text = "GENERATED_CANDIDATE" if "writer executing" in kwargs["messages"][0]["content"] else "CONTRACT_TEXT"
        return _FakeResponse(text)


class _FakeClient:
    def __init__(self):
        self.calls: list[dict] = []
        self.messages = _FakeMessages(self.calls)


def _split_brief(provider: str, model: str) -> SetupBrief:
    return SetupBrief(
        artifact="test artifact",
        artifact_type="single-file",
        criteria={"quality": "good"},
        iterations=1,
        mode="seedless",
        api_provider=provider,
        generator_model=model,
        clerk_model=model,
        executor_model=model,
        output_dir="/tmp",
    )


async def test_split_generate_google_does_not_use_bedrock_converse(monkeypatch):
    """Regression: Gemini model id must NOT route to invoke_bedrock_model
    just because is_anthropic_model() returns False."""
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "simmer_sdk.client.create_async_client",
        lambda brief, role="default": fake_client,
    )

    # If the gate is broken, this raises (boto3 has no creds in tests)
    def explode(*args, **kwargs):
        raise AssertionError("invoke_bedrock_model should not be called for api_provider='google'")
    monkeypatch.setattr("simmer_sdk.client.invoke_bedrock_model", explode)

    brief = _split_brief(provider="google", model="gemini-3.5-flash")
    result = await _split_generate(
        brief=brief,
        iteration=1,
        current_candidate="seed text",
        asi="improve specificity",
    )

    assert isinstance(result, GeneratorOutput)
    # Two calls: architect (contract) + executor (final candidate)
    assert len(fake_client.calls) == 2
    assert result.candidate == "GENERATED_CANDIDATE"


async def test_split_generate_bedrock_with_claude_uses_messages_create(monkeypatch):
    """Bedrock + Claude model id should still go through messages.create (not Converse)."""
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "simmer_sdk.client.create_async_client",
        lambda brief, role="default": fake_client,
    )

    def explode(*args, **kwargs):
        raise AssertionError("Claude model on Bedrock should use SDK, not Converse")
    monkeypatch.setattr("simmer_sdk.client.invoke_bedrock_model", explode)

    brief = _split_brief(provider="bedrock", model="claude-sonnet-4-6")
    await _split_generate(
        brief=brief,
        iteration=1,
        current_candidate="seed",
        asi="x",
    )

    assert len(fake_client.calls) == 2


async def test_split_generate_bedrock_with_non_claude_uses_converse(monkeypatch):
    """Bedrock + non-Claude model id is the ONE case where Converse fires."""
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "simmer_sdk.client.create_async_client",
        lambda brief, role="default": fake_client,
    )

    converse_called = {"count": 0}
    async def fake_converse(model_id, prompt, brief, max_tokens=8192):
        converse_called["count"] += 1
        return ("FROM_BEDROCK", {"input_tokens": 1, "output_tokens": 2})
    monkeypatch.setattr("simmer_sdk.client.invoke_bedrock_model", fake_converse)
    # Also patch via the from-import site in generator.py
    monkeypatch.setattr("simmer_sdk.generator.invoke_bedrock_model", fake_converse, raising=False)

    brief = _split_brief(provider="bedrock", model="amazon.nova-lite-v1:0")
    await _split_generate(
        brief=brief,
        iteration=1,
        current_candidate="seed",
        asi="x",
    )

    # Architect (Claude path via messages.create) + executor (Converse) = 1 messages.create call
    assert len(fake_client.calls) == 1
    assert converse_called["count"] == 1
