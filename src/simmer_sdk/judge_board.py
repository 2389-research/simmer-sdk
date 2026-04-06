# ABOUTME: Judge board orchestration — parallel scoring, deliberation, synthesis.
# ABOUTME: Manages 3-phase judge panel: independent score, cross-review, consensus.

"""Judge Board — board composition, parallel dispatch, deliberation, synthesis.

Orchestrates a panel of 3 judges through three phases:
1. Independent scoring (parallel via anyio task group)
2. Deliberation (one round — each judge sees others' scores, not ASI)
3. Synthesis (consensus scores + single ASI)
"""

from __future__ import annotations

import os
import re
import statistics
from typing import Optional

import anyio
import anthropic
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

from simmer_sdk.judge import parse_judge_output
from simmer_sdk.primitives import get_primitives_for_judge
from simmer_sdk.prompts import (
    build_board_composition_prompt,
    build_board_panelist_prompt,
    build_deliberation_prompt,
    build_synthesis_prompt,
)
from simmer_sdk.types import JudgeDefinition, JudgeOutput, SetupBrief, StableWins


# ---------------------------------------------------------------------------
# Pure Python — consensus scoring
# ---------------------------------------------------------------------------


def compute_consensus_scores(judge_scores: list[dict[str, int]]) -> dict[str, int]:
    """Compute consensus scores from multiple judges using the median.

    For each criterion, collects all judges' scores and takes the median
    (rounded to the nearest int). Works with 2-5 judges.
    """
    # Gather all criteria from all judges
    all_criteria: set[str] = set()
    for scores in judge_scores:
        all_criteria.update(scores.keys())

    consensus: dict[str, int] = {}
    for criterion in sorted(all_criteria):
        values = [s[criterion] for s in judge_scores if criterion in s]
        if values:
            consensus[criterion] = round(statistics.median(values))

    return consensus


# ---------------------------------------------------------------------------
# Board composition
# ---------------------------------------------------------------------------


def _parse_judge_panel(text: str) -> list[JudgeDefinition]:
    """Parse the LLM's JUDGE_PANEL output into JudgeDefinition objects."""
    judges: list[JudgeDefinition] = []

    # Split on "- name:" entries
    entries = re.split(r"(?m)^\s*-\s*name:\s*", text)
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Extract name (first line)
        lines = entry.split("\n", 1)
        name = lines[0].strip()

        # Extract lens
        lens_match = re.search(r"lens:\s*(.+?)(?:\n|$)", entry)
        lens = lens_match.group(1).strip() if lens_match else ""

        # Extract primitives
        primitives: list[str] = []
        prims_match = re.search(r"primitives:\s*\n((?:\s*-\s*.+\n?)+)", entry)
        if prims_match:
            for prim_line in prims_match.group(1).strip().split("\n"):
                prim = re.sub(r"^\s*-\s*", "", prim_line).strip()
                if prim:
                    primitives.append(prim)

        if name and lens:
            judges.append(JudgeDefinition(name=name, lens=lens, primitives=primitives))

    return judges


async def compose_judges(
    brief: SetupBrief,
    problem_class: str,
    candidate_summary: str,
) -> list[JudgeDefinition]:
    """Compose the judge panel for a board run.

    If ``brief.judge_panel`` is set, uses those directly (custom panel).
    Otherwise, dispatches an LLM call to design 3 judges tailored to
    the problem.
    """
    if brief.judge_panel:
        return brief.judge_panel

    prompt = build_board_composition_prompt(
        artifact_summary=candidate_summary,
        criteria=brief.criteria,
        problem_class=problem_class,
        has_evaluator=brief.evaluator is not None,
        background=brief.background,
        search_space=brief.search_space,
        judge_count=brief.judge_count,
    )

    from simmer_sdk.client import create_async_client, map_model_id
    client = create_async_client(brief)
    response = await client.messages.create(
        model=map_model_id(brief.clerk_model, brief),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    from simmer_sdk.client import extract_text
    text = extract_text(response)

    judges = _parse_judge_panel(text)

    # Fallback: if parsing failed, return sensible defaults
    target_count = brief.judge_count or 3
    if len(judges) < target_count:
        defaults = [
            JudgeDefinition(name="Analyst", lens="Evaluate correctness and completeness against criteria"),
            JudgeDefinition(name="Pragmatist", lens="Evaluate practical utility and execution quality"),
            JudgeDefinition(name="Critic", lens="Challenge assumptions and find weaknesses"),
            JudgeDefinition(name="Strategist", lens="Evaluate coherence of approach and long-term viability"),
            JudgeDefinition(name="Empiricist", lens="Evaluate evidence quality and measurable outcomes"),
        ]
        judges = defaults[:target_count]

    return judges[:target_count]


# ---------------------------------------------------------------------------
# Helpers for stripping ASI from judge output text
# ---------------------------------------------------------------------------


def _strip_asi_from_output(output_text: str) -> str:
    """Remove the ASI section from judge output, keeping only scores + reasoning."""
    # Try to find ASI header and strip everything from there
    patterns = [
        r"\n\s*ASI\s*\(highest[- ]leverage direction\).*",
        r"\n\s*ASI\s*:.*",
    ]
    for pat in patterns:
        stripped = re.split(pat, output_text, maxsplit=1, flags=re.IGNORECASE | re.DOTALL)
        if len(stripped) > 1:
            return stripped[0].strip()
    return output_text


# ---------------------------------------------------------------------------
# Phase 1: Independent scoring (parallel)
# ---------------------------------------------------------------------------


async def _dispatch_single_panelist(
    brief: SetupBrief,
    judge_def: JudgeDefinition,
    problem_class: str,
    iteration: int,
    candidate: str,
    seed_candidate: Optional[str] = None,
    seed_scores: Optional[dict[str, int]] = None,
    evaluator_output: Optional[str] = None,
    previous_asi: Optional[str] = None,
    iteration_history: Optional[str] = None,
    exploration_status: Optional[str] = None,
    previous_deliberation: Optional[str] = None,
    candidate_path: Optional[str] = None,
    evaluator_path: Optional[str] = None,
    prior_candidate_paths: Optional[list[str]] = None,
    output_contract: Optional[str] = None,
) -> tuple[str, str, JudgeOutput]:
    """Dispatch a single panelist and return (name, raw_text, parsed_output)."""
    primitives = get_primitives_for_judge(
        has_evaluator=brief.evaluator is not None,
        has_search_space=brief.search_space is not None,
        custom_primitives=judge_def.primitives if judge_def.primitives else None,
    )

    # Resolve judge preamble: use explicit value, or local default for ollama
    preamble = brief.judge_preamble
    if preamble is None and brief.api_provider == "ollama":
        from simmer_sdk.prompts import LOCAL_JUDGE_PREAMBLE
        preamble = LOCAL_JUDGE_PREAMBLE

    prompt = build_board_panelist_prompt(
        judge_def=judge_def,
        iteration=iteration,
        artifact_type=brief.artifact_type,
        problem_class=problem_class,
        criteria=brief.criteria,
        candidate=candidate,
        primitives=primitives,
        seed_candidate=seed_candidate,
        seed_scores=seed_scores,
        evaluator_output=evaluator_output,
        previous_asi=previous_asi,
        iteration_history=iteration_history,
        search_space=brief.search_space,
        exploration_status=exploration_status,
        background=brief.background,
        previous_deliberation=previous_deliberation,
        candidate_path=candidate_path,
        evaluator_path=evaluator_path,
        prior_candidate_paths=prior_candidate_paths,
        output_contract=output_contract,
        judge_preamble=preamble,
    )

    is_workspace = brief.artifact_type == "workspace"
    workspace_path: Optional[str] = brief.artifact if is_workspace else None

    # Local mode: use Ollama agent loop instead of Claude CLI
    if brief.api_provider == "ollama":
        from simmer_sdk.local_agent import run_local_agent
        result_text = await run_local_agent(
            prompt=prompt,
            model=brief.judge_model,
            ollama_url=brief.ollama_url,
            tools=["Read", "Grep", "Glob"],
            cwd=workspace_path if is_workspace else brief.output_dir,
            max_turns=25,
        )
        parsed = parse_judge_output(result_text, brief.criteria)
        return judge_def.name, result_text, parsed

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

    parsed = parse_judge_output(result_text, brief.criteria)
    return judge_def.name, result_text, parsed


# ---------------------------------------------------------------------------
# Phase 2: Deliberation
# ---------------------------------------------------------------------------


async def _deliberate_single(
    model: str,
    judge_name: str,
    own_output: str,
    other_outputs: list[tuple[str, str]],
    brief: Optional[SetupBrief] = None,
) -> tuple[str, str]:
    """Run one judge's deliberation round and return (name, deliberation_text)."""
    from simmer_sdk.client import create_async_client, map_model_id
    prompt = build_deliberation_prompt(
        judge_name=judge_name,
        own_output=own_output,
        other_outputs=other_outputs,
    )

    if brief:
        client = create_async_client(brief)
        resolved_model = map_model_id(model, brief)
    else:
        import anthropic as _anthropic
        client = _anthropic.AsyncAnthropic()
        resolved_model = model

    response = await client.messages.create(
        model=resolved_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    from simmer_sdk.client import extract_text
    return judge_name, extract_text(response)


def _extract_revised_scores(
    deliberation_text: str,
    original_scores: dict[str, int],
    criteria: dict[str, str],
) -> dict[str, int]:
    """Extract revised scores from deliberation text, falling back to originals."""
    revised = dict(original_scores)

    # Look for patterns like: criterion: ... revised score 7 ... or ... 7/10
    score_pattern = re.compile(
        r"^\s*\[?([A-Za-z][A-Za-z0-9_ \-]*)\]?\s*:\s*.*?(\d+)\s*/\s*10",
        re.MULTILINE,
    )
    # Also look for "revised score" mentions
    revised_pattern = re.compile(
        r"([A-Za-z][A-Za-z0-9_ \-]*)\s*[:\-]\s*.*?(?:revised|updated|changed)\s*.*?(\d+)\s*/?\s*10?",
        re.MULTILINE | re.IGNORECASE,
    )

    from simmer_sdk.judge import _normalize_key

    criteria_norm = {_normalize_key(k): k for k in criteria}

    for pattern in [score_pattern, revised_pattern]:
        for match in pattern.finditer(deliberation_text):
            raw_name = match.group(1).strip()
            score_val = int(match.group(2))
            if score_val < 1 or score_val > 10:
                continue

            norm = _normalize_key(raw_name)
            matched_key = criteria_norm.get(norm)

            if matched_key is None:
                for norm_crit, orig_key in criteria_norm.items():
                    if norm.startswith(norm_crit) or norm_crit.startswith(norm):
                        matched_key = orig_key
                        break

            if matched_key is not None:
                revised[matched_key] = score_val

    return revised


# ---------------------------------------------------------------------------
# Phase 3: Synthesis
# ---------------------------------------------------------------------------


def _parse_synthesis(text: str, criteria: dict[str, str]) -> tuple[str, str]:
    """Parse synthesis output, returning (asi, deliberation_summary)."""
    # Extract ASI
    asi = ""
    asi_patterns = [
        r"ASI\s*\(highest[- ]leverage direction\)\s*[:\n](.*?)(?=\n[A-Z]{3,}|\Z)",
        r"ASI\s*[:\n](.*?)(?=\n[A-Z]{3,}|\Z)",
    ]
    for pat in asi_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            asi = m.group(1).strip()
            break

    # Extract deliberation summary (WORKING / NOT WORKING / DIRECTION)
    summary = ""
    summary_match = re.search(
        r"(WORKING\s*\(preserve.*?\).*?)(?=\n\s*(?:```|$)|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if summary_match:
        summary = summary_match.group(1).strip()
    else:
        # Try to grab from WORKING to end of DIRECTION section
        working_match = re.search(r"(WORKING.*)", text, re.IGNORECASE | re.DOTALL)
        if working_match:
            summary = working_match.group(1).strip()

    return asi, summary


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def dispatch_board(
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
    stable_wins: Optional[StableWins] = None,
    candidate_path: Optional[str] = None,
    evaluator_path: Optional[str] = None,
    prior_candidate_paths: Optional[list[str]] = None,
    cached_judges: Optional[list[JudgeDefinition]] = None,
) -> JudgeOutput:
    """Orchestrate the full board: compose, score in parallel, deliberate, synthesize.

    Returns a single JudgeOutput that is indistinguishable from a single judge's
    output — the rest of the loop does not need to know whether it came from
    a single judge or a board.
    """
    # --- Compose panel (use cached if provided) ---
    if cached_judges is not None:
        judges = cached_judges
    else:
        candidate_summary = candidate[:2000] if len(candidate) > 2000 else candidate
        judges = await compose_judges(brief, problem_class, candidate_summary)

    # Build previous deliberation string from stable_wins
    previous_deliberation: Optional[str] = None
    if stable_wins and (stable_wins.working or stable_wins.not_working or stable_wins.direction):
        parts: list[str] = []
        if stable_wins.working:
            parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- {nw}" for nw in stable_wins.not_working))
        if stable_wins.direction:
            parts.append(f"DIRECTION:\n{stable_wins.direction}")
        previous_deliberation = "\n\n".join(parts)

    # -----------------------------------------------------------------------
    # Phase 1: Independent scoring (parallel)
    # -----------------------------------------------------------------------
    phase1_results: dict[int, tuple[str, str, JudgeOutput]] = {}
    phase1_errors: list[tuple[str, Exception]] = []

    async with anyio.create_task_group() as tg:
        async def _run_panelist(idx: int, judge_def: JudgeDefinition) -> None:
            try:
                result = await _dispatch_single_panelist(
                    brief=brief,
                    judge_def=judge_def,
                    problem_class=problem_class,
                    iteration=iteration,
                    candidate=candidate,
                    seed_candidate=seed_candidate,
                    seed_scores=seed_scores,
                    evaluator_output=evaluator_output,
                    previous_asi=previous_asi,
                    iteration_history=iteration_history,
                    exploration_status=exploration_status,
                    previous_deliberation=previous_deliberation,
                    candidate_path=candidate_path,
                    evaluator_path=evaluator_path,
                    prior_candidate_paths=prior_candidate_paths,
                    output_contract=brief.output_contract,
                )
                phase1_results[idx] = result
            except Exception as exc:
                phase1_errors.append((judge_def.name, exc))

        for idx, judge_def in enumerate(judges):
            tg.start_soon(_run_panelist, idx, judge_def)

    # Need at least 1 judge to proceed — if all failed, surface the details
    if not phase1_results:
        error_details = "; ".join(f"{name}: {exc}" for name, exc in phase1_errors)
        raise RuntimeError(f"All {len(judges)} board judges failed: {error_details}")

    # Deterministic ordering by original judge index
    ordered_phase1 = [phase1_results[i] for i in sorted(phase1_results)]

    # -----------------------------------------------------------------------
    # Phase 2: Deliberation (one round)
    # -----------------------------------------------------------------------
    # Prepare stripped outputs (no ASI) for other judges to see
    stripped_outputs: dict[str, str] = {}
    full_outputs: dict[str, str] = {}
    phase1_scores: dict[str, dict[str, int]] = {}
    for name, raw_text, parsed in ordered_phase1:
        stripped_outputs[name] = _strip_asi_from_output(raw_text)
        full_outputs[name] = raw_text
        phase1_scores[name] = parsed.scores

    deliberation_results: dict[str, str] = {}
    post_deliberation_scores: list[dict[str, int]] = []

    delib_results: dict[int, tuple[str, str]] = {}
    delib_errors: list[tuple[str, Exception]] = []

    async with anyio.create_task_group() as tg:
        async def _run_deliberation(idx: int, jname: str) -> None:
            try:
                others = [
                    (oname, stripped_outputs[oname])
                    for oname in stripped_outputs
                    if oname != jname
                ]
                name, delib_text = await _deliberate_single(
                    model=brief.clerk_model,
                    judge_name=jname,
                    own_output=full_outputs[jname],
                    other_outputs=others,
                    brief=brief,
                )
                delib_results[idx] = (name, delib_text)
            except Exception as exc:
                delib_errors.append((jname, exc))

        for idx, jname in enumerate(stripped_outputs):
            tg.start_soon(_run_deliberation, idx, jname)

    # Deterministic ordering by original judge index
    ordered_delib = [delib_results[i] for i in sorted(delib_results)]

    for name, delib_text in ordered_delib:
        deliberation_results[name] = delib_text
        revised = _extract_revised_scores(
            delib_text,
            phase1_scores[name],
            brief.criteria,
        )
        post_deliberation_scores.append(revised)

    # For judges whose deliberation failed, fall back to their Phase 1 scores
    succeeded_delib_names = {name for name, _ in ordered_delib}
    for name in phase1_scores:
        if name not in succeeded_delib_names:
            post_deliberation_scores.append(phase1_scores[name])

    # -----------------------------------------------------------------------
    # Phase 3: Synthesis
    # -----------------------------------------------------------------------
    consensus = compute_consensus_scores(post_deliberation_scores)

    synthesis_prompt = build_synthesis_prompt(
        criteria=brief.criteria,
        all_judge_outputs=[(name, full_outputs[name]) for name, _, _ in ordered_phase1],
        deliberation_results=[(name, deliberation_results.get(name, "")) for name, _, _ in ordered_phase1],
        artifact_type=brief.artifact_type,
        search_space=brief.search_space,
        stable_wins=stable_wins,
    )

    # Use judge model for synthesis — haiku loses structural nuance when
    # distilling board deliberation into a single ASI.
    from simmer_sdk.client import create_async_client, map_model_id
    client = create_async_client(brief)
    response = await client.messages.create(
        model=map_model_id(brief.judge_model, brief),
        max_tokens=4096,
        messages=[{"role": "user", "content": synthesis_prompt}],
    )
    from simmer_sdk.client import extract_text
    synthesis_text = extract_text(response)

    asi, deliberation_summary = _parse_synthesis(synthesis_text, brief.criteria)

    # Use the computed consensus scores — they're reliable Python math.
    # Don't re-parse from synthesis text which is fragile.
    final_scores = consensus

    # Build raw_text with the consensus scores stamped clearly at the top.
    # The reflect agent reads this to update trajectory.md — if the synthesis
    # text buries the scores or references seed scores, the reflect agent
    # extracts the wrong numbers. Stamping the consensus scores ensures they
    # are unambiguous.
    scores_block = "\n".join(f"  {k}: {v}/10" for k, v in final_scores.items())
    consensus_composite = round(sum(final_scores.values()) / len(final_scores), 1) if final_scores else 0.0
    stamped_raw_text = (
        f"BOARD CONSENSUS SCORES (post-deliberation):\n"
        f"{scores_block}\n"
        f"COMPOSITE: {consensus_composite}/10\n\n"
        f"ASI (highest-leverage direction):\n{asi}\n\n"
        f"--- FULL SYNTHESIS ---\n{synthesis_text}"
    )

    return JudgeOutput(
        scores=final_scores,
        asi=asi,
        deliberation_summary=deliberation_summary or None,
        raw_text=stamped_raw_text,
    )
