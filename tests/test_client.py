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
        artifact_type="prompt",
        criteria={"clarity": "clear?"},
        iterations=1,
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


def test_map_model_bedrock_translates():
    brief = _brief(api_provider="bedrock")
    assert map_model_id("claude-sonnet-4-5", brief) == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def test_map_model_bedrock_passthrough_unknown():
    brief = _brief(api_provider="bedrock")
    assert map_model_id("custom-model-id", brief) == "custom-model-id"


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


def test_agent_env_bedrock():
    brief = _brief(
        api_provider="bedrock",
        aws_access_key="AKIA",
        aws_secret_key="secret",
        aws_region="us-east-1",
    )
    env = get_agent_env(brief)
    assert env["CLAUDE_CODE_USE_BEDROCK"] == "1"
    assert env["AWS_REGION"] == "us-east-1"
    assert env["AWS_ACCESS_KEY_ID"] == "AKIA"
    assert env["AWS_SECRET_ACCESS_KEY"] == "secret"
    assert "ANTHROPIC_API_KEY" in env


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


# ---------------------------------------------------------------------------
# OLLAMA_MODELS list exists and has entries
# ---------------------------------------------------------------------------


def test_ollama_models_populated():
    assert len(OLLAMA_MODELS) > 0
    assert all(":" in m for m in OLLAMA_MODELS)  # Ollama tags have model:size format


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
