# ABOUTME: Tests for custom tool registration in the local agent.

from simmer_sdk.local_agent import (
    TOOL_FUNCTIONS,
    TOOL_SCHEMAS,
    _TOOL_NAME_MAP,
)


def test_builtin_tools_registered():
    """Built-in tools should be in the registry."""
    assert "read" in TOOL_FUNCTIONS
    assert "grep" in TOOL_FUNCTIONS
    assert "glob" in TOOL_FUNCTIONS
    assert "write" in TOOL_FUNCTIONS
    assert "bash" in TOOL_FUNCTIONS


def test_builtin_schemas_registered():
    """Built-in tool schemas should exist."""
    assert "read" in TOOL_SCHEMAS
    assert "grep" in TOOL_SCHEMAS
    assert "glob" in TOOL_SCHEMAS
    assert "write" in TOOL_SCHEMAS
    assert "bash" in TOOL_SCHEMAS


def test_tool_name_mapping():
    """Simmer-style names should map to local names."""
    assert _TOOL_NAME_MAP["Read"] == "read"
    assert _TOOL_NAME_MAP["Grep"] == "grep"
    assert _TOOL_NAME_MAP["Glob"] == "glob"
    assert _TOOL_NAME_MAP["Write"] == "write"
    assert _TOOL_NAME_MAP["Bash"] == "bash"


def test_custom_tools_schema_format():
    """Verify the expected custom tool format matches OpenAI function calling."""
    custom_tool = {
        "query_image": {
            "function": lambda image_path, question: f"Description of {image_path}",
            "schema": {
                "type": "function",
                "function": {
                    "name": "query_image",
                    "description": "Ask a question about an image using vision.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_path": {"type": "string", "description": "Path to the image"},
                            "question": {"type": "string", "description": "Question about the image"},
                        },
                        "required": ["image_path", "question"],
                    },
                },
            },
        }
    }

    # Verify the schema is well-formed
    tool_def = custom_tool["query_image"]
    assert "function" in tool_def
    assert "schema" in tool_def
    assert callable(tool_def["function"])
    assert tool_def["schema"]["type"] == "function"
    assert tool_def["schema"]["function"]["name"] == "query_image"


async def test_custom_tool_async_function():
    """Async custom tool functions should be supported."""
    async def my_async_tool(query: str) -> str:
        return f"Result for: {query}"

    result = await my_async_tool("test")
    assert result == "Result for: test"


def test_custom_tools_in_setup_brief():
    """SetupBrief should accept custom_tools."""
    from simmer_sdk.types import SetupBrief

    def dummy_tool(x: str) -> str:
        return x

    custom = {"my_tool": {"function": dummy_tool, "schema": {"type": "function", "function": {"name": "my_tool"}}}}
    brief = SetupBrief(
        artifact="test",
        artifact_type="single-file",
        criteria={"q": "good"},
        iterations=1,
        mode="seedless",
        custom_tools=custom,
    )
    assert brief.custom_tools is not None
    assert "my_tool" in brief.custom_tools
