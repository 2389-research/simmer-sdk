# ABOUTME: Tests for client.py — model mapping, env vars, client creation, retry config.
# ABOUTME: Covers Anthropic, Bedrock, and Ollama provider paths without making real API calls.

"""Tests for client.py — provider routing, model mapping, env vars."""

import pytest

from simmer_sdk.client import (
    BEDROCK_MODEL_MAP,
    OLLAMA_MODELS,
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
