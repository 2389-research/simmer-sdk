# ABOUTME: Tests for client.py — model mapping, env vars, client creation, retry config.
# ABOUTME: Covers Anthropic, Bedrock, Ollama, and Google provider paths without making real API calls.

"""Tests for client.py — provider routing, model mapping, env vars."""

import pytest

from simmer_sdk.client import (
    BEDROCK_MODEL_MAP,
    OLLAMA_MODELS,
    _resolve_gemini_thinking_level,
    create_async_client,
    extract_text,
    get_agent_env,
    map_model_id,
)
from simmer_sdk.types import SetupBrief


def _brief(**overrides) -> SetupBrief:
    defaults = dict(
        artifact="test",
        artifact_type="single-file",
        criteria={"quality": "good"},
        iterations=3,
        mode="seedless",
    )
    defaults.update(overrides)
    return SetupBrief(**defaults)


# ---------------------------------------------------------------------------
# map_model_id
# ---------------------------------------------------------------------------


def test_map_model_anthropic_passthrough():
    brief = _brief(api_provider="anthropic")
    assert map_model_id("claude-sonnet-4-6", brief) == "claude-sonnet-4-6"


def test_map_model_anthropic_unknown_passthrough():
    brief = _brief(api_provider="anthropic")
    assert map_model_id("some-future-model", brief) == "some-future-model"


def test_map_model_bedrock_maps_known():
    brief = _brief(api_provider="bedrock")
    assert map_model_id("claude-sonnet-4-5", brief) == BEDROCK_MODEL_MAP["claude-sonnet-4-5"]


def test_map_model_bedrock_maps_haiku():
    brief = _brief(api_provider="bedrock")
    assert map_model_id("claude-haiku-4-5", brief) == BEDROCK_MODEL_MAP["claude-haiku-4-5"]


def test_map_model_bedrock_passthrough_unknown():
    brief = _brief(api_provider="bedrock")
    assert map_model_id("custom-model-id", brief) == "custom-model-id"


def test_map_model_bedrock_maps_sonnet46():
    brief = _brief(api_provider="bedrock")
    result = map_model_id("claude-sonnet-4-6", brief)
    assert result == BEDROCK_MODEL_MAP["claude-sonnet-4-6"]


def test_map_model_ollama_passthrough():
    brief = _brief(api_provider="ollama")
    assert map_model_id("qwen3:32b", brief) == "qwen3:32b"


def test_map_model_ollama_passthrough_anthropic_ids():
    """Ollama doesn't remap — callers must set model fields to Ollama tags."""
    brief = _brief(api_provider="ollama")
    assert map_model_id("claude-sonnet-4-6", brief) == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# get_agent_env
# ---------------------------------------------------------------------------


def test_agent_env_anthropic_empty():
    brief = _brief(api_provider="anthropic")
    assert get_agent_env(brief) == {}


def test_agent_env_bedrock_sets_core_vars():
    brief = _brief(api_provider="bedrock")
    env = get_agent_env(brief)
    assert env["CLAUDE_CODE_USE_BEDROCK"] == "1"
    assert "ANTHROPIC_API_KEY" in env


def test_agent_env_bedrock_sets_aws_credentials():
    brief = _brief(
        api_provider="bedrock",
        aws_access_key="AK",
        aws_secret_key="SK",
        aws_region="us-west-2",
    )
    env = get_agent_env(brief)
    assert env["CLAUDE_CODE_USE_BEDROCK"] == "1"
    assert env["AWS_ACCESS_KEY_ID"] == "AK"
    assert env["AWS_SECRET_ACCESS_KEY"] == "SK"
    assert env["AWS_REGION"] == "us-west-2"


def test_agent_env_bedrock_omits_missing_credentials():
    brief = _brief(api_provider="bedrock")
    env = get_agent_env(brief)
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "AWS_REGION" not in env


def test_agent_env_bedrock_partial_credentials():
    brief = _brief(api_provider="bedrock", aws_region="eu-west-1")
    env = get_agent_env(brief)
    assert env["AWS_REGION"] == "eu-west-1"
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_agent_env_ollama():
    brief = _brief(api_provider="ollama", ollama_url="http://ollama:11434")
    env = get_agent_env(brief)
    assert env["ANTHROPIC_BASE_URL"] == "http://ollama:11434"
    assert env["ANTHROPIC_API_KEY"] == "ollama"
    assert "CLAUDE_CODE_USE_BEDROCK" not in env


def test_agent_env_ollama_default_url():
    brief = _brief(api_provider="ollama")
    env = get_agent_env(brief)
    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:11434"


# ---------------------------------------------------------------------------
# create_async_client
# ---------------------------------------------------------------------------


def test_create_client_anthropic():
    from anthropic import AsyncAnthropic
    brief = _brief(api_provider="anthropic")
    client = create_async_client(brief)
    assert isinstance(client, AsyncAnthropic)


def test_create_client_ollama():
    from anthropic import AsyncAnthropic
    brief = _brief(api_provider="ollama", ollama_url="http://localhost:11434")
    client = create_async_client(brief)
    assert isinstance(client, AsyncAnthropic)
    assert "localhost:11434" in str(client.base_url)


def test_create_client_bedrock():
    from anthropic import AsyncAnthropicBedrock
    brief = _brief(
        api_provider="bedrock",
        aws_access_key="AKIA",
        aws_secret_key="secret",
        aws_region="us-east-1",
    )
    client = create_async_client(brief)
    assert isinstance(client, AsyncAnthropicBedrock)


def test_create_client_anthropic_has_max_retries(monkeypatch):
    """AsyncAnthropic should be constructed with max_retries=3."""
    captured = {}

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    original = None
    try:
        import anthropic as _ant
        original = _ant.AsyncAnthropic
        _ant.AsyncAnthropic = FakeAsyncAnthropic
        import simmer_sdk.client as c
        c.create_async_client(_brief(api_provider="anthropic"))
    finally:
        if original is not None:
            import anthropic as _ant
            _ant.AsyncAnthropic = original

    assert captured.get("max_retries") == 3


# ---------------------------------------------------------------------------
# OLLAMA_MODELS
# ---------------------------------------------------------------------------


def test_ollama_models_populated():
    assert len(OLLAMA_MODELS) > 0
    assert all(":" in m for m in OLLAMA_MODELS)


# ---------------------------------------------------------------------------
# extract_text — handles thinking blocks from reasoning models
# ---------------------------------------------------------------------------


class _FakeBlock:
    def __init__(self, type_: str, text: str = ""):
        self.type = type_
        self.text = text


class _FakeResponse:
    def __init__(self, blocks):
        self.content = blocks


def test_extract_text_standard_model():
    resp = _FakeResponse([_FakeBlock("text", "Hello world")])
    assert extract_text(resp) == "Hello world"


def test_extract_text_reasoning_model():
    resp = _FakeResponse([
        _FakeBlock("thinking", "Let me think..."),
        _FakeBlock("text", "Hello world"),
    ])
    assert extract_text(resp) == "Hello world"


def test_extract_text_thinking_only_fallback():
    """When max_tokens is too low, reasoning models return only thinking."""
    block = _FakeBlock("thinking")
    block.thinking = "The answer is four."
    resp = _FakeResponse([block])
    assert extract_text(resp) == "The answer is four."


def test_extract_text_empty_response():
    resp = _FakeResponse([])
    assert extract_text(resp) == ""


# ---------------------------------------------------------------------------
# Google / Gemini provider
# ---------------------------------------------------------------------------


def test_create_client_google_returns_gemini_client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from simmer_sdk._gemini_adapter import GeminiClient
    client = create_async_client(_brief(api_provider="google"))
    assert isinstance(client, GeminiClient)


def test_create_client_google_uses_brief_api_key_over_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    brief = _brief(api_provider="google", google_api_key="explicit-key")
    client = create_async_client(brief)
    assert client._api_key == "explicit-key"


def test_create_client_google_falls_back_to_google_api_key_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "from-google-env")
    client = create_async_client(_brief(api_provider="google"))
    assert client._api_key == "from-google-env"


def test_create_client_google_raises_without_any_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        create_async_client(_brief(api_provider="google"))


def test_create_client_google_passes_role_thinking_level(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    brief = _brief(
        api_provider="google",
        gemini_thinking_level="MINIMAL",
        gemini_judge_thinking_level="HIGH",
    )
    judge_client = create_async_client(brief, role="judge")
    other_client = create_async_client(brief, role="generator")
    assert judge_client._thinking_level == "HIGH"
    assert other_client._thinking_level == "MINIMAL"


def test_create_client_google_lowercase_thinking_level_normalized(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    brief = _brief(api_provider="google", gemini_thinking_level="low")
    client = create_async_client(brief)
    assert client._thinking_level == "LOW"


# ---------------------------------------------------------------------------
# _resolve_gemini_thinking_level — per-role lookup with global fallback
# ---------------------------------------------------------------------------


def test_resolve_thinking_level_per_role_override():
    brief = _brief(
        gemini_thinking_level="MINIMAL",
        gemini_judge_thinking_level="HIGH",
        gemini_generator_thinking_level="LOW",
    )
    assert _resolve_gemini_thinking_level(brief, "judge") == "HIGH"
    assert _resolve_gemini_thinking_level(brief, "generator") == "LOW"
    assert _resolve_gemini_thinking_level(brief, "clerk") == "MINIMAL"


def test_resolve_thinking_level_falls_back_to_global():
    brief = _brief(gemini_thinking_level="MEDIUM")
    assert _resolve_gemini_thinking_level(brief, "judge") == "MEDIUM"
    assert _resolve_gemini_thinking_level(brief, "generator") == "MEDIUM"
    assert _resolve_gemini_thinking_level(brief, "clerk") == "MEDIUM"


def test_resolve_thinking_level_none_when_nothing_set():
    brief = _brief()
    assert _resolve_gemini_thinking_level(brief, "judge") is None


def test_resolve_thinking_level_unknown_role_falls_back_to_global():
    brief = _brief(gemini_thinking_level="LOW")
    assert _resolve_gemini_thinking_level(brief, "unknown_role") == "LOW"


# ---------------------------------------------------------------------------
# get_agent_env — Google has no Agent SDK path
# ---------------------------------------------------------------------------


def test_get_agent_env_google_returns_empty():
    """Claude CLI can't drive Gemini — no env vars to wire up."""
    assert get_agent_env(_brief(api_provider="google")) == {}
