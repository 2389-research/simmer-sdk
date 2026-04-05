# ABOUTME: Tests for client.py — map_model_id, get_agent_env, and retry config.
# ABOUTME: Covers Anthropic and Bedrock provider paths without making real API calls.

import pytest

from simmer_sdk.client import map_model_id, get_agent_env, BEDROCK_MODEL_MAP
from simmer_sdk.types import SetupBrief


def _make_brief(**overrides) -> SetupBrief:
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


def test_map_model_id_anthropic_passthrough():
    brief = _make_brief(api_provider="anthropic")
    assert map_model_id("claude-sonnet-4-6", brief) == "claude-sonnet-4-6"


def test_map_model_id_anthropic_unknown_passthrough():
    brief = _make_brief(api_provider="anthropic")
    assert map_model_id("some-future-model", brief) == "some-future-model"


def test_map_model_id_bedrock_maps_known():
    brief = _make_brief(api_provider="bedrock")
    assert map_model_id("claude-sonnet-4-5", brief) == BEDROCK_MODEL_MAP["claude-sonnet-4-5"]


def test_map_model_id_bedrock_maps_haiku():
    brief = _make_brief(api_provider="bedrock")
    assert map_model_id("claude-haiku-4-5", brief) == BEDROCK_MODEL_MAP["claude-haiku-4-5"]


def test_map_model_id_bedrock_passthrough_unknown():
    brief = _make_brief(api_provider="bedrock")
    # Unknown IDs pass through — caller may have specified a Bedrock ARN directly
    assert map_model_id("custom-model-id", brief) == "custom-model-id"


def test_map_model_id_bedrock_maps_sonnet46():
    brief = _make_brief(api_provider="bedrock")
    result = map_model_id("claude-sonnet-4-6", brief)
    assert result == BEDROCK_MODEL_MAP["claude-sonnet-4-6"]


# ---------------------------------------------------------------------------
# get_agent_env
# ---------------------------------------------------------------------------


def test_get_agent_env_anthropic_empty():
    brief = _make_brief(api_provider="anthropic")
    assert get_agent_env(brief) == {}


def test_get_agent_env_bedrock_sets_core_vars():
    brief = _make_brief(api_provider="bedrock")
    env = get_agent_env(brief)
    assert env["CLAUDE_CODE_USE_BEDROCK"] == "1"
    assert "ANTHROPIC_API_KEY" in env


def test_get_agent_env_bedrock_sets_aws_credentials():
    brief = _make_brief(
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


def test_get_agent_env_bedrock_omits_missing_credentials():
    # When AWS credentials are None, the keys should not appear in env
    brief = _make_brief(api_provider="bedrock")
    env = get_agent_env(brief)
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "AWS_REGION" not in env


def test_get_agent_env_bedrock_partial_credentials():
    # Only region is set — only that key should be present
    brief = _make_brief(api_provider="bedrock", aws_region="eu-west-1")
    env = get_agent_env(brief)
    assert env["AWS_REGION"] == "eu-west-1"
    assert "AWS_ACCESS_KEY_ID" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env


# ---------------------------------------------------------------------------
# create_async_client — verify max_retries is passed (import-level, no network)
# ---------------------------------------------------------------------------


def test_create_async_client_anthropic_has_max_retries(monkeypatch):
    """AsyncAnthropic should be constructed with max_retries=3."""
    captured = {}

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import simmer_sdk.client as client_module
    import anthropic

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeAsyncAnthropic)

    brief = _make_brief(api_provider="anthropic")
    # Re-import inside the function so monkeypatch takes effect
    from importlib import import_module
    import simmer_sdk.client as c
    # Patch directly on the module's namespace the import uses
    original = None
    try:
        import anthropic as _ant
        original = _ant.AsyncAnthropic
        _ant.AsyncAnthropic = FakeAsyncAnthropic
        c.create_async_client(brief)
    finally:
        if original is not None:
            _ant.AsyncAnthropic = original

    assert captured.get("max_retries") == 3
