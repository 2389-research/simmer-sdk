# ABOUTME: Dispatch resolution — determines which agent backend to use.
# ABOUTME: Routes between Ollama (local_agent), direct API (api_agent), and CLI (ClaudeSDKClient).

"""Dispatch resolution for agent backends."""

from __future__ import annotations

from simmer_sdk.types import SetupBrief


def resolve_dispatch(brief: SetupBrief) -> str:
    """Resolve which dispatch method to use: 'ollama', 'api', or 'cli'.

    - ``"ollama"`` — local models via Ollama (OpenAI-compatible API)
    - ``"api"`` — direct Anthropic Messages API with tool_use (no subprocess)
    - ``"cli"`` — Claude Agent SDK / Claude Code CLI subprocess (legacy)

    When ``agent_dispatch="auto"`` (default):
    - Ollama provider → ``"ollama"``
    - Anthropic/Bedrock provider → ``"api"``

    Set ``agent_dispatch="cli"`` explicitly to use the legacy subprocess path.
    """
    dispatch = getattr(brief, "agent_dispatch", "auto")
    valid = {"auto", "api", "cli"}
    if dispatch not in valid:
        raise ValueError(f"agent_dispatch must be one of {valid}, got {dispatch!r}")

    if brief.api_provider == "ollama":
        return "ollama"

    if dispatch == "api":
        return "api"
    if dispatch == "cli":
        return "cli"

    # auto: default to direct API for cloud providers
    return "api"
