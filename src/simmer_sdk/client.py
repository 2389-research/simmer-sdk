"""Client factory for Anthropic API and AWS Bedrock.

When api_provider="bedrock", creates AsyncAnthropicBedrock clients and maps
model IDs to Bedrock format. When api_provider="anthropic" (default), uses
AsyncAnthropic with ANTHROPIC_API_KEY from environment.

For ClaudeSDKClient (Agent SDK) calls, Bedrock is configured via env vars
passed through ClaudeAgentOptions(env={...}). The bundled Claude CLI handles
routing internally when CLAUDE_CODE_USE_BEDROCK=1 is set.
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


def create_async_client(brief: SetupBrief):
    """Create an async Anthropic client based on the API provider config.

    Returns AsyncAnthropic for direct API, AsyncAnthropicBedrock for Bedrock.
    """
    if brief.api_provider == "bedrock":
        from anthropic import AsyncAnthropicBedrock
        return AsyncAnthropicBedrock(
            aws_access_key=brief.aws_access_key,
            aws_secret_key=brief.aws_secret_key,
            aws_region=brief.aws_region,
        )
    else:
        from anthropic import AsyncAnthropic
        return AsyncAnthropic()


def map_model_id(model: str, brief: SetupBrief) -> str:
    """Map a direct API model ID to the appropriate provider format.

    For Bedrock, translates claude-sonnet-4-6 -> us.anthropic.claude-sonnet-4-6-v1:0.
    Passes through unknown IDs unchanged (caller may have specified a Bedrock ID directly).
    For direct API, returns the model ID unchanged.
    """
    if brief.api_provider != "bedrock":
        return model
    return BEDROCK_MODEL_MAP.get(model, model)


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
    For direct API, returns empty dict (SDK uses ANTHROPIC_API_KEY from env).
    """
    if brief.api_provider != "bedrock":
        return {}
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
