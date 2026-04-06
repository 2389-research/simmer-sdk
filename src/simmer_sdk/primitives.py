# ABOUTME: Built-in judge primitive library for board composition.
# ABOUTME: Provides domain-specific evaluation primitives matched to problem characteristics.

"""Judge Primitive Library — building blocks for constructing judges on a board panel."""

# CORE_PRIMITIVES: apply to all judges
CORE_PRIMITIVES: dict[str, str] = {
    "seed_calibration": "Score via seed calibration — score the original first, anchor all subsequent iterations to it.",
    "diagnose_before_scoring": "Diagnose before scoring — read the candidate, evaluator output, and relevant code/config. Understand *why* things are the way they are before writing scores.",
    "protect_high_scoring": "Protect high-scoring elements — identify what's working and constrain your ASI to preserve it.",
    "score_all_criteria": "Score ALL criteria from your lens — every judge scores every criterion from their perspective, not one criterion per judge.",
}

# EVALUATOR_PRIMITIVES: when evaluator is present
EVALUATOR_PRIMITIVES: dict[str, str] = {
    "cluster_failures": "Cluster evaluator failures by type — near-misses (spelling), systematic gaps (whole category), noise (hallucinations). The pattern determines the fix.",
    "verify_proper_nouns": "Verify proper nouns from lossy sources — transcripts, OCR, and auto-captions garble names.",
    "flag_stochasticity": "Flag evaluator stochasticity — if the same config produces different results, small score changes may be noise.",
}

# EXPLORATION_PRIMITIVES: when problem involves search
EXPLORATION_PRIMITIVES: dict[str, str] = {
    "review_tried": "Review what's been tried — check iteration history before suggesting more of the same.",
    "flag_ceilings": "Flag ceilings — if 2+ iterations tried the same type of change with no improvement, the bottleneck is structural.",
    "research_if_stuck": "Research if stuck — look up how similar problems are solved rather than guessing.",
}


def get_primitives_for_judge(
    has_evaluator: bool,
    has_search_space: bool,
    custom_primitives: list[str] | None = None,
) -> list[str]:
    """Return the list of primitive strings applicable for a judge.

    Always includes core primitives. Adds evaluator primitives when an
    evaluator is present, and exploration primitives when the problem
    involves a search space. Appends any custom primitives if provided.
    """
    primitives: list[str] = list(CORE_PRIMITIVES.values())

    if has_evaluator:
        primitives.extend(EVALUATOR_PRIMITIVES.values())

    if has_search_space:
        primitives.extend(EXPLORATION_PRIMITIVES.values())

    if custom_primitives:
        primitives.extend(custom_primitives)

    return primitives
