# ABOUTME: Tests for _gemini_adapter.py — request/response shape, retry, content flattening.
# ABOUTME: Mocks httpx, no real API calls.

"""Unit tests for the Gemini → Anthropic-shape adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from simmer_sdk._gemini_adapter import (
    GeminiClient,
    _flatten_content,
    _GeminiResponse,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _ok_response(text: str = "hello", prompt_tokens: int = 10,
                 candidates_tokens: int = 5, thoughts_tokens: int = 0):
    """Build a fake httpx.Response with a typical Gemini success payload."""
    payload = {
        "candidates": [{
            "content": {"parts": [{"text": text}]},
        }],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": candidates_tokens,
            "thoughtsTokenCount": thoughts_tokens,
        },
    }
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _err_response(status_code: int):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.request = MagicMock()
    return resp


class _FakeAsyncHttpClient:
    """Mimics httpx.AsyncClient for the adapter — call .responses to drive replies."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if not self._responses:
            raise RuntimeError("test ran out of mocked responses")
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def patch_httpx(monkeypatch):
    """Patch httpx.AsyncClient to return a fake driven by queued responses.

    The adapter does ``import httpx`` lazily inside _post_generate, so we
    patch the attribute on the httpx module itself.
    """
    def install(responses):
        fake = _FakeAsyncHttpClient(responses)

        def factory(*args, **kwargs):
            return fake

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return fake

    return install


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construct_requires_api_key():
    with pytest.raises(ValueError, match="api_key"):
        GeminiClient(api_key="")


def test_thinking_level_normalized_to_upper():
    client = GeminiClient(api_key="k", thinking_level="medium")
    assert client._thinking_level == "MEDIUM"


def test_thinking_level_none_stays_none():
    client = GeminiClient(api_key="k")
    assert client._thinking_level is None


def test_base_url_default():
    client = GeminiClient(api_key="k")
    assert client._base_url == "https://generativelanguage.googleapis.com/v1beta"


def test_base_url_strips_trailing_slash():
    client = GeminiClient(api_key="k", base_url="https://example.com/v1/")
    assert client._base_url == "https://example.com/v1"


# ---------------------------------------------------------------------------
# _flatten_content
# ---------------------------------------------------------------------------


def test_flatten_string_passthrough():
    assert _flatten_content("hello") == "hello"


def test_flatten_text_blocks_concatenated():
    blocks = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": "world"},
    ]
    assert _flatten_content(blocks) == "Hello world"


def test_flatten_skips_non_text_blocks():
    blocks = [
        {"type": "text", "text": "Keep"},
        {"type": "tool_use", "name": "Read", "input": {}},
        {"type": "text", "text": " this"},
    ]
    assert _flatten_content(blocks) == "Keep this"


def test_flatten_handles_bare_strings_in_list():
    assert _flatten_content(["a", "b"]) == "ab"


# ---------------------------------------------------------------------------
# messages.create — request shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_url_and_auth_header(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="secret-key")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "ping"}],
    )

    call = fake.calls[0]
    assert call["url"].endswith("/models/gemini-3.5-flash:generateContent")
    assert call["headers"]["X-goog-api-key"] == "secret-key"
    assert call["headers"]["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_request_maps_user_role(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "hello"}],
    )

    contents = fake.calls[0]["json"]["contents"]
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"] == [{"text": "hello"}]


@pytest.mark.asyncio
async def test_request_maps_assistant_role_to_model(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
            {"role": "user", "content": "Q2"},
        ],
    )

    roles = [c["role"] for c in fake.calls[0]["json"]["contents"]]
    assert roles == ["user", "model", "user"]


@pytest.mark.asyncio
async def test_request_includes_system_instruction(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        system="You are a helper.",
        messages=[{"role": "user", "content": "hi"}],
    )

    payload = fake.calls[0]["json"]
    assert payload["systemInstruction"] == {"parts": [{"text": "You are a helper."}]}


@pytest.mark.asyncio
async def test_request_omits_system_when_not_provided(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert "systemInstruction" not in fake.calls[0]["json"]


@pytest.mark.asyncio
async def test_request_includes_thinking_level_when_set(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k", thinking_level="HIGH")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    gen_config = fake.calls[0]["json"]["generationConfig"]
    assert gen_config["thinkingConfig"] == {"thinkingLevel": "HIGH"}
    assert gen_config["maxOutputTokens"] == 100


@pytest.mark.asyncio
async def test_request_omits_thinking_config_when_level_none(patch_httpx):
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    gen_config = fake.calls[0]["json"]["generationConfig"]
    assert "thinkingConfig" not in gen_config


@pytest.mark.asyncio
async def test_create_raises_on_tools_kwarg(patch_httpx):
    """Tool-use isn't translated to Gemini's functionCall — must fail loudly."""
    patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    with pytest.raises(NotImplementedError, match="tools"):
        await client.messages.create(
            model="gemini-3.5-flash",
            max_tokens=100,
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"name": "Read", "description": "..."}],
        )


@pytest.mark.asyncio
async def test_create_raises_on_tool_choice_kwarg(patch_httpx):
    patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    with pytest.raises(NotImplementedError, match="tool_choice"):
        await client.messages.create(
            model="gemini-3.5-flash",
            max_tokens=100,
            messages=[{"role": "user", "content": "hi"}],
            tool_choice="auto",
        )


@pytest.mark.asyncio
async def test_create_ignores_empty_tools_list(patch_httpx):
    """tools=[] (falsy) should pass through — only non-empty raises."""
    fake = patch_httpx([_ok_response()])
    client = GeminiClient(api_key="k")

    await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_choice=None,
    )
    assert "tools" not in fake.calls[0]["json"]


# ---------------------------------------------------------------------------
# messages.create — response normalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_content_anthropic_shape(patch_httpx):
    patch_httpx([_ok_response(text="hi there")])
    client = GeminiClient(api_key="k")

    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "ping"}],
    )

    assert isinstance(resp, _GeminiResponse)
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "hi there"
    assert resp.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_response_thoughts_counted_as_output_tokens(patch_httpx):
    """thoughtsTokenCount is billed as output — adapter must roll it into output_tokens."""
    patch_httpx([_ok_response(
        prompt_tokens=20, candidates_tokens=50, thoughts_tokens=200,
    )])
    client = GeminiClient(api_key="k")

    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "x"}],
    )

    assert resp.usage.input_tokens == 20
    assert resp.usage.output_tokens == 250  # 50 candidates + 200 thoughts


@pytest.mark.asyncio
async def test_response_empty_candidates_raises(patch_httpx):
    """No candidates = blocked / safety-filtered / max-tokens-no-text.
    Surfacing this as an error prevents silent empty-string propagation."""
    payload = {
        "candidates": [],
        "promptFeedback": {"blockReason": "SAFETY"},
        "usageMetadata": {"promptTokenCount": 5},
    }
    resp_obj = MagicMock(spec=httpx.Response)
    resp_obj.status_code = 200
    resp_obj.json.return_value = payload
    resp_obj.raise_for_status.return_value = None
    patch_httpx([resp_obj])

    client = GeminiClient(api_key="k")
    with pytest.raises(RuntimeError, match="no candidates"):
        await client.messages.create(
            model="gemini-3.5-flash",
            max_tokens=100,
            messages=[{"role": "user", "content": "x"}],
        )


@pytest.mark.asyncio
async def test_response_multipart_text_concatenated(patch_httpx):
    """Gemini sometimes returns multiple parts in one candidate."""
    payload = {
        "candidates": [{
            "content": {"parts": [{"text": "Hello "}, {"text": "world"}]},
        }],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2},
    }
    resp_obj = MagicMock(spec=httpx.Response)
    resp_obj.status_code = 200
    resp_obj.json.return_value = payload
    resp_obj.raise_for_status.return_value = None
    patch_httpx([resp_obj])

    client = GeminiClient(api_key="k")
    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "x"}],
    )
    assert resp.content[0].text == "Hello world"


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds(patch_httpx, monkeypatch):
    """Rate-limit responses are transient — must retry, not fail immediately."""
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    fake = patch_httpx([
        _err_response(429),
        _ok_response(text="recovered"),
    ])

    client = GeminiClient(api_key="k")
    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "x"}],
    )
    assert resp.content[0].text == "recovered"
    assert len(fake.calls) == 2


@pytest.mark.asyncio
async def test_retries_on_503_then_succeeds(patch_httpx, monkeypatch):
    # Patch asyncio.sleep so retries don't actually block the test
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    fake = patch_httpx([
        _err_response(503),
        _err_response(503),
        _ok_response(text="recovered"),
    ])

    client = GeminiClient(api_key="k")
    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "x"}],
    )

    assert resp.content[0].text == "recovered"
    assert len(fake.calls) == 3


@pytest.mark.asyncio
async def test_retries_on_read_timeout_then_succeeds(patch_httpx, monkeypatch):
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    fake = patch_httpx([
        httpx.ReadTimeout("slow"),
        _ok_response(text="recovered"),
    ])

    client = GeminiClient(api_key="k")
    resp = await client.messages.create(
        model="gemini-3.5-flash",
        max_tokens=100,
        messages=[{"role": "user", "content": "x"}],
    )

    assert resp.content[0].text == "recovered"
    assert len(fake.calls) == 2


@pytest.mark.asyncio
async def test_retries_exhausted_raises_last_error(patch_httpx, monkeypatch):
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))

    patch_httpx([
        _err_response(503),
        _err_response(503),
        _err_response(503),
        _err_response(503),
    ])

    client = GeminiClient(api_key="k")
    with pytest.raises(httpx.HTTPStatusError):
        await client.messages.create(
            model="gemini-3.5-flash",
            max_tokens=100,
            messages=[{"role": "user", "content": "x"}],
        )


@pytest.mark.asyncio
async def test_non_retryable_4xx_raises_immediately(patch_httpx):
    """400/401/403 should raise_for_status — not retried."""
    resp_obj = MagicMock(spec=httpx.Response)
    resp_obj.status_code = 401
    resp_obj.request = MagicMock()
    resp_obj.raise_for_status.side_effect = httpx.HTTPStatusError(
        "unauthorized", request=resp_obj.request, response=resp_obj,
    )
    fake = patch_httpx([resp_obj])

    client = GeminiClient(api_key="k")
    with pytest.raises(httpx.HTTPStatusError):
        await client.messages.create(
            model="gemini-3.5-flash",
            max_tokens=100,
            messages=[{"role": "user", "content": "x"}],
        )
    # No retry — exactly one call
    assert len(fake.calls) == 1
