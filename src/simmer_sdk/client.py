# ABOUTME: API client factory for Anthropic, AWS Bedrock, and Ollama providers.
# ABOUTME: Handles model ID mapping, CLI path resolution, and agent environment setup.

"""Client factory for Anthropic API, AWS Bedrock, and Ollama.

When api_provider="bedrock", creates AsyncAnthropicBedrock clients and maps
model IDs to Bedrock format. When api_provider="ollama", creates AsyncAnthropic
clients pointed at Ollama's Anthropic-compatible /v1/messages endpoint.
When api_provider="anthropic" (default), uses AsyncAnthropic with
ANTHROPIC_API_KEY from environment.

For ClaudeSDKClient (Agent SDK) calls, provider config is passed via env vars
through ClaudeAgentOptions(env={...}). Bedrock uses CLAUDE_CODE_USE_BEDROCK=1,
Ollama uses ANTHROPIC_BASE_URL pointed at the Ollama server.
"""

from __future__ import annotations

from simmer_sdk.types import SetupBrief


# Bedrock model ID mapping — callers can pass direct API names and we translate
BEDROCK_MODEL_MAP = {
    # Current models with full date-stamped Bedrock IDs
    "claude-sonnet-4-6": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",  # 4.6 not yet on Bedrock, use 4.5
    "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-haiku-4-5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "claude-opus-4-6": "us.anthropic.claude-opus-4-5-20251101-v1:0",  # 4.6 not yet on Bedrock, use 4.5
    "claude-opus-4-5": "us.anthropic.claude-opus-4-5-20251101-v1:0",
    # Direct API date-stamped IDs
    "claude-sonnet-4-5-20250929": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-haiku-4-5-20251001": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
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


def create_async_client(brief: SetupBrief):
    """Create an async Anthropic client based on the API provider config.

    Returns AsyncAnthropic for direct API and Ollama, AsyncAnthropicBedrock
    for Bedrock. Ollama uses the Anthropic SDK pointed at Ollama's
    /v1/messages endpoint.
    """
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
