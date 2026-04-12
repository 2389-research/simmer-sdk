# ABOUTME: Direct Anthropic API agent loop — replaces ClaudeSDKClient subprocess.
# ABOUTME: Tool-use loop using Messages API for Read/Edit/Write/Grep/Glob/Bash.

"""Direct API agent loop for Anthropic/Bedrock.

Replaces the Claude Agent SDK (ClaudeSDKClient) which spawns Claude Code CLI
as a Node.js subprocess. This uses the Anthropic Messages API directly with
tool_use, eliminating subprocess hangs, zombie processes, and startup overhead.

Mirrors the structure of local_agent.py but uses anthropic.AsyncAnthropic
instead of the OpenAI-compatible Ollama endpoint.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
from typing import Any, Optional

from simmer_sdk.tools import execute_tool, get_anthropic_tool_defs

logger = logging.getLogger(__name__)


class AgentLoopError(Exception):
    """Raised when the agent loop fails to produce a usable response."""
    pass


async def run_api_agent(
    prompt: str,
    client: Any,  # anthropic.AsyncAnthropic or AsyncAnthropicBedrock
    model: str,
    tools: Optional[list[str]] = None,
    custom_tools: Optional[dict[str, dict]] = None,
    cwd: Optional[str] = None,
    system_prompt: Optional[str] = None,
    max_turns: int = 25,
    max_tokens: int = 8192,
    usage_tracker: Optional[Any] = None,  # UsageTracker instance
    usage_role: str = "agent",  # Role label for usage tracking
) -> str:
    """Run an agent loop using the Anthropic Messages API with tool_use.

    Args:
        prompt: The task prompt for this agent.
        client: Async Anthropic client (AsyncAnthropic or AsyncAnthropicBedrock).
        model: Model ID, e.g. "claude-sonnet-4-6".
        tools: List of built-in tool names (e.g., ["Read", "Grep", "Glob"]).
        custom_tools: Dict of custom tools: {"name": {"function": fn, "schema": {...}}}.
        cwd: Working directory for file operations.
        system_prompt: Optional system prompt.
        max_turns: Maximum tool-use turns before returning best effort.
        max_tokens: Max output tokens per API call.

    Returns:
        The final text response from the model.
    """
    # Build tool definitions
    tool_defs = []
    custom_fns: dict[str, Any] = {}

    if tools:
        tool_defs.extend(get_anthropic_tool_defs(tools))

    if custom_tools:
        for name, tool_def in custom_tools.items():
            schema = tool_def.get("schema")
            fn = tool_def.get("function")
            if schema and fn:
                tool_defs.append(schema)
                schema_name = schema.get("name", name)
                custom_fns[schema_name] = fn

    # Resolve cwd — pass to tools, do NOT os.chdir (process-global, breaks concurrency)
    resolved_cwd = cwd or os.getcwd()

    messages: list[dict] = [{"role": "user", "content": prompt}]
    last_text = ""

    # Track duplicate tool calls for loop-breaking
    last_tool_call: Optional[tuple[str, str]] = None
    duplicate_count = 0

    try:
        for turn in range(max_turns):
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if tool_defs:
                kwargs["tools"] = tool_defs
            if system_prompt:
                kwargs["system"] = system_prompt

            # Strip tools on final turn to force text response
            if turn == max_turns - 1 and "tools" in kwargs:
                del kwargs["tools"]

            logger.debug("API agent turn %d/%d: sending %d messages", turn + 1, max_turns, len(messages))
            response = await client.messages.create(**kwargs)

            # Track usage per turn
            if usage_tracker and hasattr(response, "usage") and response.usage:
                usage_tracker.record(model, usage_role, response)

            # Collect text from this response
            for block in response.content:
                if hasattr(block, "text"):
                    last_text = block.text

            # Done — model produced final text
            if response.stop_reason == "end_turn":
                logger.debug("API agent done at turn %d, %d chars", turn + 1, len(last_text))
                return _extract_text(response)

            # Model wants to use tools
            if response.stop_reason == "tool_use":
                # Append assistant turn with full content (must include tool_use blocks)
                messages.append({"role": "assistant", "content": response.content})

                # Execute tool calls
                tool_results = []
                should_break = False

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input

                    # Duplicate detection
                    call_sig = (tool_name, json.dumps(tool_input, sort_keys=True))
                    if call_sig == last_tool_call:
                        duplicate_count += 1
                        if duplicate_count >= 2:
                            logger.warning("Breaking: duplicate tool call %s x%d", tool_name, duplicate_count + 1)
                            should_break = True
                            break
                    else:
                        duplicate_count = 0
                        last_tool_call = call_sig

                    logger.debug("  Tool: %s(%s)", tool_name, list(tool_input.keys()))

                    # Execute — check custom tools first, then built-in
                    if tool_name in custom_fns:
                        try:
                            fn = custom_fns[tool_name]
                            if inspect.iscoroutinefunction(fn):
                                result = await fn(**tool_input)
                            else:
                                result = fn(**tool_input)
                        except Exception as e:
                            result = f"ERROR: Custom tool '{tool_name}' failed: {type(e).__name__}: {e}"
                    else:
                        result = execute_tool(tool_name, tool_input, resolved_cwd)

                    # Truncate large results
                    result_str = str(result)
                    if len(result_str) > 20000:
                        result_str = result_str[:20000] + "\n... (truncated)"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                if should_break:
                    break

                # Append tool results as user turn
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason — treat as complete
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return _extract_text(response)

        # Max turns reached
        logger.warning("API agent hit max_turns=%d — returning best effort", max_turns)
        if last_text:
            return last_text
        return _extract_text(response) if response else ""

    finally:
        pass  # No cleanup needed — cwd is passed to tools, not set globally


def _extract_text(response) -> str:
    """Extract text content from an Anthropic Messages API response."""
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts).strip()
