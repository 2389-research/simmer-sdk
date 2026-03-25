"""Prompt-building functions for every role in the simmer loop.

Each function loads the ACTUAL skill file from skill_reference/ and appends
dynamic context. The skill files are the source of truth — no paraphrasing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from simmer_sdk.types import JudgeDefinition, StableWins

# ---------------------------------------------------------------------------
# Skill file loading
# ---------------------------------------------------------------------------

_SKILL_DIR = Path(__file__).parent / "skill_reference"


def _load_skill(name: str) -> str:
    """Load a skill file from the skill_reference directory."""
    path = _SKILL_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_criteria(criteria: dict[str, str]) -> str:
    """Format criteria dict as a bulleted rubric block."""
    lines: list[str] = []
    for name, description in criteria.items():
        lines.append(f"  - {name}: {description}")
    return "\n".join(lines)


def _format_scores(scores: dict[str, int]) -> str:
    """Format scores dict for display."""
    return "\n".join(f"  - {k}: {v}/10" for k, v in scores.items())


def _optional_block(label: str, value: Optional[str]) -> str:
    """Return a labelled block only when *value* is truthy."""
    if not value:
        return ""
    return f"\n{label}:\n{value}\n"


# ---------------------------------------------------------------------------
# 1. Generator prompt
# ---------------------------------------------------------------------------

def build_generator_prompt(
    iteration: int,
    artifact_type: str,
    criteria: dict[str, str],
    current_candidate: str,
    asi: str,
    output_dir: str,
    background: Optional[str] = None,
    panel_summary: Optional[str] = None,
    output_contract: Optional[str] = None,
    validation_command: Optional[str] = None,
    search_space: Optional[str] = None,
    exploration_status: Optional[str] = None,
    workspace_path: Optional[str] = None,
    original_description: Optional[str] = None,
    regression_note: Optional[str] = None,
) -> str:
    """Build the generator subagent prompt.

    Loads the generator skill file verbatim, then appends the dynamic context
    matching the orchestrator skill's 'Step 1: Generator (subagent)' prompt template.
    """
    skill_text = _load_skill("generator")

    parts: list[str] = [
        "You are the generator in a simmer refinement loop.\n",
        "Invoke the skill: simmer:simmer-generator\n",
        skill_text,
        f"\nITERATION: {iteration}",
        f"ARTIFACT_TYPE: {artifact_type}",
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
    ]

    if background:
        parts.append(f"\nBACKGROUND:\n{background}")

    if panel_summary:
        parts.append(f"\nPANEL DELIBERATION SUMMARY:\n{panel_summary}")

    if original_description:
        parts.append(
            f"\nORIGINAL BRIEF:\n{original_description}\n\n"
            "The above is the original description that defines scope, format, "
            "and constraints. All iterations must respect these constraints."
        )

    if artifact_type == "workspace":
        wp = workspace_path or current_candidate
        parts.append(f"\nWORKSPACE: {wp}")
        parts.append(_optional_block("OUTPUT_CONTRACT", output_contract))
        parts.append(_optional_block("VALIDATION_COMMAND", validation_command))
        parts.append(_optional_block("SEARCH_SPACE", search_space))
        parts.append(_optional_block("EXPLORATION STATUS", exploration_status))
        if regression_note:
            parts.append(f"\nREGRESSION NOTE:\n{regression_note}")
        parts.append(f"\nJUDGE FEEDBACK (ASI from previous round):\n{asi}")
        parts.append(
            "\nMake your changes directly in the workspace directory.\n"
            "You may edit multiple files in a single iteration when the ASI "
            "calls for coordinated changes.\n"
            "Report: what specifically changed and why (2-3 sentences). "
            "List the files modified."
        )
    else:
        parts.append(f"\nCURRENT CANDIDATE:\n{current_candidate}")
        parts.append(_optional_block("OUTPUT_CONTRACT", output_contract))
        parts.append(_optional_block("VALIDATION_COMMAND", validation_command))
        parts.append(_optional_block("SEARCH_SPACE", search_space))
        parts.append(_optional_block("EXPLORATION STATUS", exploration_status))
        if regression_note:
            parts.append(f"\nREGRESSION NOTE:\n{regression_note}")
        parts.append(f"\nJUDGE FEEDBACK (ASI from previous round):\n{asi}")
        parts.append(
            f"\nWrite your improved candidate to: "
            f"{output_dir}/iteration-{iteration}-candidate.md\n\n"
            "Report: what specifically changed and why (2-3 sentences)."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 2. Judge prompt
# ---------------------------------------------------------------------------

def build_judge_prompt(
    iteration: int,
    artifact_type: str,
    problem_class: str,
    criteria: dict[str, str],
    candidate: str,
    seed_candidate: Optional[str] = None,
    seed_scores: Optional[dict[str, int]] = None,
    evaluator_output: Optional[str] = None,
    previous_asi: Optional[str] = None,
    iteration_history: Optional[str] = None,
    search_space: Optional[str] = None,
    exploration_status: Optional[str] = None,
    output_contract: Optional[str] = None,
    candidate_path: Optional[str] = None,
    evaluator_path: Optional[str] = None,
    prior_candidate_paths: Optional[list[str]] = None,
) -> str:
    """Build the single judge subagent prompt.

    Loads the judge skill file verbatim. Context discipline varies by problem_class:
    - text/creative: candidate + criteria + seed reference only
    - code/pipeline: above + evaluator output + previous ASI + iteration history
    """
    skill_text = _load_skill("judge")

    parts: list[str] = [
        "You are the judge in a simmer refinement loop.\n",
        "Invoke the skill: simmer:simmer-judge\n",
        skill_text,
        f"\nITERATION: {iteration}",
        f"ARTIFACT_TYPE: {artifact_type}",
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
        f"\nCANDIDATE:\n{candidate}",
    ]

    # File paths for investigation
    if candidate_path:
        parts.append(f"\nFILES YOU SHOULD READ:")
        parts.append(f"- Candidate: {candidate_path}")
        if evaluator_path:
            parts.append(f"- Evaluator script: {evaluator_path}")
        if prior_candidate_paths and problem_class != "text/creative":
            for p in prior_candidate_paths:
                parts.append(f"- Prior candidate: {p}")

    # Seed calibration (iteration 1+)
    if seed_candidate is not None and iteration > 0:
        parts.append(f"\nSEED CALIBRATION:\n{seed_candidate}")
    if seed_scores is not None and iteration > 0:
        parts.append(f"\nSEED SCORES:\n{_format_scores(seed_scores)}")

    # Context discipline: code/pipeline gets extra context
    if problem_class != "text/creative":
        parts.append(_optional_block("EVALUATOR OUTPUT", evaluator_output))
        parts.append(_optional_block("OUTPUT_CONTRACT", output_contract))
        parts.append(_optional_block("PREVIOUS ASI", previous_asi))
        parts.append(_optional_block("ITERATION HISTORY", iteration_history))
        parts.append(_optional_block("SEARCH_SPACE", search_space))
        parts.append(_optional_block("EXPLORATION STATUS", exploration_status))
        parts.append(
            "\nInterpret the evaluator output alongside the criteria.\n"
            "Score this candidate using the seed as a calibration reference.\n"
            "Use the iteration history, previous ASI, and exploration status to inform "
            "your ASI — analyze what's been tried, what worked, what didn't."
        )
    else:
        parts.append(
            "\nScore this candidate against the criteria using the seed as a "
            "calibration reference.\nDo NOT look at or consider any intermediate "
            "iteration scores."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 3. Board panelist prompt
# ---------------------------------------------------------------------------

def build_board_panelist_prompt(
    judge_def: JudgeDefinition,
    iteration: int,
    artifact_type: str,
    problem_class: str,
    criteria: dict[str, str],
    candidate: str,
    primitives: list[str],
    seed_candidate: Optional[str] = None,
    seed_scores: Optional[dict[str, int]] = None,
    evaluator_output: Optional[str] = None,
    previous_asi: Optional[str] = None,
    iteration_history: Optional[str] = None,
    search_space: Optional[str] = None,
    exploration_status: Optional[str] = None,
    background: Optional[str] = None,
    previous_deliberation: Optional[str] = None,
    candidate_path: Optional[str] = None,
    evaluator_path: Optional[str] = None,
    prior_candidate_paths: Optional[list[str]] = None,
    output_contract: Optional[str] = None,
) -> str:
    """Build a board panelist prompt.

    Loads the judge skill file verbatim (panelists ARE judges). Adds the lens,
    mutation bounds, investigation step, and primitives from the judge board skill.
    """
    judge_skill = _load_skill("judge")
    board_skill = _load_skill("judge_board")

    # Format primitives
    primitives_text = "\n".join(f"- {p}" for p in primitives)

    parts: list[str] = [
        "You are one of three judges on a simmer judge board. Your role is to "
        "score from your specific lens — the other judges cover other angles.\n",
        f"YOUR LENS: {judge_def.name}",
        f"{judge_def.lens}\n",
        f"ARTIFACT_TYPE: {artifact_type}",
    ]

    if search_space:
        parts.append(f"SEARCH_SPACE: {search_space}")

    # Mutation bounds from the board skill
    if artifact_type == "workspace":
        parts.append(
            "WHAT THE GENERATOR CAN CHANGE: files in the workspace directory "
            "(code, config, prompts, scripts, new files)"
        )
    else:
        parts.append(
            "WHAT THE GENERATOR CAN CHANGE: the text content of the artifact only "
            "(not model selection, code, infrastructure, pipeline topology)"
        )

    parts.append(_optional_block("BACKGROUND", background))
    parts.append(_optional_block("PREVIOUS PANEL DELIBERATION", previous_deliberation))

    # File paths for investigation
    files_block = []
    if candidate_path:
        files_block.append(f"- Candidate: {candidate_path}")
    if evaluator_path:
        files_block.append(f"- Evaluator script: {evaluator_path}")
    if prior_candidate_paths and problem_class != "text/creative":
        for p in prior_candidate_paths:
            files_block.append(f"- Prior candidate: {p}")
    if files_block:
        parts.append("\nFILES YOU SHOULD READ:\n" + "\n".join(files_block))

    # Investigation step from the board skill
    parts.append("""
── STEP 1: INVESTIGATE (required, before scoring) ──

Read the files listed above. Understand the problem before judging it.

On iteration 0 (seed):
- Read the evaluator script — understand HOW it scores (exact match?
  fuzzy? case-sensitive? what format does it expect?)
- Read the ground truth if accessible — what's the theoretical maximum?
- Read the background constraints — what can the model actually do?

Every iteration:
- Read the candidate file — structure and formatting matter, not just
  the text summary in this prompt
- When you see a failure pattern you don't know how to fix, SEARCH
  for solutions before proposing your ASI

── STEP 2: SCORE (with full understanding) ──

Score ALL criteria from your lens — not just one. Your lens frames
HOW you analyze, not WHAT you analyze.

── STEP 3: ASI (informed by research) ──

Your ASI candidate must be actionable within the generator's bounds.
""")

    # Applicable primitives
    parts.append(f"\nAPPLICABLE PRIMITIVES:\n{primitives_text}")

    # Now include the full judge skill for scoring rules
    parts.append("\n--- JUDGE SCORING RULES ---\n")
    parts.append(judge_skill)

    # Dynamic context
    parts.append(f"\nITERATION: {iteration}")
    parts.append(f"\nCRITERIA:\n{_format_criteria(criteria)}")
    parts.append(f"\nCANDIDATE:\n{candidate}")

    if seed_candidate is not None and iteration > 0:
        parts.append(f"\nSEED CALIBRATION:\n{seed_candidate}")
    if seed_scores is not None and iteration > 0:
        parts.append(f"\nSEED SCORES:\n{_format_scores(seed_scores)}")

    if problem_class != "text/creative":
        parts.append(_optional_block("EVALUATOR OUTPUT", evaluator_output))
        parts.append(_optional_block("OUTPUT_CONTRACT", output_contract))
        parts.append(_optional_block("PREVIOUS ASI", previous_asi))
        parts.append(_optional_block("ITERATION HISTORY", iteration_history))
        parts.append(_optional_block("EXPLORATION STATUS", exploration_status))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 4. Deliberation prompt
# ---------------------------------------------------------------------------

def build_deliberation_prompt(
    judge_name: str,
    own_output: str,
    other_outputs: list[tuple[str, str]],
) -> str:
    """Build a deliberation prompt for one judge.

    Uses the deliberation format from the judge board skill verbatim.
    One round only. Each judge sees others' scores + reasoning but NOT their ASI.
    """
    parts: list[str] = [
        "You are deliberating on a simmer judge board.\n",
        f"YOUR INDEPENDENT SCORES (from Phase 1):\n{own_output}\n",
    ]

    for other_name, other_scores in other_outputs:
        parts.append(f"{other_name}'s SCORES:\n{other_scores}\n")

    parts.append("""Review the other judges' scores and reasoning. For each criterion:

1. **Agree** — if you agree, say so briefly
2. **Challenge** — if you disagree, explain what the other judge missed
   or got wrong. Cite evidence from the candidate or evaluator output.
3. **Concede** — if another judge's reasoning changes your mind, revise
   your score and explain why

One round only. Be direct.

DELIBERATION:
  [criterion]: [agree/challenge/concede] — [reasoning] — [revised score if changed, or "holds"]
""")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 5. Synthesis prompt
# ---------------------------------------------------------------------------

def build_synthesis_prompt(
    criteria: dict[str, str],
    all_judge_outputs: list[tuple[str, str]],
    deliberation_results: list[tuple[str, str]],
    artifact_type: str,
    search_space: Optional[str] = None,
    stable_wins: Optional[StableWins] = None,
) -> str:
    """Build the synthesis (clerk) prompt.

    Uses the synthesis instructions from the judge board skill verbatim.
    The clerk distills — doesn't select. ONE focused ASI.
    """
    board_skill = _load_skill("judge_board")

    parts: list[str] = [
        "You are the clerk synthesizing a simmer judge board's output.\n",
        "Read the Phase 3: Synthesis section of this skill carefully:\n",
        board_skill,
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
        f"\nARTIFACT_TYPE: {artifact_type}",
    ]

    if search_space:
        parts.append(f"\nSEARCH_SPACE: {search_space}")

    if stable_wins and (stable_wins.working or stable_wins.not_working):
        sw_parts = []
        if stable_wins.working:
            sw_parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            sw_parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- {n}" for n in stable_wins.not_working))
        if stable_wins.direction:
            sw_parts.append(f"DIRECTION:\n{stable_wins.direction}")
        parts.append(f"\nSTABLE WINS FROM REFLECT:\n" + "\n\n".join(sw_parts))

    parts.append("\n--- JUDGE OUTPUTS ---\n")
    for name, output in all_judge_outputs:
        parts.append(f"\n{name}:\n{output}\n")

    parts.append("\n--- DELIBERATION RESULTS ---\n")
    for name, delib in deliberation_results:
        parts.append(f"\n{name}:\n{delib}\n")

    parts.append("""
Now synthesize:

1. Compute consensus scores (median of post-deliberation scores per criterion).
2. Distill ONE ASI — the single highest-leverage move. Do NOT list multiple changes.
3. Write a deliberation summary with WORKING / NOT WORKING / DIRECTION sections.

Output format:

ITERATION SCORES:
  [criterion]: [N]/10 — [consensus reasoning]
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[single focused ASI]

DELIBERATION SUMMARY:
WORKING (preserve — do not remove or change):
- [stable elements]

NOT WORKING (do not retry same approach):
- [failed approaches]

DIRECTION:
[one sentence — where to go next]
""")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 6. Board composition prompt
# ---------------------------------------------------------------------------

def build_board_composition_prompt(
    artifact_summary: str,
    criteria: dict[str, str],
    problem_class: str,
    has_evaluator: bool,
    background: Optional[str] = None,
    search_space: Optional[str] = None,
) -> str:
    """Build the prompt to compose a judge panel.

    Uses the judge composition section from the judge board skill verbatim.
    """
    board_skill = _load_skill("judge_board")

    parts: list[str] = [
        "You are composing a judge panel for a simmer refinement loop.\n",
        "Read the Judge Composition section of this skill carefully:\n",
        board_skill,
        f"\nPROBLEM CLASS: {problem_class}",
        f"HAS EVALUATOR: {has_evaluator}",
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
        f"\nARTIFACT SUMMARY:\n{artifact_summary[:2000]}",
    ]

    if background:
        parts.append(f"\nBACKGROUND:\n{background}")
    if search_space:
        parts.append(f"\nSEARCH_SPACE:\n{search_space}")

    parts.append("""
Design 3 judges with diverse lenses for this specific problem. Each judge needs:
- A unique angle on the problem
- Relevant primitives from the library

Output format:

JUDGE_PANEL:
  - name: [Judge Name]
    lens: [What this judge focuses on and why]
  - name: [Judge Name]
    lens: [What this judge focuses on and why]
  - name: [Judge Name]
    lens: [What this judge focuses on and why]
""")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 7. Reflect prompt
# ---------------------------------------------------------------------------

def build_reflect_prompt(
    judge_output_text: str,
    generator_report: str,
    iteration: int,
    max_iterations: int,
    criteria: dict[str, str],
    primary: Optional[str],
    artifact_type: str,
    search_space: Optional[str],
    current_trajectory_md: str,
) -> str:
    """Build the reflect LLM prompt.

    Loads the reflect skill file verbatim. The LLM updates trajectory.md,
    detects regression, tracks stable wins — exactly as the skill does.
    """
    skill_text = _load_skill("reflect")

    parts: list[str] = [
        "You are the reflect subskill in a simmer refinement loop.\n",
        "Invoke the skill: simmer:simmer-reflect\n",
        skill_text,
        f"\nITERATION: {iteration}",
        f"MAX ITERATIONS: {max_iterations}",
        f"ARTIFACT_TYPE: {artifact_type}",
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
    ]

    if primary:
        parts.append(f"PRIMARY CRITERION: {primary}")

    parts.append(f"\nLATEST JUDGE OUTPUT:\n{judge_output_text}")
    parts.append(f"\nGENERATOR REPORT:\n{generator_report}")

    if current_trajectory_md:
        parts.append(f"\nCURRENT TRAJECTORY.MD:\n{current_trajectory_md}")
    else:
        parts.append("\nCURRENT TRAJECTORY.MD:\n(empty — this is the first iteration)")

    if search_space:
        parts.append(f"\nSEARCH_SPACE: {search_space}")

    parts.append("""
Now perform your reflect duties:
1. Record the scores in the trajectory table (add a new row)
2. Compute composite as average of all criterion scores, one decimal
3. Track best-so-far (primary criterion first if set, composite tiebreaker)
4. Detect regression (if this iteration scored below best-so-far)
5. Condense the generator report to a key_change under 60 characters
6. Track stable wins (what's working, what's not)
7. Pass the ASI through unchanged

Output the FULL UPDATED trajectory table, then the structured output:

UPDATED TRAJECTORY TABLE:
[full markdown table with all rows including this iteration]

ITERATION [N] RECORDED
BEST SO FAR: iteration [N] (composite: [N.N]/10)
REGRESSION: [true/false] — [if true: use iteration N as input to next generator]
ITERATIONS REMAINING: [N]
ASI FOR NEXT ROUND: [the judge's ASI, unchanged]
EXPLORATION STATUS: [what's been tried vs untried — omit for text/creative or no search space]
STABLE WINS: [what's working — do not remove]
NOT WORKING: [what's been tried and failed — do not retry same approach]
DIRECTION: [current strategic direction — one sentence]
KEY CHANGE: [condensed to under 60 characters]
SCORES: [criterion1=N, criterion2=N, ...]
""")

    return "\n".join(parts)
