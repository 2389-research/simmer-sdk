# ABOUTME: Problem classification and judge mode auto-selection.
# ABOUTME: Resolves SetupBrief config, classifies as text/creative, code/testable, or pipeline/engineering.

from __future__ import annotations

import copy

from simmer_sdk.types import SetupBrief


def classify_problem(brief: SetupBrief) -> str:
    """Classify the problem type based on the SetupBrief.

    Rules:
    - workspace (artifact_type == "workspace" or mode == "from-workspace")
      AND evaluator present -> "pipeline/engineering"
    - evaluator present (non-workspace) -> "code/testable"
    - everything else -> "text/creative"
    """
    is_workspace = (
        brief.artifact_type == "workspace" or brief.mode == "from-workspace"
    )
    has_evaluator = bool(brief.evaluator)

    if is_workspace and has_evaluator:
        return "pipeline/engineering"
    if has_evaluator:
        return "code/testable"
    return "text/creative"


def auto_select_judge_mode(
    problem_class: str,
    num_criteria: int,
    user_override: str | None,
) -> str:
    """Auto-select judge mode based on problem class and number of criteria.

    Rules (in priority order):
    1. User override ("single" or "board") always wins.
    2. code/testable or pipeline/engineering -> "board"
    3. text/creative with >=3 criteria -> "board"
    4. text/creative with <=2 criteria -> "single"
    """
    if user_override is not None:
        return user_override

    if problem_class in ("code/testable", "pipeline/engineering"):
        return "board"

    # text/creative
    if num_criteria >= 3:
        return "board"
    return "single"


def resolve_brief(brief: SetupBrief) -> SetupBrief:
    """Resolve "auto" judge_mode to a concrete value.

    Returns a new deep-copied SetupBrief with judge_mode resolved.
    The original brief is not mutated.
    """
    resolved = copy.deepcopy(brief)

    if resolved.judge_mode == "auto":
        problem_class = classify_problem(resolved)
        num_criteria = len(resolved.criteria)
        resolved.judge_mode = auto_select_judge_mode(problem_class, num_criteria, None)

    return resolved
