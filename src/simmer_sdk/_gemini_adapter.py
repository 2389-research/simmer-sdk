# ABOUTME: Anthropic-shape adapter for Google Gemini's generateContent API.
# ABOUTME: Lets existing call sites use client.messages.create() against Gemini unchanged.

"""Thin async adapter that exposes Google Gemini behind the AsyncAnthropic
``client.messages.create()`` shape.

The simmer SDK call sites all look like::

    response = await client.messages.create(model=..., max_tokens=..., messages=[...])
    text = extract_text(response)
    tracker.record(model, role, response)

This adapter wraps Gemini's REST endpoint and returns objects that match
that contract: ``response.content[*].text`` for the text payload and
``response.usage.input_tokens / output_tokens`` for tracking.

Tool use (Anthropic's tool_use / Gemini's functionCall) is NOT supported
in this adapter. Workflows that need an agent loop (e.g. the workspace
generator path) cannot use api_provider="google" yet — use
``split_generator=True`` with a string artifact instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _GeminiTextBlock:
    """Matches the shape Anthropic SDK returns in ``response.content[i]``."""
    text: str
    type: str = "text"


@dataclass
class _GeminiUsage:
    """Matches the shape simmer's UsageTracker expects in ``response.usage``."""
    input_tokens: int
    output_tokens: int


@dataclass
class _GeminiResponse:
    """Anthropic-shaped response object backed by a Gemini API call."""
    content: list[_GeminiTextBlock]
    usage: _GeminiUsage
    stop_reason: str = "end_turn"


# Map Anthropic role names to Gemini's
_ROLE_MAP = {"user": "user", "assistant": "model"}


def _flatten_content(content: Any) -> str:
    """Anthropic accepts either a string or a list of content blocks. Gemini
    only consumes plain text in this adapter — image blocks and tool blocks
    are not propagated. Caller is responsible for not sending those."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


class _Messages:
    """Implements ``client.messages.create(...)`` against Gemini."""

    def __init__(self, client: "GeminiClient") -> None:
        self._client = client

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str | None = None,
        **kwargs: Any,
    ) -> _GeminiResponse:
        # tools=, tool_choice= etc. are silently dropped — see module docstring.
        return await self._client._post_generate(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            system=system,
        )


class GeminiClient:
    """Async client that mimics ``anthropic.AsyncAnthropic`` for Gemini.

    Construct via :func:`create` or directly. Use:
        client = GeminiClient(api_key=..., thinking_level="MEDIUM")
        resp = await client.messages.create(model="gemini-3.5-flash", ...)
    """

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        thinking_level: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiClient requires a non-empty api_key")
        self._api_key = api_key
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._thinking_level = thinking_level.upper() if thinking_level else None
        self._timeout = timeout
        self.messages = _Messages(self)

    async def _post_generate(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system: str | None,
    ) -> _GeminiResponse:
        import httpx

        contents: list[dict] = []
        for m in messages:
            role = _ROLE_MAP.get(m.get("role", "user"), "user")
            text = _flatten_content(m.get("content", ""))
            contents.append({"role": role, "parts": [{"text": text}]})

        generation_config: dict[str, Any] = {"maxOutputTokens": max_tokens}
        if self._thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{self._base_url}/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self._api_key,
        }
        # Retry on transient 5xx / timeouts. Gemini's free tier 503s under load.
        import asyncio
        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            for attempt in range(4):
                try:
                    resp = await http.post(url, json=payload, headers=headers)
                    if resp.status_code >= 500:
                        last_exc = httpx.HTTPStatusError(
                            f"{resp.status_code} from Gemini", request=resp.request, response=resp
                        )
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                    last_exc = e
                    await asyncio.sleep(2 ** attempt)
            else:
                raise last_exc if last_exc else RuntimeError("Gemini call failed without exception")

        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))

        usage = data.get("usageMetadata", {})
        # Thinking tokens are billed as output — count them in output_tokens
        # so cost estimates match the real bill.
        input_tokens = int(usage.get("promptTokenCount", 0) or 0)
        candidates_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
        thoughts_tokens = int(usage.get("thoughtsTokenCount", 0) or 0)
        output_tokens = candidates_tokens + thoughts_tokens

        return _GeminiResponse(
            content=[_GeminiTextBlock(text=text)],
            usage=_GeminiUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )
