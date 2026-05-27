# ABOUTME: API client factory for Anthropic, AWS Bedrock, and Ollama providers.
# ABOUTME: Handles model ID mapping, CLI path resolution, and agent environment setup.

"""Client factory for Anthropic API, AWS Bedrock, Ollama, and Google Gemini.

When api_provider="bedrock", creates AsyncAnthropicBedrock clients and maps
model IDs to Bedrock format. When api_provider="ollama", creates AsyncAnthropic
clients pointed at Ollama's Anthropic-compatible /v1/messages endpoint.
When api_provider="google", returns a GeminiClient adapter that exposes
Anthropic's messages.create() shape over Google's generateContent endpoint
(tool_use is NOT supported — see _gemini_adapter.py).
When api_provider="anthropic" (default), uses AsyncAnthropic with
ANTHROPIC_API_KEY from environment.

For ClaudeSDKClient (Agent SDK) calls, provider config is passed via env vars
through ClaudeAgentOptions(env={...}). Bedrock uses CLAUDE_CODE_USE_BEDROCK=1,
Ollama uses ANTHROPIC_BASE_URL pointed at the Ollama server. Google has no
Agent SDK path — the Claude CLI can't drive Gemini.
"""

from __future__ import annotations

from simmer_sdk.types import SetupBrief


# Bedrock model ID mapping — callers can pass direct API names and we translate
BEDROCK_MODEL_MAP = {
    # Current models
    "claude-sonnet-4-6": "us.anthropic.claude-sonnet-4-6",
    "claude-opus-4-6": "us.anthropic.claude-opus-4-6-v1",
    "claude-haiku-4-5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    # Legacy 4.5 aliases (still valid but superseded by 4.6)
    "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-opus-4-5": "us.anthropic.claude-opus-4-5-20251101-v1:0",
}

# Common Ollama model suggestions — not exhaustive, users can pass any Ollama tag.
# Listed here for documentation and validation hints.
OLLAMA_MODELS = [
    "gemma4:31b",
    "gemma4:26b",
    "qwen3:32b",
    "qwen3.5:27b",
    "qwen3.5:9b",
    "qwen3.5:4b",
    "llama4:16x17b",
    "gemma3:27b",
    "gemma3:4b",
]


def extract_text(response) -> str:
    """Extract text from an Anthropic API response, skipping thinking blocks.

    Reasoning models (e.g., Gemma 4, qwen3 via Ollama) return [thinking, text]
    content blocks. Standard models return [text]. If max_tokens is too low,
    reasoning models may return only [thinking] with no text block — in that
    case we fall back to the thinking content since it often contains the
    useful output.
    """
    for block in response.content:
        if block.type == "text":
            return block.text
    # Fallback: extract thinking content if no text block was produced
    for block in response.content:
        if block.type == "thinking":
            return getattr(block, "thinking", str(block))
    return ""


def _resolve_gemini_thinking_level(brief: SetupBrief, role: str) -> str | None:
    """Pick the Gemini thinking level for a given role with fallback to global."""
    role_field = {
        "judge": brief.gemini_judge_thinking_level,
        "generator": brief.gemini_generator_thinking_level,
        "clerk": brief.gemini_clerk_thinking_level,
    }.get(role)
    return role_field or brief.gemini_thinking_level


def create_async_client(brief: SetupBrief, role: str = "default"):
    """Create an async model client based on the API provider config.

    Returns AsyncAnthropic for direct API and Ollama, AsyncAnthropicBedrock
    for Bedrock, GeminiClient for Google. ``role`` is only used for Google
    to pick the right per-role thinking level (judge/generator/clerk).
    Ollama uses the Anthropic SDK pointed at Ollama's /v1/messages endpoint.

    When a trajectory logger is active, the returned client is transparently
    wrapped so every ``messages.create`` call is logged, and this call begins a
    new agent session (one client == one logical agent session in this codebase).
    """
    client = _build_raw_client(brief, role)

    # Trajectory logging: begin a session for this client and wrap it. No-op
    # (returns the raw client) when no logger is active.
    from simmer_sdk.trajectory import begin_session, get_active_logger, wrap_client

    if get_active_logger() is not None:
        begin_session(role)
        return wrap_client(client)
    return client


def _build_raw_client(brief: SetupBrief, role: str = "default"):
    """Construct the underlying provider client (no logging wrapper)."""
    if brief.api_provider == "bedrock":
        from anthropic import AsyncAnthropicBedrock
        return AsyncAnthropicBedrock(
            aws_access_key=brief.aws_access_key,
            aws_secret_key=brief.aws_secret_key,
            aws_region=brief.aws_region,
            max_retries=3,
        )
    elif brief.api_provider == "ollama":
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(
            base_url=brief.ollama_url,
            api_key="ollama",  # Ollama doesn't need a real key
        )
    elif brief.api_provider == "google":
        import os
        from simmer_sdk._gemini_adapter import GeminiClient
        api_key = brief.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "api_provider='google' requires GEMINI_API_KEY (or GOOGLE_API_KEY) "
                "in the environment or brief.google_api_key set."
            )
        return GeminiClient(
            api_key=api_key,
            thinking_level=_resolve_gemini_thinking_level(brief, role),
        )
    else:
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(max_retries=3)


def map_model_id(model: str, brief: SetupBrief) -> str:
    """Map a direct API model ID to the appropriate provider format.

    For Bedrock, translates claude-sonnet-4-6 -> us.anthropic.claude-sonnet-4-6-v1:0.
    For Ollama, returns the model ID unchanged (uses Ollama tags like qwen3:32b).
    Passes through unknown IDs unchanged (caller may have specified a provider ID directly).
    """
    if brief.api_provider == "bedrock":
        return BEDROCK_MODEL_MAP.get(model, model)
    return model


def is_anthropic_model(model_id: str) -> bool:
    """Check if a model ID is an Anthropic/Claude model."""
    return "anthropic" in model_id or model_id.startswith("claude-")


async def invoke_bedrock_model(
    model_id: str,
    prompt: str,
    brief: SetupBrief,
    max_tokens: int = 16384,
) -> tuple[str, dict]:
    """Invoke any Bedrock model via boto3. Returns (text, usage_dict).

    Works with non-Anthropic models (Nova, Llama, Mistral) that the
    Anthropic SDK can't call. Uses the Bedrock Converse API for
    consistent request/response format across all models.
    """
    import boto3
    import anyio

    def _sync_call():
        client = boto3.client(
            "bedrock-runtime",
            region_name=brief.aws_region or "us-east-1",
            aws_access_key_id=brief.aws_access_key,
            aws_secret_access_key=brief.aws_secret_key,
        )
        return client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
        )

    response = await anyio.to_thread.run_sync(_sync_call)

    text = ""
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            text += block["text"]

    usage = response.get("usage", {})
    usage_dict = {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
    }

    return text, usage_dict


def get_cli_path() -> str | None:
    """Get the path to the system-installed Claude CLI if available.

    The bundled CLI in claude-agent-sdk v0.1.53 (CLI v2.1.88) has a broken
    subprocess transport protocol. The system-installed CLI works correctly.
    Returns None if not found, which makes ClaudeAgentOptions fall back
    to the bundled binary.
    """
    import shutil
    return shutil.which("claude")


def get_agent_env(brief: SetupBrief) -> dict[str, str]:
    """Get environment variables for ClaudeSDKClient (Agent SDK) calls.

    For Bedrock, sets CLAUDE_CODE_USE_BEDROCK=1 and AWS credentials.
    For Ollama, sets ANTHROPIC_BASE_URL pointed at the Ollama server.
    For direct API, returns empty dict (SDK uses ANTHROPIC_API_KEY from env).
    """
    if brief.api_provider == "ollama":
        return {
            "ANTHROPIC_BASE_URL": brief.ollama_url,
            # Claude CLI requires ANTHROPIC_API_KEY even when using a
            # custom base URL. Ollama doesn't validate it.
            "ANTHROPIC_API_KEY": "ollama",
        }
    if brief.api_provider == "bedrock":
        env = {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            # The Claude Code CLI requires ANTHROPIC_API_KEY to be set even in
            # Bedrock mode (for initial auth handshake). A dummy value works —
            # actual API calls go through Bedrock via AWS credentials.
            "ANTHROPIC_API_KEY": "bedrock-mode-no-key-needed",
        }
        if brief.aws_region:
            env["AWS_REGION"] = brief.aws_region
        if brief.aws_access_key:
            env["AWS_ACCESS_KEY_ID"] = brief.aws_access_key
        if brief.aws_secret_key:
            env["AWS_SECRET_ACCESS_KEY"] = brief.aws_secret_key
        return env
    return {}
