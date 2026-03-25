"""Prompt-building functions for every role in the simmer loop.

Each function takes structured data and returns the full prompt string that
a subagent receives.  These prompts are faithful translations of the battle-tested
skill files from the Claude Code simmer plugin.
"""

from __future__ import annotations

from typing import Optional

from simmer_sdk.types import JudgeDefinition, StableWins


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_criteria(criteria: dict[str, str]) -> str:
    """Format criteria dict as a bulleted rubric block."""
    lines: list[str] = []
    for name, description in criteria.items():
        lines.append(f"  - {name}: {description}")
    return "\n".join(lines)


def _optional_block(label: str, value: Optional[str]) -> str:
    """Return a labelled block only when *value* is truthy."""
    if not value:
        return ""
    return f"\n{label}:\n{value}\n"


def _optional_section(label: str, value: Optional[str]) -> str:
    """Return a section only when *value* is truthy, no trailing newline."""
    if not value:
        return ""
    return f"\n{label}:\n{value}"


# ---------------------------------------------------------------------------
# 1. Generator prompt
# ---------------------------------------------------------------------------

_GENERATOR_SKILL_INSTRUCTIONS = """\
# Simmer Generator

Produce an improved version of the artifact. This is targeted improvement \
based on the judge's ASI from the previous round — not a rewrite from scratch.

## Context You Receive

- **Current candidate**: the full artifact text (single-file) or workspace path (workspace)
- **Criteria rubric**: what "better" means (criteria with descriptions)
- **ASI**: the highest-leverage direction to pursue (from previous judge round)
- **Iteration number**: which round this is
- **Artifact type**: single-file or workspace
- **Background** (optional): constraints, available resources, domain knowledge
- **Panel deliberation summary** (optional): what the judge panel concluded last round — \
WORKING elements to preserve, NOT WORKING approaches to avoid, DIRECTION for this iteration. \
Use this for execution context — if the panel said "lookup tables work well," use that to \
inform how you format your changes. Do NOT use it to decide *what* to change — that's the ASI's job.

You do NOT receive score history or previous candidates. This is intentional — work from the \
ASI, not from scores. Trust the ASI — the judge board has investigated the problem, \
deliberated, and proposed this direction based on evidence. Execute it skillfully.

## What To Do

### Seedless Iteration 1

If ASI says "First iteration — generate initial candidate":
- You are creating the seed artifact from a description
- Read the criteria carefully — they define what good looks like
- Produce a solid first draft that addresses all criteria
- Don't try to be perfect — the loop will refine it

### Single-File Mode

1. **Read the ASI carefully.** The judge identified the single highest-leverage fix. \
Address that specifically.
2. **Do not try to fix everything at once.** Focused improvement compounds better than \
scattered edits. Address the ASI. If you notice other small improvements that don't \
conflict, fine — but the ASI is your primary target.
3. **Preserve what works.** Don't regress on aspects that aren't mentioned in the ASI. \
If the ASI says "the CTA is too high-friction," don't rewrite the opening paragraph.
4. **Respect the artifact's natural scope.** Growth is fine when the criteria demand it. \
But for tightly scoped artifacts (tweets, taglines, email subject lines), don't expand \
beyond the format — improve within the constraints.
5. **Produce the full improved artifact.** Not a diff, not instructions — the complete \
text. Write it to the file path specified by the orchestrator.

### Workspace Mode

1. **Read the ASI carefully.** In workspace mode, the ASI describes a strategic *direction* \
— which may involve coordinated changes across multiple files.
2. **Execute the full direction.** If the ASI says "switch the reasoning step to a larger \
model, keep extraction on mini, adjust both prompts," do all of that in one iteration.
3. **Use the background context.** The background tells you what's available (models, APIs, \
infrastructure constraints). Stay within those bounds.
4. **Make changes directly in the workspace.** Edit files in place. The orchestrator tracks \
state via git commits.
5. **Don't make unrelated changes.** The ASI defines the direction — don't also refactor \
the config format or reorganize the directory structure unless the ASI calls for it.
6. **Evaluator scripts may be modified** if the ASI calls for a topology or pipeline change \
that requires it. Evaluator modifications should change HOW the pipeline runs (topology, \
calling patterns, preprocessing), not how results are SCORED. If a modification changes the \
scoring criteria, note this explicitly so the judge can account for it.
7. **Validate before committing to expensive runs.** When making infrastructure changes, \
verify the pipeline still produces valid output before the full evaluator run.

## Common Mistakes

- **Rewriting from scratch** — loses good parts of the current candidate. Targeted edits only.
- **Making only one tiny change in workspace mode** — execute the full ASI direction.
- **Making unrelated changes** — stay focused on the ASI direction.
- **Ignoring background constraints** — read the background context, stay within bounds.
- **Optimizing for imagined scores** — you don't have scores. Work from the ASI text.
- **Producing a diff or instructions instead of the full artifact (single-file)** — always \
produce the full artifact in single-file mode.
"""


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
    """Build the full prompt dispatched to the generator subagent.

    Two variants based on *artifact_type*:
    - ``"single-file"``: candidate text inline, asks generator to write to output file.
    - ``"workspace"``: includes workspace path; ASI may describe multi-file changes.
    """

    parts: list[str] = [
        "You are the generator in a simmer refinement loop.\n",
        _GENERATOR_SKILL_INSTRUCTIONS,
        f"ITERATION: {iteration}",
        f"ARTIFACT_TYPE: {artifact_type}",
        f"\nCRITERIA:\n{_format_criteria(criteria)}",
    ]

    # --- Background (both modes) ---
    if background:
        parts.append(f"\nBACKGROUND:\n{background}")

    # --- Panel deliberation summary ---
    if panel_summary:
        parts.append(
            f"\nPANEL DELIBERATION SUMMARY:\n{panel_summary}\n"
            "Use this for execution context — preserve WORKING elements, avoid "
            "NOT WORKING approaches.  The ASI decides *what* to change."
        )

    if artifact_type == "workspace":
        # --- Workspace variant ---
        wp = workspace_path or current_candidate
        parts.append(f"\nWORKSPACE: {wp}")

        if output_contract:
            parts.append(
                f"\nOUTPUT_CONTRACT:\n{output_contract}\n"
                "After making changes, verify your output matches this contract "
                "before reporting success. If your change breaks the contract, "
                "fix it or revert before the evaluator runs."
            )
        if validation_command:
            parts.append(
                f"\nVALIDATION_COMMAND:\n{validation_command}\n"
                "Run this after making infrastructure changes (model swaps, "
                "topology changes) to cheaply verify the pipeline still works. "
                "If validation fails, fix or try an alternative — don't waste "
                "a full evaluator run on a broken pipeline."
            )
        if search_space:
            parts.append(
                f"\nSEARCH_SPACE:\n{search_space}\n"
                "Stay within these bounds. If the ASI suggests exploring outside "
                "the search space, find the closest feasible alternative within bounds. "
                "Note in your report if you believe the search space should be expanded."
            )
        if exploration_status:
            parts.append(f"\nEXPLORATION STATUS:\n{exploration_status}")

        if original_description:
            parts.append(
                f"\nORIGINAL BRIEF:\n{original_description}\n\n"
                "The above is the original description that defines scope, format, and constraints.\n"
                "All iterations must respect these constraints."
            )

        if regression_note:
            parts.append(f"\nREGRESSION NOTE:\n{regression_note}")

        parts.append(
            f"\nJUDGE FEEDBACK (ASI from previous round):\n{asi}"
        )
        parts.append(
            "\nMake your changes directly in the workspace directory.\n"
            "You may edit multiple files in a single iteration when the ASI "
            "calls for coordinated changes.\n"
            "If making infrastructure changes, run VALIDATION_COMMAND "
            "(if available) before reporting success.\n\n"
            "Report: what specifically changed and why (2-3 sentences). "
            "List the files modified."
        )
    else:
        # --- Single-file variant ---
        if original_description:
            parts.append(
                f"\nORIGINAL BRIEF:\n{original_description}\n\n"
                "The above is the original description that defines scope, format, and constraints.\n"
                "All iterations must respect these constraints."
            )

        parts.append(f"\nCURRENT CANDIDATE:\n{current_candidate}")

        if output_contract:
            parts.append(f"\nOUTPUT_CONTRACT:\n{output_contract}")
        if validation_command:
            parts.append(f"\nVALIDATION_COMMAND:\n{validation_command}")
        if search_space:
            parts.append(f"\nSEARCH_SPACE:\n{search_space}")
        if exploration_status:
            parts.append(f"\nEXPLORATION STATUS:\n{exploration_status}")

        if regression_note:
            parts.append(f"\nREGRESSION NOTE:\n{regression_note}")

        parts.append(
            f"\nJUDGE FEEDBACK (ASI from previous round):\n{asi}"
        )
        parts.append(
            f"\nWrite your improved candidate to: "
            f"{output_dir}/iteration-{iteration}-candidate.md\n\n"
            "Report: what specifically changed and why (2-3 sentences)."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 2. Judge prompt
# ---------------------------------------------------------------------------

_JUDGE_SKILL_INSTRUCTIONS = """\
# Simmer Judge

Score the candidate against each criterion. Identify the highest-leverage \
direction to pursue next. Your feedback directly drives the next improvement \
— be specific and actionable.

## Evaluation Modes

| Mode | What you receive | How to score |
|------|-----------------|--------------|
| **Judge-only** | Candidate + criteria | Score against criteria descriptions using your judgment |
| **Runnable** | Candidate + criteria + evaluator output | Interpret evaluator output alongside criteria |
| **Hybrid** | Candidate + criteria + evaluator output | Evaluator provides data, you judge that data against criteria |

In all modes, you score against the criteria. The evaluator output is additional \
evidence — it doesn't replace your judgment, it informs it.

### Interpreting Evaluator Output

Evaluator output has no required format. Read it as you would read any diagnostic \
information. Extract what's relevant to the criteria. If the evaluator output is \
unclear or empty, score based on the candidate and criteria alone.

**Stochastic evaluators:** If evaluator output shows high variance between runs, \
note this in your reasoning. Small score changes (1 point or less) on stochastic \
evaluators may not represent real improvement. The ASI should target changes large \
enough to exceed the noise floor.

**Complete failures:** If the evaluator output shows a complete failure (0% on all \
metrics, errors only, empty output, invalid format), treat this as a FAILURE. Score \
all criteria at 1/10. The ASI should diagnose the failure cause rather than suggesting \
incremental improvements.

## Calibration

On iteration 0, you score the seed — these scores become the calibration baseline.

On iteration 1+, you receive the seed artifact and its scores as a reference point:
- **Floor reference**: the seed and what it scored (concrete example)
- **Ceiling definition**: the criterion descriptions of what 10/10 looks like

Score the current candidate on its own merits using these two anchors. You CAN score \
below the seed if the candidate regressed. The seed is a reference, not a floor.

Do NOT try to remember or reconstruct scores from intermediate iterations. Score \
against the criterion descriptions and the seed reference only.

## Scoring

Score each criterion on a **1-10 integer scale**. No half-points, no decimals.

For each criterion:
1. **Score** (integer, 1-10)
2. **Reasoning** (2-3 sentences explaining why this score)
3. **Specific improvement** (one concrete thing that would raise this score)

### Score Reference

| Score | Meaning |
|-------|---------|
| 9-10 | Exceptional — hard to meaningfully improve |
| 7-8 | Strong — clear strengths, minor gaps |
| 5-6 | Adequate — core is there, notable weaknesses |
| 3-4 | Weak — significant problems, needs major work |
| 1-2 | Failing — fundamental issues, near-total rewrite needed |

**Compute composite:** average of all criterion scores, one decimal place.

### Criteria Tradeoffs

When criteria trade off against each other, note this explicitly in your reasoning. \
Focus your ASI on the dimension with the most remaining headroom rather than trying \
to balance all criteria simultaneously.

### Raw Metrics as Discriminators

When evaluator output provides precise metrics, note the raw metric in your reasoning \
even though the score is an integer. Do not use fractional scores.

### Contract Violations

If the setup brief includes an OUTPUT_CONTRACT, check whether the evaluator output \
indicates the contract was violated. Contract violations are more severe than poor \
scores. Score all criteria at 1/10 and direct the ASI at fixing the contract violation.

## ASI (Actionable Side Information)

After scoring, identify the **highest-leverage direction to pursue next.** The ASI \
is the most important output — it directly drives what the generator does.

### Single-File Mode (Text/Creative)

The ASI is a single focused fix — one specific edit that would improve the candidate most.

**The ASI must be:**
- **Single**: one fix, not a list
- **Specific**: not "improve clarity" but "the second paragraph assumes the reader \
knows what X is — define it or move the definition earlier"
- **Concrete**: the generator should know exactly what to change
- **Actionable**: something that can be done in one editing pass

### Workspace Mode (Code/Pipeline)

The ASI is a single strategic *direction* — one coherent move that may involve \
coordinated changes across multiple files.

**Before writing the ASI, analyze and research:**
1. Analyze evaluator output patterns — cluster failures by type.
2. Review what's been tried — check iteration history and exploration status.
3. Research if stuck — look up best practices, not just keep tweaking.
4. Explore proactively — if untried options exist past the halfway point, suggest one.
5. Then propose a direction informed by evidence, not just intuition.

**The ASI must be:**
- **One direction**: a coherent strategy, not a list of unrelated fixes
- **Evidence-based**: cite specific patterns from evaluator output
- **Specific**: name the files, models, or components involved
- **Concrete**: the generator should understand the full scope of changes
- **Actionable**: something that can be executed in one iteration

## Common Mistakes

- Producing unrelated ASI items as a list — ASI is ONE direction.
- Vague ASI — be specific about what to change and why.
- Ignoring evaluator output — use it as evidence for scoring and ASI.
- Over-relying on evaluator output — it's evidence, not the final score.
- Anchoring to imagined intermediate scores — score against criteria + seed only.
- Treating seed scores as a floor — score honestly, regressions happen.
- Scoring non-integers — integer scores only, 1-10.
- Writing ASI from vibes instead of evidence — analyze evaluator output patterns first.
- Suggesting the same type of change repeatedly — if it hasn't worked for 2+ rounds, \
propose a structural change.
"""

_JUDGE_REQUIRED_FORMAT = """\
## Required Output Format

```
ITERATION [N] SCORES:
  [criterion 1]: [N]/10 — [reasoning] — [specific improvement]
  [criterion 2]: [N]/10 — [reasoning] — [specific improvement]
  [criterion 3]: [N]/10 — [reasoning] — [specific improvement]
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[concrete, specific, actionable instruction for the generator]
```

**CRITICAL:** Use this exact format. The orchestrator and reflect subskill parse it.\
"""

_JUDGE_INVESTIGATE_STEP = """\
─── STEP 1: INVESTIGATE (required, before scoring) ───

Read the files listed above. Understand the problem before judging it.

On iteration 0 (seed):
- Read the evaluator script — understand HOW it scores (exact match? fuzzy? \
case-sensitive? what format does it expect?)
- Read the ground truth if accessible — what's the theoretical maximum? \
Are there unreachable targets?
- Read the background constraints — what can the model actually do?

Every iteration:
- Read the candidate file — structure and formatting matter, not just the \
text summary in this prompt
- [Code/pipeline only] Read prior candidates — what structural changes were \
tried and what was their effect? (Text/creative judges do NOT read prior \
candidates — this prevents anchoring to previous versions)
- When you see a failure pattern you don't know how to fix, SEARCH for \
solutions before proposing your ASI

─── STEP 2: SCORE (with full understanding) ───

Score ALL criteria. Your scores should be grounded in what you found during \
investigation, not just observation of the evaluator output.

─── STEP 3: ASI (informed by research) ───

Your ASI must:
- Be actionable within the generator's bounds
- Cite what you found during investigation
- Reference prior iterations when relevant
- If you searched for solutions, cite what you found

If the bottleneck is outside the generator's bounds, say so.\
"""


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
    """Build the full prompt dispatched to the judge subagent.

    Two variants based on *problem_class*:
    - ``"text/creative"``: candidate + criteria + seed reference only.
      NO intermediate scores, previous ASI, or trajectory.
    - ``"code/testable"`` or ``"pipeline/engineering"``: everything
      text/creative gets PLUS evaluator output, previous ASI, iteration
      history, search space, exploration status.
    """

    is_code = problem_class in ("code/testable", "pipeline/engineering")

    parts: list[str] = [
        "You are the judge in a simmer refinement loop.\n",
        _JUDGE_SKILL_INSTRUCTIONS,
        _JUDGE_REQUIRED_FORMAT,
    ]

    # --- Context discipline note ---
    if is_code:
        parts.append(
            "\n## Context Discipline (code/pipeline)\n"
            "You receive additional context to enable strategic reasoning: "
            "previous ASI, iteration history, search space, and exploration status. "
            "This lets you reason about *why* the current approach isn't working. "
            "You still score against the criteria and seed — the history informs "
            "your ASI, not your scores."
        )
    else:
        parts.append(
            "\n## Context Discipline (text/creative)\n"
            "You do NOT receive intermediate iteration scores, previous ASI, or "
            "previous candidates. You receive only the seed as a fixed calibration "
            "reference. This prevents score anchoring on subjective judgments."
        )

    # --- Core parameters ---
    parts.append(f"\nITERATION: {iteration}")
    parts.append(f"ARTIFACT_TYPE: {artifact_type}")
    parts.append(f"\nCRITERIA:\n{_format_criteria(criteria)}")

    # --- Files to investigate ---
    file_lines: list[str] = []
    if candidate_path:
        file_lines.append(f"- Candidate: {candidate_path}")
    if evaluator_path:
        file_lines.append(f"- Evaluator script: {evaluator_path}")
    if prior_candidate_paths:
        if is_code:
            file_lines.append(
                "- Prior candidates: " + ", ".join(prior_candidate_paths)
            )
        # text/creative does NOT get prior candidates
    if file_lines:
        parts.append("\nFILES YOU SHOULD READ:\n" + "\n".join(file_lines))

    parts.append(f"\n{_JUDGE_INVESTIGATE_STEP}")

    # --- Candidate ---
    parts.append(f"\nCANDIDATE:\n{candidate}")

    # --- Seed calibration ---
    if seed_candidate is not None and iteration > 0:
        parts.append(f"\nSEED CALIBRATION:\n{seed_candidate}")
    if seed_scores is not None and iteration > 0:
        scores_lines = "\n".join(
            f"  {k}: {v}/10" for k, v in seed_scores.items()
        )
        parts.append(f"\nSEED SCORES:\n{scores_lines}")

    # --- Evaluator output ---
    if evaluator_output is not None:
        parts.append(f"\nEVALUATOR OUTPUT:\n{evaluator_output}")

    # --- Output contract ---
    if output_contract:
        parts.append(f"\nOUTPUT_CONTRACT:\n{output_contract}")

    # --- Code/pipeline extras (context discipline: only for code/pipeline) ---
    if is_code:
        if previous_asi:
            parts.append(f"\nPREVIOUS ASI:\n{previous_asi}")
        if iteration_history:
            parts.append(f"\nITERATION HISTORY:\n{iteration_history}")
        if search_space:
            parts.append(f"\nSEARCH_SPACE:\n{search_space}")
        if exploration_status:
            parts.append(f"\nEXPLORATION STATUS:\n{exploration_status}")

    # --- Closing instruction ---
    if evaluator_output is not None and is_code:
        parts.append(
            "\nInterpret the evaluator output alongside the criteria.\n"
            "Check evaluator output against the output contract if specified.\n"
            "Score this candidate using the seed as a calibration reference.\n"
            "Use the iteration history, previous ASI, and exploration status to "
            "inform your ASI — analyze what's been tried, what worked, what "
            "didn't, and propose an evidence-based direction. You may research "
            "approaches if the current path is stuck."
        )
    else:
        parts.append(
            "\nScore this candidate against the criteria using the seed as a "
            "calibration reference.\n"
            "Do NOT look at or consider any intermediate iteration scores."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 3. Board panelist prompt
# ---------------------------------------------------------------------------

_PANELIST_PREAMBLE = """\
You are one of three judges on a simmer judge board. Your role is to score \
from your specific lens — the other judges cover other angles.\
"""

_MUTATION_BOUNDS_TABLE = """\
### Mutation Bounds

| Artifact Type | Generator Can Change | Generator Cannot Change |
|---------------|---------------------|------------------------|
| **single-file** | The text content of the artifact (prompt, document, config file) | Model selection, code, infrastructure, pipeline topology, add new files |
| **workspace** | Any files in the workspace directory — code, config, prompts, scripts, add new files | Things outside the workspace, external infrastructure not in the search space |

Every ASI the panel produces must be actionable within these bounds. If the \
panel concludes "the model is the bottleneck" but the artifact is single-file \
(can't swap models), the ASI should recommend switching to workspace mode or \
early termination rather than suggesting a model swap the generator can't execute.

Judges must read the relevant artifacts before scoring. Read the candidate, \
the evaluator script, config files, and prior candidates. Understand how the \
system works and why the scores are what they are. Research approaches if you \
see failure patterns you don't know how to fix.\
"""


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
) -> str:
    """Build the full prompt for a single panelist on the judge board.

    Includes lens assignment, mutation bounds, investigation step, applicable
    primitives, previous deliberation summary, and all the judge scoring rules.
    """

    is_code = problem_class in ("code/testable", "pipeline/engineering")

    parts: list[str] = [_PANELIST_PREAMBLE]

    # --- Lens assignment ---
    parts.append(
        f"\nYOUR LENS: {judge_def.name}\n{judge_def.lens}"
    )

    # --- Artifact type and mutation bounds ---
    parts.append(f"\nARTIFACT_TYPE: {artifact_type}")
    if search_space:
        parts.append(f"SEARCH_SPACE: {search_space}")
    if artifact_type == "workspace":
        parts.append("WHAT THE GENERATOR CAN CHANGE: files in the workspace directory")
    else:
        parts.append("WHAT THE GENERATOR CAN CHANGE: text content only")

    parts.append(f"\n{_MUTATION_BOUNDS_TABLE}")

    # --- Background ---
    if background:
        parts.append(f"\nBACKGROUND:\n{background}")

    # --- Previous deliberation ---
    if previous_deliberation:
        parts.append(
            f"\nPREVIOUS PANEL DELIBERATION:\n{previous_deliberation}\n"
            "Respect the WORKING list — these elements have been stable across "
            "iterations and should not be removed or changed. The NOT WORKING "
            "list prevents retrying failed approaches. Build on prior conclusions "
            "rather than reasoning from scratch each iteration."
        )

    # --- Files to investigate ---
    file_lines: list[str] = []
    if candidate_path:
        file_lines.append(f"- Candidate: {candidate_path}")
    if evaluator_path:
        file_lines.append(f"- Evaluator script: {evaluator_path}")
    if prior_candidate_paths and is_code:
        file_lines.append(
            "- Prior candidates: " + ", ".join(prior_candidate_paths)
        )
    if file_lines:
        parts.append("\nFILES YOU SHOULD READ:\n" + "\n".join(file_lines))

    # --- Investigation step ---
    parts.append(f"\n{_JUDGE_INVESTIGATE_STEP}")

    # --- Applicable primitives ---
    if primitives:
        prims_block = "\n".join(f"- {p}" for p in primitives)
        parts.append(
            f"\nAPPLICABLE PRIMITIVES (capabilities for your lens):\n{prims_block}"
        )

    # --- Full judge scoring rules ---
    parts.append(f"\n{_JUDGE_SKILL_INSTRUCTIONS}")

    # --- Context discipline note ---
    if is_code:
        parts.append(
            "## Context Discipline (code/pipeline)\n"
            "You receive evaluator output, previous ASI, iteration history, "
            "search space, and exploration status. The history informs your ASI, "
            "not your scores."
        )
    else:
        parts.append(
            "## Context Discipline (text/creative)\n"
            "You do NOT receive intermediate scores, previous ASI, or previous "
            "candidates. Score against the criteria and the seed reference only."
        )

    # --- Core parameters ---
    parts.append(f"\nITERATION: {iteration}")
    parts.append(f"\nCRITERIA:\n{_format_criteria(criteria)}")
    parts.append(f"\nCANDIDATE:\n{candidate}")

    # --- Seed calibration ---
    if seed_candidate is not None and iteration > 0:
        parts.append(f"\nSEED CALIBRATION:\n{seed_candidate}")
    if seed_scores is not None and iteration > 0:
        scores_lines = "\n".join(
            f"  {k}: {v}/10" for k, v in seed_scores.items()
        )
        parts.append(f"\nSEED SCORES:\n{scores_lines}")

    # --- Evaluator output ---
    if evaluator_output is not None:
        parts.append(f"\nEVALUATOR OUTPUT:\n{evaluator_output}")

    # --- Code/pipeline extras ---
    if is_code:
        if previous_asi:
            parts.append(f"\nPREVIOUS ASI:\n{previous_asi}")
        if iteration_history:
            parts.append(f"\nITERATION HISTORY:\n{iteration_history}")
        if exploration_status:
            parts.append(f"\nEXPLORATION STATUS:\n{exploration_status}")

    # --- Required output format ---
    parts.append(f"\n{_JUDGE_REQUIRED_FORMAT}")

    # --- Closing ---
    parts.append(
        "\nScore ALL criteria from your lens — not just one. Your lens frames "
        "HOW you analyze, not WHAT you analyze. Every judge scores every criterion "
        "from their unique perspective."
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 4. Deliberation prompt
# ---------------------------------------------------------------------------

def build_deliberation_prompt(
    judge_name: str,
    own_output: str,
    other_outputs: list[tuple[str, str]],
) -> str:
    """Build the deliberation prompt for a single panelist.

    One round only.  Each judge sees others' scores + reasoning but NOT their
    ASI candidates.  Format: Agree / Challenge / Concede per criterion.

    Parameters
    ----------
    judge_name:
        Name of the judge receiving this prompt.
    own_output:
        This judge's full Phase-1 output (scores + reasoning + ASI).
    other_outputs:
        List of ``(name, scores_and_reasoning)`` tuples for the other judges.
        **Must not include ASI** — only scores and reasoning.
    """

    parts: list[str] = [
        "You are deliberating on a simmer judge board.\n",
        f"YOUR INDEPENDENT SCORES (from Phase 1):\n{own_output}\n",
    ]

    for other_name, other_scores_reasoning in other_outputs:
        parts.append(f"{other_name}'s SCORES:\n{other_scores_reasoning}\n")

    parts.append(
        "Review the other judges' scores and reasoning. For each criterion:\n\n"
        "1. **Agree** — if you agree, say so briefly\n"
        "2. **Challenge** — if you disagree, explain what the other judge missed "
        "or got wrong. Cite evidence from the candidate or evaluator output.\n"
        "3. **Concede** — if another judge's reasoning changes your mind, revise "
        "your score and explain why\n\n"
        "One round only. Be direct. Challenges are the point — they surface "
        "blind spots that a single judge would miss.\n\n"
        "DELIBERATION:\n"
        "  [criterion]: [agree/challenge/concede] — [reasoning] — "
        "[revised score if changed, or \"holds\"]"
    )

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
    """Build the synthesis prompt for the clerk (Phase 3 of board).

    The clerk distills — doesn't select.  ONE focused ASI, not a list.
    Must check generator feasibility and alignment with panel conclusions.
    """

    parts: list[str] = [
        "You are the clerk synthesizing the judge board's output.\n",
        "## Your Job\n",
        "Produce consensus scores and a single ASI from the panel's independent "
        "scoring and deliberation.  The output must be identical in format to a "
        "single judge's output — the orchestrator cannot tell the difference.\n",
    ]

    # --- Criteria ---
    parts.append(f"CRITERIA:\n{_format_criteria(criteria)}\n")
    parts.append(f"ARTIFACT_TYPE: {artifact_type}")

    if search_space:
        parts.append(f"SEARCH_SPACE: {search_space}")

    # --- All judge outputs (include ASI for synthesis) ---
    parts.append("\n## Judge Outputs (with ASI candidates)\n")
    for name, full_output in all_judge_outputs:
        parts.append(f"### {name}\n{full_output}\n")

    # --- Deliberation results ---
    parts.append("## Deliberation Results\n")
    for name, deliberation in deliberation_results:
        parts.append(f"### {name}\n{deliberation}\n")

    # --- Stable wins ---
    if stable_wins:
        sw_parts: list[str] = []
        if stable_wins.working:
            sw_parts.append(
                "WORKING (preserve — do not remove or change):\n"
                + "\n".join(f"- {w}" for w in stable_wins.working)
            )
        if stable_wins.not_working:
            sw_parts.append(
                "NOT WORKING (do not retry same approach):\n"
                + "\n".join(f"- {nw}" for nw in stable_wins.not_working)
            )
        if stable_wins.direction:
            sw_parts.append(f"DIRECTION:\n{stable_wins.direction}")
        if sw_parts:
            parts.append(
                "## Stable Wins from Reflect\n" + "\n\n".join(sw_parts) + "\n"
            )

    # --- Synthesis instructions ---
    parts.append(
        "## Synthesis Instructions\n\n"
        "**Step 1: Consensus scores.**\n"
        "For each criterion, take the post-deliberation scores (revised where "
        "judges conceded, original where they held):\n"
        "- **All within 1 point**: use the median. Note agreement.\n"
        "- **2+ point spread after deliberation**: use the median. Note the "
        "tension and why judges disagreed — this informs the ASI.\n\n"
        "Compute composite as the average, one decimal place.\n\n"
        "**Step 2: Synthesize ASI.**\n"
        "Read all three judges' independent ASI candidates + the deliberation "
        "highlights. Then **distill** — don't select.\n\n"
        "The board's value is in its analysis. The ASI's value is in its focus. "
        "Don't let the breadth of the analysis dilute the focus of the ASI.\n\n"
        "1. **Identify the single highest-leverage move.** Not the most thorough "
        "analysis — the one change that would move scores the most. If all three "
        "judges point at different things, pick the one that addresses the primary "
        "criterion's biggest bottleneck. If you find yourself writing \"also\" or "
        "listing multiple changes, you're diluting. Pick one.\n\n"
        "2. **Check alignment with panel conclusions.** If the deliberation "
        "concluded \"current approach has hit a ceiling,\" the ASI must propose a "
        "structural change — not more of the same approach. If no structural change "
        "is possible in the current mode, recommend early termination with a specific "
        "next step the user can take.\n\n"
        "3. **Check generator feasibility.** In single-file mode, the generator can "
        "only edit text. Don't propose code changes, model swaps, or architecture "
        "changes unless the artifact type is workspace. Filter for what the generator "
        "can actually do in the current mode.\n\n"
        "4. **Keep it focused.** The ASI is ONE direction with ONE primary change. "
        "A compound ASI will overwhelm the generator. The single judge's strength "
        "was focus — the board must match that.\n\n"
        "**Step 3: Deliberation summary (for next iteration's panel).**\n"
        "Write a structured summary with three sections:\n\n"
        "```\n"
        "WORKING (preserve — do not remove or change):\n"
        "- [element that's been stable across iterations]\n\n"
        "NOT WORKING (do not retry same approach):\n"
        "- [element that was tried and regressed]\n\n"
        "DIRECTION:\n"
        "[What the panel concluded about where to go next — one sentence.]\n"
        "```\n\n"
        "Incorporate the STABLE WINS from the reflect subskill if available.\n\n"
        "**Step 4: Output.**\n"
        "Produce the standard judge output format:\n\n"
        "```\n"
        "ITERATION [N] SCORES:\n"
        "  [criterion]: [N]/10 — [consensus reasoning, noting tensions if any] "
        "— [specific improvement]\n"
        "COMPOSITE: [N.N]/10\n\n"
        "ASI (highest-leverage direction):\n"
        "[single ASI — the strongest-evidence direction from the panel]\n"
        "```\n\n"
        "This is identical to what a single judge produces. The orchestrator, "
        "reflect, and generator cannot tell the difference."
    )

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
    """Build the prompt that asks the LLM to design 3 judges for the board.

    Used once at the start of a run to compose the judge panel tailored to
    the specific problem.
    """

    parts: list[str] = [
        "You are composing a judge board for a simmer refinement loop.\n",
        "## Your Job\n",
        "Design 3 judges with diverse lenses for this specific problem. Each judge "
        "needs a unique angle. Ask: \"What are the 3 most different ways to evaluate "
        "this artifact?\" The answer depends on the problem.\n",
        "The judges should be specific to the problem, not generic "
        "\"Metrics/Strategy/Integration.\"\n",
    ]

    # --- Problem context ---
    parts.append(f"PROBLEM CLASS: {problem_class}")
    parts.append(f"HAS EVALUATOR: {'yes' if has_evaluator else 'no'}")
    parts.append(f"\nARTIFACT SUMMARY:\n{artifact_summary}")
    parts.append(f"\nCRITERIA:\n{_format_criteria(criteria)}")

    if background:
        parts.append(f"\nBACKGROUND:\n{background}")
    if search_space:
        parts.append(f"\nSEARCH_SPACE:\n{search_space}")

    # --- Primitive library ---
    parts.append(
        "\n## Judge Primitive Library\n\n"
        "Building blocks for constructing judges. Apply relevant ones to each "
        "judge based on their role.\n\n"
        "**Core (apply to all judges):**\n"
        "- Score via seed calibration — score the original first, anchor all "
        "subsequent iterations to it\n"
        "- Diagnose before scoring — read the candidate, evaluator output, and "
        "relevant code/config. Understand *why* things are the way they are before "
        "writing scores.\n"
        "- Protect high-scoring elements — identify what's working and constrain "
        "your ASI to preserve it\n"
        "- Score ALL criteria from your lens — every judge scores every criterion "
        "from their perspective, not one criterion per judge\n"
    )

    if has_evaluator:
        parts.append(
            "**When evaluator is present:**\n"
            "- Cluster evaluator failures by type — near-misses (spelling), "
            "systematic gaps (whole category), noise (hallucinations). The pattern "
            "determines the fix.\n"
            "- Verify proper nouns from lossy sources — transcripts, OCR, and "
            "auto-captions garble names\n"
            "- Flag evaluator stochasticity — if the same config produces different "
            "results, small score changes may be noise\n"
        )

    if search_space:
        parts.append(
            "**When the problem involves exploration:**\n"
            "- Review what's been tried — check iteration history before suggesting "
            "more of the same\n"
            "- Flag ceilings — if 2+ iterations tried the same type of change with "
            "no improvement, the bottleneck is structural\n"
            "- Research if stuck — look up how similar problems are solved rather "
            "than guessing\n"
        )

    # --- Example compositions ---
    parts.append(
        "## Example Compositions (for reference — create problem-specific judges, "
        "not these)\n\n"
        "**Code/pipeline with evaluator:**\n"
        "| Judge | Why this lens | Key primitives |\n"
        "|-------|--------------|----------------|\n"
        "| Evaluator Analyst | Deep-dive the metrics — pass/fail patterns, "
        "near-misses vs systematic gaps | Cluster failures, flag stochasticity |\n"
        "| Constraint Realist | Execution environment capabilities and limits | "
        "Diagnose before scoring, flag ceilings, research if stuck |\n"
        "| Downstream User | Does the output work for its intended use? | "
        "Protect high-scoring elements, score via seed calibration |\n\n"
        "**Creative writing (no evaluator):**\n"
        "| Judge | Why this lens | Key primitives |\n"
        "|-------|--------------|----------------|\n"
        "| Craft | Structure, pacing, voice | Diagnose before scoring, "
        "protect high-scoring elements |\n"
        "| Reader | Emotional impact reading cold | Score via seed calibration |\n"
        "| Domain Expert | Genre/setting/rules accuracy | Research if stuck |\n"
    )

    # --- Required output format ---
    parts.append(
        "## Required Output Format\n\n"
        "Return exactly 3 judges in this format:\n\n"
        "```\n"
        "JUDGE_PANEL:\n"
        "  - name: [Judge Name]\n"
        "    lens: [1-2 sentence description of what to focus on and what "
        "perspective this judge brings]\n"
        "    primitives:\n"
        "      - [primitive 1]\n"
        "      - [primitive 2]\n"
        "  - name: [Judge Name]\n"
        "    lens: [description]\n"
        "    primitives:\n"
        "      - [primitive 1]\n"
        "      - [primitive 2]\n"
        "  - name: [Judge Name]\n"
        "    lens: [description]\n"
        "    primitives:\n"
        "      - [primitive 1]\n"
        "      - [primitive 2]\n"
        "```\n\n"
        "Each judge must score ALL criteria from their lens — the lens frames "
        "the perspective, not the criterion. 3 judges x N criteria = 3N scored "
        "data points with cross-criterion insight."
    )

    return "\n".join(parts)
