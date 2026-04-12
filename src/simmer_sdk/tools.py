# ABOUTME: Shared tool implementations and schemas for agent loops.
# ABOUTME: Read, Edit, Write, Grep, Glob, Bash — used by both api_agent and local_agent.

"""Shared tool implementations for simmer agent loops.

Provides filesystem tools (Read, Edit, Write, Grep, Glob, Bash) with both
Python implementations and JSON schemas for LLM tool-use APIs. Used by
api_agent.py (Anthropic API) and local_agent.py (Ollama).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_read(file_path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read a file and return numbered lines."""
    try:
        p = Path(file_path)
        if not p.exists():
            return f"ERROR: File not found: {file_path}. Use Glob to list available files."
        if p.is_dir():
            return f"ERROR: {file_path} is a directory, not a file. Use Glob to list its contents."
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()

        start_idx = max(0, start_line - 1)  # convert to 0-indexed
        end_idx = end_line if end_line else len(lines)
        selected = lines[start_idx:end_idx]
        numbered = [f"{i + start_idx + 1}\t{line}" for i, line in enumerate(selected)]
        result = "\n".join(numbered)

        # Hard cap to prevent context flooding
        if len(result) > 50_000:
            result = result[:50_000] + f"\n\n[TRUNCATED: file has {len(lines)} lines]"
        return result
    except Exception as e:
        return f"ERROR reading {file_path}: {e}"


def tool_edit(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Find and replace text in a file. old_string must be unique unless replace_all=True."""
    try:
        p = Path(file_path)
        if not p.exists():
            return f"ERROR: File not found: {file_path}"

        content = p.read_text(encoding="utf-8", errors="replace")
        count = content.count(old_string)

        if count == 0:
            return (
                f"ERROR: old_string not found in {file_path}. "
                f"Make sure you're matching the exact text including whitespace and indentation."
            )
        if count > 1 and not replace_all:
            return (
                f"ERROR: old_string found {count} times in {file_path}. "
                f"Provide more surrounding context to make it unique, or set replace_all=true."
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
            replacements = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replacements = 1

        p.write_text(new_content, encoding="utf-8")
        return f"Edited {file_path}: {replacements} replacement(s) made."
    except Exception as e:
        return f"ERROR editing {file_path}: {e}"


def tool_write(file_path: str, content: str, cwd: str | None = None) -> str:
    """Write content to a file, creating directories as needed.

    For known simmer artifact filenames, normalizes to cwd to prevent
    models from creating nested directory structures.
    """
    try:
        p = Path(file_path)
        base = Path(cwd) if cwd else Path.cwd()
        basename = p.name

        known_patterns = ("iteration-", "trajectory.md", "result.md", "seed.md")
        if any(basename.startswith(pat) or basename == pat for pat in known_patterns):
            p = base / basename
        elif not p.is_absolute():
            p = base / p

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {p}"
    except Exception as e:
        return f"ERROR writing {file_path}: {e}"


def tool_grep(pattern: str, path: str = ".", context_lines: int = 2,
              glob_filter: str = "", max_results: int = 50) -> str:
    """Search file contents with regex, return matching lines with context."""
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"ERROR: invalid regex: {e}"

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
        if not fp.is_file() or fp.stat().st_size > 1_000_000:
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if regex.search(line):
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    ctx = lines[start:end]
                    header = f"--- {fp} (line {i + 1}) ---"
                    results.append(header + "\n" + "\n".join(ctx))
                    if len(results) >= max_results:
                        results.append(f"[TRUNCATED: {max_results} match limit — refine your pattern]")
                        return "\n\n".join(results)
        except Exception:
            continue

    if not results:
        return f"No matches for pattern '{pattern}' in {path}"
    return "\n\n".join(results)


def tool_glob(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern."""
    search_path = Path(path)
    if not search_path.exists():
        return f"ERROR: path not found: {path}. Check the directory exists."
    matches = sorted(search_path.glob(pattern))
    if not matches:
        return f"No files matching '{pattern}' in {path}"
    return "\n".join(str(m) for m in matches[:100])


def tool_bash(command: str, cwd: str = ".") -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code {result.returncode})"
        return output[:10000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 30s"
    except Exception as e:
        return f"ERROR executing command: {e}"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS: dict[str, Any] = {
    "Read": tool_read,
    "Edit": tool_edit,
    "Write": tool_write,
    "Grep": tool_grep,
    "Glob": tool_glob,
    "Bash": tool_bash,
}

# Map of alternative names
TOOL_ALIASES: dict[str, str] = {
    "read": "Read",
    "edit": "Edit",
    "write": "Write",
    "grep": "Grep",
    "glob": "Glob",
    "bash": "Bash",
}


def execute_tool(name: str, inputs: dict, cwd: str) -> str:
    """Execute a tool by name. Returns result string (never raises)."""
    # Resolve aliases
    canonical = TOOL_ALIASES.get(name, name)
    fn = TOOL_FUNCTIONS.get(canonical)
    if not fn:
        return f"ERROR: Unknown tool '{name}'"

    def _resolve_path(raw: str) -> str:
        """Resolve a path against cwd if relative."""
        p = Path(raw)
        if not p.is_absolute():
            p = Path(cwd) / p
        return str(p)

    try:
        if canonical == "Read":
            path = inputs.get("path", inputs.get("file_path", ""))
            return fn(file_path=_resolve_path(path),
                      start_line=inputs.get("start_line", 1),
                      end_line=inputs.get("end_line"))
        elif canonical == "Edit":
            path = inputs.get("path", inputs.get("file_path", ""))
            return fn(file_path=_resolve_path(path),
                      old_string=inputs.get("old_string", ""),
                      new_string=inputs.get("new_string", ""),
                      replace_all=inputs.get("replace_all", False))
        elif canonical == "Write":
            path = inputs.get("path", inputs.get("file_path", ""))
            return fn(file_path=_resolve_path(path),
                      content=inputs.get("content", ""),
                      cwd=cwd)
        elif canonical == "Grep":
            path = inputs.get("path", cwd)
            return fn(pattern=inputs.get("pattern", ""),
                      path=_resolve_path(path),
                      context_lines=inputs.get("context_lines", 2),
                      glob_filter=inputs.get("glob_filter", ""))
        elif canonical == "Glob":
            path = inputs.get("path", inputs.get("cwd", cwd))
            return fn(pattern=inputs.get("pattern", ""),
                      path=_resolve_path(path))
        elif canonical == "Bash":
            return fn(command=inputs.get("command", ""), cwd=cwd)
        else:
            return fn(**inputs)
    except Exception as e:
        return f"ERROR: Tool '{name}' failed: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Anthropic API tool schemas
# ---------------------------------------------------------------------------

ANTHROPIC_TOOL_SCHEMAS: dict[str, dict] = {
    "Read": {
        "name": "Read",
        "description": (
            "Read the contents of a file. Returns numbered lines. "
            "For large files, use start_line and end_line to read specific sections "
            "rather than the entire file — this saves tokens and keeps context focused. "
            "Do not re-read files already in your context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file to read."},
                "start_line": {"type": "integer", "description": "First line to read (1-indexed). Optional."},
                "end_line": {"type": "integer", "description": "Last line to read (inclusive). Optional."},
            },
            "required": ["path"],
        },
    },
    "Edit": {
        "name": "Edit",
        "description": (
            "Find and replace text in a file. old_string must exactly match text in the file "
            "(including whitespace and indentation). It must be unique in the file unless "
            "replace_all is true. Use this for surgical changes — do not rewrite entire files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the file to edit."},
                "old_string": {"type": "string", "description": "Exact text to find and replace."},
                "new_string": {"type": "string", "description": "Replacement text."},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences. Default false."},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    "Write": {
        "name": "Write",
        "description": (
            "Write content to a file, creating parent directories as needed. "
            "Overwrites existing files. Prefer Edit for modifying existing files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to write to."},
                "content": {"type": "string", "description": "Full content to write."},
            },
            "required": ["path", "content"],
        },
    },
    "Grep": {
        "name": "Grep",
        "description": (
            "Search for a regex pattern in files. Returns matching lines with context. "
            "Use targeted patterns rather than broad ones. Results truncated at 50 matches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for."},
                "path": {"type": "string", "description": "File or directory to search. Recursive for directories."},
                "context_lines": {"type": "integer", "description": "Lines of context around each match. Default: 2."},
            },
            "required": ["pattern", "path"],
        },
    },
    "Glob": {
        "name": "Glob",
        "description": (
            "List files matching a glob pattern. Use to discover what files exist "
            "before reading or grepping them. Returns sorted list of paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.json', '**/*.md'."},
                "path": {"type": "string", "description": "Directory to search in."},
            },
            "required": ["pattern"],
        },
    },
    "Bash": {
        "name": "Bash",
        "description": "Execute a shell command. Timeout: 30s. Output truncated at 10K chars.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
            },
            "required": ["command"],
        },
    },
}

# OpenAI-compatible schemas (for Ollama)
OPENAI_TOOL_SCHEMAS: dict[str, dict] = {
    name: {
        "type": "function",
        "function": {
            "name": name.lower(),
            "description": schema["description"],
            "parameters": schema["input_schema"],
        },
    }
    for name, schema in ANTHROPIC_TOOL_SCHEMAS.items()
}


def get_anthropic_tool_defs(tool_names: list[str]) -> list[dict]:
    """Get Anthropic API tool definitions for the given tool names."""
    return [ANTHROPIC_TOOL_SCHEMAS[name] for name in tool_names if name in ANTHROPIC_TOOL_SCHEMAS]


def get_openai_tool_defs(tool_names: list[str]) -> list[dict]:
    """Get OpenAI-compatible tool definitions for the given tool names."""
    return [OPENAI_TOOL_SCHEMAS[name] for name in tool_names if name in OPENAI_TOOL_SCHEMAS]
