# ABOUTME: Generator subagent dispatch and output parsing.
# ABOUTME: Sends candidates to Claude Agent SDK for improvement based on ASI feedback.

from __future__ import annotations

import re
from dataclasses import dataclass, field

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, TextBlock

from simmer_sdk.prompts import build_generator_prompt
from simmer_sdk.types import SetupBrief


@dataclass
class GeneratorOutput:
    """Output from the generator subagent."""

    candidate: str
    report: str
    files_modified: list[str] = field(default_factory=list)


def _parse_generator_output(result_text: str, brief: SetupBrief) -> GeneratorOutput:
    """Parse the generator subagent output into a GeneratorOutput."""
    # Extract report from result text
    report = result_text[:500] if result_text else ""

    # Try to extract a more structured report if present
    report_match = re.search(
        r"(?:report|summary|changes?)[:\s]+(.+?)(?:\n\n|\Z)",
        result_text,
        re.IGNORECASE | re.DOTALL,
    )
    if report_match:
        report = report_match.group(1).strip()[:500]

    # Extract files_modified if mentioned
    files_modified: list[str] = []
    files_match = re.search(
        r"[Ff]iles? (?:modified|changed|updated)[:\s]+(.+?)(?:\n\n|\Z)",
        result_text,
        re.DOTALL,
    )
    if files_match:
        raw = files_match.group(1).strip()
        # Split by newlines or commas, strip whitespace and bullet chars
        files_modified = [
            f.strip().lstrip("-* ").strip()
            for f in re.split(r"[\n,]+", raw)
            if f.strip().lstrip("-* ").strip()
        ]

    # For single-file mode, the entire result text is the candidate artifact
    candidate = result_text

    return GeneratorOutput(
        candidate=candidate,
        report=report,
        files_modified=files_modified,
    )


async def _split_generate(
    brief: SetupBrief,
    iteration: int,
    current_candidate: str,
    asi: str,
    original_description: str | None = None,
    regression_note: str | None = None,
) -> GeneratorOutput:
    """Split generator: architect (generator_model) plans, executor (clerk_model) writes.

    The architect model writes a detailed contract specifying exactly what
    changes to make. The executor model takes the contract + current artifact
    and produces the full new version. This lets a stronger model direct a
    cheaper model, reducing output token cost.
    """
    from simmer_sdk.client import create_async_client, map_model_id, extract_text

    client = create_async_client(brief)

    # Step 1: Architect writes the contract
    architect_prompt = (
        f"You are the architect in a simmer refinement loop (iteration {iteration}).\n\n"
        f"CURRENT ARTIFACT:\n{current_candidate}\n\n"
        f"ASI (single most impactful improvement):\n{asi}\n\n"
    )
    if original_description:
        architect_prompt += f"ORIGINAL DESCRIPTION:\n{original_description}\n\n"
    if regression_note:
        architect_prompt += f"REGRESSION NOTE:\n{regression_note}\n\n"

    architect_prompt += (
        "Write a DETAILED CONTRACT for how to improve this artifact. "
        "A junior writer will follow your contract to produce the new version.\n\n"
        "Your contract must specify:\n"
        "1. PRESERVE: What sections/elements to keep exactly as-is\n"
        "2. MODIFY: What to change, with exact instructions for each change\n"
        "3. ADD: What new content to create, with detailed specs\n"
        "4. REMOVE: What to cut\n"
        "5. STRUCTURE: The overall organization of the final output\n\n"
        "Be specific enough that someone who hasn't seen the ASI reasoning "
        "could follow your contract and produce the right result."
    )

    architect_model = map_model_id(brief.generator_model, brief)
    architect_response = await client.messages.create(
        model=architect_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": architect_prompt}],
    )
    contract = extract_text(architect_response)

    if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
        brief._usage_tracker.record(architect_model, "generator_architect", architect_response)

    # Step 2: Executor produces the artifact from the contract
    executor_prompt = (
        f"You are a skilled writer executing a contract to improve an artifact.\n\n"
        f"CURRENT ARTIFACT:\n{current_candidate}\n\n"
        f"CONTRACT (follow exactly):\n{contract}\n\n"
        f"Produce the complete improved artifact. Output ONLY the artifact text — "
        f"no commentary, no explanation of changes, no preamble."
    )

    executor_model = map_model_id(brief.clerk_model, brief)
    executor_response = await client.messages.create(
        model=executor_model,
        max_tokens=16384,
        messages=[{"role": "user", "content": executor_prompt}],
    )
    candidate = extract_text(executor_response)

    if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
        brief._usage_tracker.record(executor_model, "generator_executor", executor_response)

    return GeneratorOutput(
        candidate=candidate,
        report=f"[split-gen] Contract: {contract[:200]}",
    )


async def dispatch_generator(
    brief: SetupBrief,
    iteration: int,
    current_candidate: str,
    asi: str,
    panel_summary: str | None = None,
    exploration_status: str | None = None,
    original_description: str | None = None,
    regression_note: str | None = None,
) -> GeneratorOutput:
    """Dispatch the generator subagent via the Claude Agent SDK."""
    # Split generator: architect plans, executor writes
    if brief.split_generator and brief.artifact_type != "workspace":
        return await _split_generate(
            brief=brief,
            iteration=iteration,
            current_candidate=current_candidate,
            asi=asi,
            original_description=original_description,
            regression_note=regression_note,
        )

    is_workspace = brief.artifact_type == "workspace"

    workspace_path: str | None = None
    if is_workspace:
        workspace_path = brief.artifact

    prompt = build_generator_prompt(
        iteration=iteration,
        artifact_type=brief.artifact_type,
        criteria=brief.criteria,
        current_candidate=current_candidate,
        asi=asi,
        output_dir=brief.output_dir,
        background=brief.background,
        panel_summary=panel_summary,
        output_contract=brief.output_contract,
        validation_command=brief.validation_command,
        search_space=brief.search_space,
        exploration_status=exploration_status,
        workspace_path=workspace_path,
        original_description=original_description,
        regression_note=regression_note,
    )

    if is_workspace:
        tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
    else:
        tools = ["Read", "Write", "Glob"]

    # Local mode: use Ollama agent loop instead of Claude CLI
    if brief.api_provider == "ollama":
        from simmer_sdk.local_agent import run_local_agent
        result_text = await run_local_agent(
            prompt=prompt,
            model=brief.generator_model,
            ollama_url=brief.ollama_url,
            tools=tools,
            custom_tools=brief.custom_tools,
            cwd=workspace_path if is_workspace else brief.output_dir,
            max_turns=20,
        )
        return _parse_generator_output(result_text, brief)

    from simmer_sdk.client import map_model_id, get_agent_env, get_cli_path
    options = ClaudeAgentOptions(
        tools=tools,
        model=map_model_id(brief.generator_model, brief),
        permission_mode="bypassPermissions",
        cwd=workspace_path if is_workspace else brief.output_dir,
        max_turns=20,
        env=get_agent_env(brief),
        cli_path=get_cli_path(),
    )

    result_text = ""
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                result_text = message.result if hasattr(message, "result") else str(message)

    return _parse_generator_output(result_text, brief)
