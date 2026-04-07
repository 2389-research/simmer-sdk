"""Local agent loop for Ollama — replaces ClaudeSDKClient for local model dispatch.

Implements a simple tool-calling agent loop using OpenAI-compatible chat completions
pointed at Ollama. The agent sends a prompt, checks for tool calls, executes them
locally (Read, Grep, Glob, Write), appends results, and repeats until done.

This is the standard pattern for local LLM agents — no Claude CLI needed.
"""

from __future__ import annotations

import glob as glob_mod
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Tool implementations — pure Python filesystem operations
# ---------------------------------------------------------------------------


def _tool_read(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a file and return numbered lines."""
    try:
        p = Path(file_path)
        if not p.exists():
            return f"Error: file not found: {file_path}"
        if p.is_dir():
            return f"Error: {file_path} is a directory, not a file"
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[offset : offset + limit]
        numbered = [f"{i + offset + 1}\t{line}" for i, line in enumerate(selected)]
        return "\n".join(numbered)
    except Exception as e:
        return f"Error reading {file_path}: {e}"


def _tool_grep(pattern: str, path: str = ".", glob_filter: str = "", max_results: int = 50) -> str:
    """Search file contents with regex, return matching lines with file:line prefix."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: invalid regex: {e}"

    results: list[str] = []
    search_path = Path(path)

    if search_path.is_file():
        files = [search_path]
    else:
        if glob_filter:
            files = list(search_path.rglob(glob_filter))
        else:
            files = list(search_path.rglob("*"))

    for fp in files:
        if not fp.is_file():
            continue
        # Skip binary/large files
        if fp.stat().st_size > 1_000_000:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{fp}:{i}: {line}")
                    if len(results) >= max_results:
                        return "\n".join(results) + f"\n... (truncated at {max_results} matches)"
        except Exception:
            continue

    if not results:
        return f"No matches for pattern '{pattern}' in {path}"
    return "\n".join(results)


def _tool_glob(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern."""
    search_path = Path(path)
    if not search_path.exists():
        return f"Error: path not found: {path}"

    matches = sorted(search_path.glob(pattern))
    if not matches:
        return f"No files matching '{pattern}' in {path}"
    return "\n".join(str(m) for m in matches[:100])


def _tool_write(file_path: str, content: str) -> str:
    """Write content to a file, creating directories as needed.

    If the file_path matches a known candidate pattern (iteration-N-candidate.md,
    trajectory.md, etc.), write it directly in cwd regardless of what path prefix
    the model constructs. Models often duplicate or mangle the cwd in paths.
    """
    try:
        p = Path(file_path)
        cwd = Path.cwd()
        basename = p.name

        # For known simmer artifact filenames, always write to cwd/basename.
        # This prevents models from creating nested directory structures when
        # they construct paths like /cwd/cwd/iteration-1-candidate.md.
        known_patterns = ("iteration-", "trajectory.md", "result.md", "seed.md")
        if any(basename.startswith(pat) or basename == pat for pat in known_patterns):
            p = cwd / basename
        elif not p.is_absolute():
            p = cwd / p

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {p}"
    except Exception as e:
        return f"Error writing {file_path}: {e}"


def _tool_bash(command: str, cwd: str = ".") -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code {result.returncode})"
        return output[:10000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s"
    except Exception as e:
        return f"Error executing command: {e}"


# ---------------------------------------------------------------------------
# Tool registry and schemas
# ---------------------------------------------------------------------------


TOOL_FUNCTIONS = {
    "read": _tool_read,
    "grep": _tool_grep,
    "glob": _tool_glob,
    "write": _tool_write,
    "bash": _tool_bash,
}

# OpenAI function-calling tool definitions
TOOL_SCHEMAS: dict[str, dict] = {
    "read": {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a file from the filesystem. Returns numbered lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file"},
                    "offset": {"type": "integer", "description": "Line number to start from (0-indexed)", "default": 0},
                    "limit": {"type": "integer", "description": "Max lines to read", "default": 2000},
                },
                "required": ["file_path"],
            },
        },
    },
    "grep": {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents with regex pattern. Returns matching lines with file:line prefix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "File or directory to search in", "default": "."},
                    "glob_filter": {"type": "string", "description": "Glob pattern to filter files (e.g. '*.py')", "default": ""},
                },
                "required": ["pattern"],
            },
        },
    },
    "glob": {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files matching a glob pattern. Returns one path per line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                    "path": {"type": "string", "description": "Directory to search in", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    "write": {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write content to a file. Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to write to"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
}

# Map simmer tool names to our local tool names
_TOOL_NAME_MAP = {
    "Read": "read",
    "Grep": "grep",
    "Glob": "glob",
    "Write": "write",
    "Edit": "write",  # Edit mapped to write for simplicity
    "Bash": "bash",
}


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def run_local_agent(
    prompt: str,
    model: str,
    ollama_url: str = "http://localhost:11434",
    tools: Optional[list[str]] = None,
    custom_tools: Optional[dict[str, dict]] = None,
    cwd: Optional[str] = None,
    max_turns: int = 20,
) -> str:
    """Run a local agent loop with tool calling via Ollama.

    Args:
        prompt: The initial prompt/task for the agent.
        model: Ollama model tag (e.g., "gemma4:31b").
        ollama_url: Ollama server URL.
        tools: List of built-in tool names (e.g., ["Read", "Grep", "Glob"]).
        custom_tools: Dict of custom tools to make available. Each entry:
            {"tool_name": {"function": callable, "schema": {...}}}
            Schema follows OpenAI function calling format:
            {"type": "function", "function": {"name": "...", "description": "...",
             "parameters": {...}}}
            Functions can be sync or async. Async functions are awaited.
        cwd: Working directory for file operations.
        max_turns: Maximum number of tool-call rounds.

    Returns:
        The agent's final text response.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url=f"{ollama_url}/v1",
        api_key="ollama",
    )

    # Build tool list from requested built-in tools + custom tools
    tool_defs = []
    available_tools: dict[str, Any] = {}
    if tools:
        for tool_name in tools:
            local_name = _TOOL_NAME_MAP.get(tool_name, tool_name.lower())
            if local_name in TOOL_SCHEMAS:
                tool_defs.append(TOOL_SCHEMAS[local_name])
                available_tools[local_name] = TOOL_FUNCTIONS[local_name]

    # Register custom tools
    if custom_tools:
        for tool_name, tool_def in custom_tools.items():
            schema = tool_def.get("schema")
            fn = tool_def.get("function")
            if schema and fn:
                tool_defs.append(schema)
                available_tools[tool_name] = fn

    messages: list[dict] = [{"role": "user", "content": prompt}]

    # Set working directory for relative paths
    original_cwd = os.getcwd()
    if cwd:
        os.chdir(cwd)

    import logging
    logger = logging.getLogger("simmer_sdk.local_agent")

    final_text = ""
    # Track last tool call for duplicate detection (loop-breaking)
    last_tool_call: Optional[tuple[str, str]] = None
    duplicate_count = 0

    try:
        for turn in range(max_turns):
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": 16384,
            }
            # On the final turn, strip tools to force a text response
            if tool_defs and turn < max_turns - 1:
                kwargs["tools"] = tool_defs

            logger.debug(f"Turn {turn}/{max_turns}: sending {len(messages)} messages")
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            # Collect any text content (models can return text + tool calls together)
            if message.content:
                final_text += message.content

            # Build assistant message for history — avoid model_dump() which adds
            # an `index` field to tool_calls that Gemma rejects
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if message.content:
                assistant_msg["content"] = message.content
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(assistant_msg)

            # Check for tool calls
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Duplicate detection — break if same call twice in a row
                    call_sig = (fn_name, tool_call.function.arguments)
                    if call_sig == last_tool_call:
                        duplicate_count += 1
                        if duplicate_count >= 2:
                            logger.warning(f"  Breaking: duplicate tool call {fn_name} x{duplicate_count+1}")
                            # Force text response on next turn by not appending tool result
                            break
                    else:
                        duplicate_count = 0
                        last_tool_call = call_sig

                    logger.debug(f"  Tool: {fn_name}({list(fn_args.keys())})")

                    # Execute the tool (supports both sync and async functions)
                    fn = available_tools.get(fn_name)
                    if fn:
                        import inspect
                        if inspect.iscoroutinefunction(fn):
                            result = await fn(**fn_args)
                        else:
                            result = fn(**fn_args)
                    else:
                        result = f"Error: unknown tool '{fn_name}'"

                    # Truncate large tool results to prevent context blowup
                    result_str = str(result)
                    if len(result_str) > 20000:
                        result_str = result_str[:20000] + "\n... (truncated)"

                    # Append tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_str,
                    })
                else:
                    # All tool calls processed — continue the loop
                    continue
                # Break from duplicate detection hit the inner break
                break
            else:
                # No tool calls — agent is done
                logger.debug(f"  Done at turn {turn}, {len(final_text)} chars")
                break

        else:
            # Exhausted max_turns
            logger.warning(f"  Exhausted {max_turns} turns, returning partial response")

    finally:
        if cwd:
            os.chdir(original_cwd)

    return final_text
