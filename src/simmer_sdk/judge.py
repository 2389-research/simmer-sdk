# ABOUTME: Single judge subagent dispatch and score parsing.
# ABOUTME: Parses LLM output into structured scores, reasoning, and ASI.

from __future__ import annotations

import re
from typing import Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

from simmer_sdk.prompts import build_judge_prompt
from simmer_sdk.types import JudgeOutput, SetupBrief


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _normalize_key(key: str) -> str:
    """Normalize a criterion name for comparison: lowercase + spaces → underscores."""
    return re.sub(r"[\s_-]+", "_", key.strip().lower())


def parse_judge_output(result_text: str, criteria: dict[str, str]) -> JudgeOutput:
    """Parse the judge's text output into a structured JudgeOutput.

    Expected format::

        ITERATION [N] SCORES:
          [criterion]: [N]/10 — [reasoning] — [specific improvement]
        COMPOSITE: [N.N]/10

        ASI (highest-leverage direction):
        [text]

    The parser is intentionally lenient to accommodate minor LLM formatting
    drift.
    """
    scores: dict[str, int] = {}
    reasoning: dict[str, str] = {}

    # Build a mapping from normalized key → original criteria key for matching
    criteria_norm: dict[str, str] = {_normalize_key(k): k for k in criteria}

    # Patterns for score lines, e.g.:
    #   criterion_name: 7/10 — reasoning here
    #   criterion_name: 7/10
    #   **criterion_name: 7/10** — reasoning (markdown bold variant)
    #   - criterion_name: 7/10 (bulleted variant)
    score_pattern = re.compile(
        r"^\s*[-*]*\s*\**([A-Za-z][A-Za-z0-9_ \-]*?)\**:\s*(\d+)\s*/\s*10\**\s*(.*)?$",
        re.MULTILINE,
    )

    for match in score_pattern.finditer(result_text):
        raw_name = match.group(1).strip()
        score_val = int(match.group(2))
        rest = (match.group(3) or "").strip().lstrip("—–-").strip()

        # Skip lines that are likely "COMPOSITE: N/10" or similar
        if _normalize_key(raw_name) in ("composite", "total", "overall"):
            continue

        # Match raw_name against known criteria keys
        norm_raw = _normalize_key(raw_name)

        matched_key: Optional[str] = None

        # 1. Exact normalized match
        if norm_raw in criteria_norm:
            matched_key = criteria_norm[norm_raw]

        # 2. Partial match: raw starts with or is contained in a criterion key
        if matched_key is None:
            for norm_crit, orig_key in criteria_norm.items():
                if norm_raw.startswith(norm_crit) or norm_crit.startswith(norm_raw):
                    matched_key = orig_key
                    break

        # 3. Substring match (raw in criterion or vice versa)
        if matched_key is None:
            for norm_crit, orig_key in criteria_norm.items():
                if norm_raw in norm_crit or norm_crit in norm_raw:
                    matched_key = orig_key
                    break

        if matched_key is not None:
            # Keep the first match encountered (highest-context match)
            if matched_key not in scores:
                scores[matched_key] = score_val
                if rest:
                    reasoning[matched_key] = rest

    # ---------------------------------------------------------------------------
    # Extract ASI section
    # ---------------------------------------------------------------------------
    asi = ""

    # Try several header patterns, from most specific to most lenient
    asi_patterns = [
        r"ASI\s*\(highest[- ]leverage direction\)\s*[:\n](.*?)(?=\n[A-Z]{3,}|\Z)",
        r"ASI\s*[:\n](.*?)(?=\n[A-Z]{3,}|\Z)",
        r"(?:highest[- ]leverage direction|single improvement|next step)[:\n](.*?)(?=\n[A-Z]{3,}|\Z)",
    ]

    for pat in asi_patterns:
        m = re.search(pat, result_text, re.IGNORECASE | re.DOTALL)
        if m:
            asi = m.group(1).strip()
            break

    # Fallback: take everything after the last score line / COMPOSITE line
    if not asi:
        composite_match = re.search(r"COMPOSITE:.*$", result_text, re.MULTILINE)
        if composite_match:
            asi = result_text[composite_match.end():].strip()

    return JudgeOutput(
        scores=scores,
        asi=asi,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def dispatch_judge(
    brief: SetupBrief,
    problem_class: str,
    iteration: int,
    candidate: str,
    seed_candidate: Optional[str] = None,
    seed_scores: Optional[dict[str, int]] = None,
    evaluator_output: Optional[str] = None,
    previous_asi: Optional[str] = None,
    iteration_history: Optional[str] = None,
    exploration_status: Optional[str] = None,
    candidate_path: Optional[str] = None,
    evaluator_path: Optional[str] = None,
    prior_candidate_paths: Optional[list[str]] = None,
) -> JudgeOutput:
    """Dispatch a single judge subagent via the Claude Agent SDK.

    Judges receive read-only tool access (Read, Grep, Glob) for investigation.
    Context discipline varies by *problem_class*:
    - ``"text/creative"``: minimal context (no history, no previous ASI).
    - ``"code/testable"`` / ``"pipeline/engineering"``: full context.
    """
    is_workspace = brief.artifact_type == "workspace"
    workspace_path: Optional[str] = brief.artifact if is_workspace else None

    # Resolve judge preamble: use explicit value, or local default for ollama
    preamble = brief.judge_preamble
    if preamble is None and brief.api_provider == "ollama":
        from simmer_sdk.prompts import LOCAL_JUDGE_PREAMBLE
        preamble = LOCAL_JUDGE_PREAMBLE

    prompt = build_judge_prompt(
        iteration=iteration,
        artifact_type=brief.artifact_type,
        problem_class=problem_class,
        criteria=brief.criteria,
        candidate=candidate,
        seed_candidate=seed_candidate,
        seed_scores=seed_scores,
        evaluator_output=evaluator_output,
        previous_asi=previous_asi,
        iteration_history=iteration_history,
        search_space=brief.search_space,
        exploration_status=exploration_status,
        output_contract=brief.output_contract,
        candidate_path=candidate_path,
        evaluator_path=evaluator_path,
        prior_candidate_paths=prior_candidate_paths,
        judge_preamble=preamble,
    )

    # Local mode: use Ollama agent loop instead of Claude CLI
    if brief.api_provider == "ollama":
        from simmer_sdk.local_agent import run_local_agent
        result_text = await run_local_agent(
            prompt=prompt,
            model=brief.judge_model,
            ollama_url=brief.ollama_url,
            tools=["Read", "Grep", "Glob"],
            custom_tools=brief.custom_tools,
            cwd=workspace_path if is_workspace else brief.output_dir,
            max_turns=25,
        )
        output = parse_judge_output(result_text, brief.criteria)
        output.raw_text = result_text
        return output

    from simmer_sdk.client import map_model_id, get_agent_env, get_cli_path
    max_turns = 25

    options = ClaudeAgentOptions(
        tools=["Read", "Grep", "Glob"],
        model=map_model_id(brief.judge_model, brief),
        permission_mode="bypassPermissions",
        cwd=workspace_path if is_workspace else brief.output_dir,
        max_turns=max_turns,
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
                    brief._usage_tracker.record_agent(brief.judge_model, "judge", message)

    output = parse_judge_output(result_text, brief.criteria)
    output.raw_text = result_text
    return output
