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
        "Write a CONTRACT for a less capable model to execute. "
        "You make the architectural decisions — structure, what goes where, "
        "what specific content to include. The executor writes it out.\n\n"
        "Your contract should:\n"
        "- Specify the exact structure (sections, order, approximate length)\n"
        "- Make every important content decision (names, concepts, specifics)\n"
        "- State what to preserve from the current version\n"
        "- State what NOT to do (common mistakes to avoid)\n\n"
        "Think of it like writing a detailed ticket for a junior colleague. "
        "They can write well but shouldn't be making design decisions."
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
        f"You are a writer executing a contract. The contract specifies the STRUCTURE, "
        f"CONTENT, and RULES. Your job is to write excellent prose that follows the "
        f"contract exactly. Do not make structural decisions — those are decided for you.\n\n"
        f"CURRENT ARTIFACT (reference for style and any preserved content):\n{current_candidate}\n\n"
        f"CONTRACT (follow exactly — every name, plot point, and structure is specified):\n{contract}\n\n"
        f"Output ONLY the complete artifact. No commentary, no explanations."
    )

    # Resolve executor model — defaults to clerk_model if not specified
    exec_model_name = brief.executor_model or brief.clerk_model
    exec_model_id = map_model_id(exec_model_name, brief)

    # Route: Anthropic SDK for Claude models, Bedrock Converse API for everything else
    from simmer_sdk.client import is_anthropic_model
    if is_anthropic_model(exec_model_id):
        executor_response = await client.messages.create(
            model=exec_model_id,
            max_tokens=16384,
            messages=[{"role": "user", "content": executor_prompt}],
        )
        candidate = extract_text(executor_response)
        if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
            brief._usage_tracker.record(exec_model_id, "generator_executor", executor_response)
    else:
        # Non-Anthropic Bedrock model (Nova, Llama, Mistral, etc.)
        from simmer_sdk.client import invoke_bedrock_model
        candidate, usage_dict = await invoke_bedrock_model(
            model_id=exec_model_id,
            prompt=executor_prompt,
            brief=brief,
            max_tokens=8192,  # Some models cap lower than 16K
        )
        if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
            brief._usage_tracker.record_tokens(
                exec_model_id, "generator_executor",
                usage_dict.get("input_tokens", 0),
                usage_dict.get("output_tokens", 0),
            )

    # Save contract to disk for inspection
    import os
    out_dir = brief.output_dir
    if out_dir:
        contract_path = os.path.join(out_dir, f"iteration-{iteration}-contract.md")
        try:
            with open(contract_path, "w") as f:
                f.write(contract)
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Failed to save contract: {e}")

    return GeneratorOutput(
        candidate=candidate,
        report=f"[split-gen] Contract: {contract[:200]}",
    )


async def _direct_edit(
    brief: SetupBrief,
    iteration: int,
    current_candidate: str,
    asi: str,
    original_description: str | None = None,
    regression_note: str | None = None,
) -> GeneratorOutput:
    """Direct edit: the strong model (generator_model) surgically improves the artifact.

    Used in hybrid mode for iterations 1+ after the cheap executor produced
    the first draft. The strong model reads the full artifact and the ASI,
    then makes targeted changes — not a full rewrite.
    """
    from simmer_sdk.client import create_async_client, map_model_id, extract_text

    client = create_async_client(brief)

    prompt = (
        f"You are improving an artifact based on judge feedback (iteration {iteration}).\n\n"
        f"CURRENT ARTIFACT:\n{current_candidate}\n\n"
        f"JUDGE FEEDBACK (ASI — single most impactful improvement):\n{asi}\n\n"
    )
    if original_description:
        prompt += f"ORIGINAL DESCRIPTION:\n{original_description}\n\n"
    if regression_note:
        prompt += f"REGRESSION NOTE:\n{regression_note}\n\n"

    prompt += (
        "Make SURGICAL changes to address the ASI feedback. Do not rewrite from scratch. "
        "Preserve everything that works. Add, modify, or restructure only what the ASI "
        "identifies as the highest-leverage improvement.\n\n"
        "Output the COMPLETE improved artifact — not a diff, not commentary."
    )

    model = map_model_id(brief.generator_model, brief)
    response = await client.messages.create(
        model=model,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
    )
    candidate = extract_text(response)

    if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
        brief._usage_tracker.record(model, "generator_edit", response)

    return GeneratorOutput(
        candidate=candidate,
        report=f"[direct-edit] Applied ASI: {asi[:200]}",
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
    # Split generator modes
    if brief.split_generator and brief.artifact_type != "workspace":
        if brief.split_generator_mode == "hybrid" and iteration > 0:
            # Hybrid: iteration 0 uses cheap executor, iterations 1+ use Sonnet direct edits
            return await _direct_edit(
                brief=brief,
                iteration=iteration,
                current_candidate=current_candidate,
                asi=asi,
                original_description=original_description,
                regression_note=regression_note,
            )
        else:
            # Always split (default) or iteration 0 of hybrid
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

    from simmer_sdk.dispatch import resolve_dispatch
    dispatch = resolve_dispatch(brief)
    agent_cwd = workspace_path if is_workspace else brief.output_dir

    if dispatch == "ollama":
        from simmer_sdk.local_agent import run_local_agent
        result_text = await run_local_agent(
            prompt=prompt,
            model=brief.generator_model,
            ollama_url=brief.ollama_url,
            tools=tools,
            custom_tools=brief.custom_tools,
            cwd=agent_cwd,
            max_turns=20,
        )
    elif dispatch == "api":
        from simmer_sdk.api_agent import run_api_agent
        from simmer_sdk.client import create_async_client, map_model_id
        result_text = await run_api_agent(
            prompt=prompt,
            client=create_async_client(brief),
            model=map_model_id(brief.generator_model, brief),
            tools=tools,
            custom_tools=brief.custom_tools,
            cwd=agent_cwd,
            max_turns=20,
        )
    else:
        # CLI dispatch (legacy)
        from simmer_sdk.client import map_model_id, get_agent_env, get_cli_path
        options = ClaudeAgentOptions(
            tools=tools,
            model=map_model_id(brief.generator_model, brief),
            permission_mode="bypassPermissions",
            cwd=agent_cwd,
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
                    if hasattr(brief, "_usage_tracker") and brief._usage_tracker:
                        brief._usage_tracker.record_agent(brief.generator_model, "generator", message)

    return _parse_generator_output(result_text, brief)
