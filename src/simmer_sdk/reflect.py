from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from simmer_sdk.types import IterationRecord, StableWins


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _composite(scores: dict[str, int]) -> float:
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores.values())


def _score_key(record: IterationRecord, primary: str | None):
    """Return a sort key for ranking iterations (higher is better).

    Returns a tuple so ties can be broken:
      - with primary:   (primary_score, composite)
      - without:        (composite,)
    """
    if primary and primary in record.scores:
        return (record.scores[primary], _composite(record.scores))
    return (_composite(record.scores),)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def find_best(trajectory: list[IterationRecord], primary: str | None) -> int:
    """Return the index of the best iteration in *trajectory*.

    Ties are broken in favour of the earlier iteration.
    """
    if not trajectory:
        return 0

    best_idx = 0
    best_key = _score_key(trajectory[0], primary)

    for idx, record in enumerate(trajectory[1:], start=1):
        key = _score_key(record, primary)
        if key > best_key:
            best_key = key
            best_idx = idx

    return best_idx


def check_regression(
    new_scores: dict[str, int],
    trajectory: list[IterationRecord],
    primary: str | None,
) -> bool:
    """Return True if *new_scores* are strictly worse than the best so far."""
    if not trajectory:
        return False

    best_idx = find_best(trajectory, primary)
    best = trajectory[best_idx]

    if primary and primary in best.scores and primary in new_scores:
        best_primary = best.scores[primary]
        new_primary = new_scores[primary]
        if new_primary != best_primary:
            return new_primary < best_primary
        # primary tied – fall through to composite comparison

    best_composite = _composite(best.scores)
    new_composite = _composite(new_scores)
    return new_composite < best_composite


def record_iteration(
    iteration: int,
    scores: dict[str, int],
    key_change: str,
    asi: str,
    judge_mode: str,
    trajectory: list[IterationRecord],
    primary: str | None,
) -> IterationRecord:
    """Create an :class:`IterationRecord`, setting *regressed* via
    :func:`check_regression`."""
    regressed = check_regression(scores, trajectory, primary)
    return IterationRecord(
        iteration=iteration,
        scores=scores,
        key_change=key_change,
        asi=asi,
        regressed=regressed,
        judge_mode=judge_mode,
    )


def check_plateau(
    trajectory: list[IterationRecord],
    primary: str | None,
) -> bool:
    """Return True if the trajectory has plateaued.

    Requires at least 4 records (seed + 3 iterations).  Plateau is defined as:
    the best score among the last 3 records is <= the best score among all
    earlier records.
    """
    if len(trajectory) < 4:
        return False

    before = trajectory[:-3]
    recent = trajectory[-3:]

    best_before_idx = find_best(before, primary)
    best_before_key = _score_key(before[best_before_idx], primary)

    best_recent_idx = find_best(recent, primary)
    best_recent_key = _score_key(recent[best_recent_idx], primary)

    return best_recent_key <= best_before_key


def track_stable_wins(trajectory: list[IterationRecord]) -> StableWins:
    """Analyse trajectory and classify key changes as working or not working.

    *Working*: non-seed, non-regressed changes that were not immediately
    followed by a regression.
    *Not working*: changes whose immediately following iteration regressed OR
    the change itself was a regression.
    """
    result = StableWins()

    if not trajectory:
        return result

    # Seed is iteration 0 (or simply the first record); skip it.
    non_seed = [r for r in trajectory if r.iteration != 0]

    for idx, record in enumerate(non_seed):
        if record.regressed:
            # The change introduced at this iteration didn't work.
            result.not_working.append(record.key_change)
        else:
            # Check if the *next* non-seed iteration regressed.
            if idx + 1 < len(non_seed) and non_seed[idx + 1].regressed:
                result.not_working.append(record.key_change)
            else:
                result.working.append(record.key_change)

    return result


def track_exploration(
    trajectory: list[IterationRecord],
    search_space: str | None,
) -> str:
    """Return a summary of what has been tried relative to *search_space*.

    Returns an empty string when *search_space* is ``None``.
    """
    if not search_space:
        return ""

    tried = [r.key_change for r in trajectory if r.iteration != 0]

    if not tried:
        return f"Search space: {search_space}\nNothing tried yet."

    tried_lines = "\n".join(f"  - {t}" for t in tried)
    return (
        f"Search space: {search_space}\n"
        f"Tried ({len(tried)}):\n{tried_lines}"
    )


def condense_key_change(report: str) -> str:
    """Sync fallback: condense a generator report to under 60 characters.

    Used when no LLM is available (e.g., unit tests). For production use,
    prefer ``condense_key_change_llm`` which uses the clerk model for
    semantic condensation.
    """
    if not report or report == "seed":
        return report
    # Strip markdown bold markers
    text = re.sub(r'\*\*', '', report)
    # Strip common prefixes like "What changed:", "Report:", etc.
    text = re.sub(r'^(What changed.*?:|Report:?|Summary:?|Changes?:?)\s*', '', text, flags=re.IGNORECASE)
    text = text.strip()
    text = text.split('\n')[0]
    text = text.split('. ')[0]
    if len(text) > 57:
        text = text[:57] + "..."
    return text.strip() or "update"


async def condense_key_change_llm(report: str, model: str = "claude-haiku-4-5") -> str:
    """Condense a generator report to a meaningful key_change using an LLM.

    The key_change is used in the trajectory table, stable wins tracking,
    and exploration status — it needs to be semantically meaningful, not
    just truncated. Uses the clerk model (haiku) for one cheap call.

    Returns under 60 characters capturing WHAT changed, not WHY.
    Falls back to regex condensation if the LLM call fails.
    """
    if not report or report == "seed":
        return report
    try:
        import anthropic
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    "Condense this generator report into a short key_change label "
                    "for a trajectory table. Under 50 characters. Capture WHAT changed, "
                    "not why. No markdown, no quotes. Examples: 'added lookup table', "
                    "'switched to qwen 27b', 'low-friction CTA', 'dual-clock mechanic'.\n\n"
                    f"Report:\n{report[:500]}"
                ),
            }],
        )
        result = response.content[0].text.strip().strip('"\'')
        if len(result) <= 60 and result:
            return result
    except Exception:
        pass
    return condense_key_change(report)


def format_trajectory_table(
    trajectory: list[IterationRecord],
    criteria_names: list[str],
    best_idx: int,
    primary: str | None,
) -> str:
    """Produce a markdown table of the iteration trajectory."""
    # Header
    headers = ["Iteration"] + criteria_names + ["Composite", "Key Change"]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join("-----------" for _ in headers) + "|"

    rows: list[str] = []
    for rec in trajectory:
        composite = sum(rec.scores.values()) / len(rec.scores) if rec.scores else 0.0
        change = rec.key_change
        if rec.regressed:
            change = f"{change} [REGRESSION]"
        cells = [str(rec.iteration)]
        for c in criteria_names:
            cells.append(str(rec.scores.get(c, "-")))
        cells.append(f"{composite:.1f}")
        cells.append(change)
        rows.append("| " + " | ".join(cells) + " |")

    best_composite = 0.0
    if trajectory and best_idx < len(trajectory):
        best_scores = trajectory[best_idx].scores
        best_composite = sum(best_scores.values()) / len(best_scores) if best_scores else 0.0

    table_lines = [header_line, sep_line] + rows
    table_lines.append("")
    table_lines.append(f"Best candidate: iteration {best_idx} (composite: {best_composite:.1f}/10)")

    return "\n".join(table_lines)


def write_trajectory_md(
    trajectory: list[IterationRecord],
    criteria_names: list[str],
    best_idx: int,
    primary: str | None,
    output_dir: Path,
) -> None:
    """Write trajectory.md to the output directory."""
    table = format_trajectory_table(trajectory, criteria_names, best_idx, primary)
    content = f"# Simmer Trajectory\n\n{table}"
    (output_dir / "trajectory.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# ReflectOutput
# ---------------------------------------------------------------------------

@dataclass
class ReflectOutput:
    """Output from the reflect step."""

    record: IterationRecord
    best_iteration: int
    best_composite: float
    regression: bool
    regression_rollback_to: int | None
    iterations_remaining: int
    asi: str
    exploration_status: str
    stable_wins: StableWins = field(default_factory=StableWins)
    direction: str = ""
    trajectory_table: str = ""


# ---------------------------------------------------------------------------
# LLM-based reflect dispatch
# ---------------------------------------------------------------------------

def _build_reflect_prompt(
    judge_output_text: str,
    generator_report: str,
    trajectory_md: str,
    iteration: int,
    max_iterations: int,
    criteria: dict[str, str],
    primary: str | None,
    artifact_type: str,
    search_space: str | None,
) -> str:
    """Build the reflect prompt using the actual skill file."""
    from simmer_sdk.prompts import build_reflect_prompt
    return build_reflect_prompt(
        judge_output_text=judge_output_text,
        generator_report=generator_report,
        iteration=iteration,
        max_iterations=max_iterations,
        criteria=criteria,
        primary=primary,
        artifact_type=artifact_type,
        search_space=search_space,
        current_trajectory_md=trajectory_md,
    )


def _parse_reflect_output(
    text: str,
    iteration: int,
    max_iterations: int,
    criteria: dict[str, str],
    judge_asi: str,
) -> dict:
    """Parse the structured reflect LLM output into a dict of values."""
    result: dict = {}

    # Best iteration
    best_match = re.search(r"BEST SO FAR:\s*iteration\s+(\d+)\s*\(composite:\s*([\d.]+)", text, re.IGNORECASE)
    if best_match:
        result["best_iteration"] = int(best_match.group(1))
        result["best_composite"] = float(best_match.group(2))
    else:
        result["best_iteration"] = iteration
        result["best_composite"] = 0.0

    # Regression
    regression_match = re.search(r"REGRESSION:\s*(true|false)", text, re.IGNORECASE)
    result["regression"] = bool(regression_match and regression_match.group(1).lower() == "true")

    # Rollback
    rollback_match = re.search(r"rollback to iteration\s+(\d+)", text, re.IGNORECASE)
    result["regression_rollback_to"] = int(rollback_match.group(1)) if rollback_match and result["regression"] else None

    # Iterations remaining
    result["iterations_remaining"] = max_iterations - iteration

    # ASI — use the judge's original ASI as passthrough (most reliable)
    asi_match = re.search(r"ASI FOR NEXT ROUND:\s*\n(.*?)(?=\nEXPLORATION STATUS:|\nSTABLE WINS:|\Z)", text, re.DOTALL | re.IGNORECASE)
    if asi_match:
        extracted_asi = asi_match.group(1).strip()
        # Use extracted if non-empty, otherwise fall back to judge's ASI
        result["asi"] = extracted_asi if extracted_asi else judge_asi
    else:
        result["asi"] = judge_asi

    # Exploration status
    exploration_match = re.search(r"EXPLORATION STATUS:\s*\n(.*?)(?=\nSTABLE WINS:|\nDIRECTION:|\Z)", text, re.DOTALL | re.IGNORECASE)
    result["exploration_status"] = exploration_match.group(1).strip() if exploration_match else ""

    # Stable wins
    working_match = re.search(r"WORKING:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    not_working_match = re.search(r"NOT WORKING:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)

    working_text = working_match.group(1).strip() if working_match else ""
    not_working_text = not_working_match.group(1).strip() if not_working_match else ""

    working_list = [w.strip() for w in working_text.split(",") if w.strip() and w.strip().lower() != "none yet" and w.strip().lower() != "none"]
    not_working_list = [w.strip() for w in not_working_text.split(",") if w.strip() and w.strip().lower() != "none yet" and w.strip().lower() != "none"]

    result["stable_wins"] = StableWins(working=working_list, not_working=not_working_list)

    # Direction
    direction_match = re.search(r"DIRECTION:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["direction"] = direction_match.group(1).strip() if direction_match else ""
    if result["direction"]:
        result["stable_wins"].direction = result["direction"]

    # Key change
    key_change_match = re.search(r"KEY CHANGE:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    result["key_change"] = key_change_match.group(1).strip() if key_change_match else f"iteration-{iteration}"

    # Scores
    scores: dict[str, int] = {}
    # Look in the SCORES section
    scores_section_match = re.search(r"SCORES:\s*\n(.*?)(?=\nCOMPOSITE:|\nTRAJECTORY TABLE:|\Z)", text, re.DOTALL | re.IGNORECASE)
    if scores_section_match:
        scores_text = scores_section_match.group(1)
        from simmer_sdk.judge import _normalize_key
        criteria_norm = {_normalize_key(k): k for k in criteria}

        score_pattern = re.compile(r"^\s*[-*]*\s*\**([A-Za-z][A-Za-z0-9_ \-]*?)\**:\s*(\d+)", re.MULTILINE)
        for match in score_pattern.finditer(scores_text):
            raw_name = match.group(1).strip()
            score_val = int(match.group(2))
            norm = _normalize_key(raw_name)

            matched_key = criteria_norm.get(norm)
            if matched_key is None:
                for norm_crit, orig_key in criteria_norm.items():
                    if norm.startswith(norm_crit) or norm_crit.startswith(norm):
                        matched_key = orig_key
                        break
            if matched_key is None:
                for norm_crit, orig_key in criteria_norm.items():
                    if norm in norm_crit or norm_crit in norm:
                        matched_key = orig_key
                        break
            if matched_key and matched_key not in scores:
                scores[matched_key] = score_val

    result["scores"] = scores

    # Trajectory table — extract everything after "TRAJECTORY TABLE:"
    table_match = re.search(r"TRAJECTORY TABLE:\s*\n(.*)", text, re.DOTALL | re.IGNORECASE)
    result["trajectory_table"] = table_match.group(1).strip() if table_match else ""

    return result


async def dispatch_reflect(
    judge_output_text: str,
    generator_report: str,
    iteration: int,
    max_iterations: int,
    criteria: dict[str, str],
    primary: str | None,
    artifact_type: str,
    search_space: str | None,
    output_dir: Path,
    model: str = "claude-haiku-4-5",
    judge_asi: str = "",
    judge_mode: str = "single",
) -> ReflectOutput:
    """Dispatch the reflect step as an LLM call.

    Mirrors the reflect subskill: the LLM reads the judge output + trajectory,
    updates the table, computes composites, detects regression, tracks stable
    wins, and writes the updated trajectory.md. No regex parsing of scores.
    """
    import anthropic

    # Read current trajectory.md if it exists
    trajectory_md_path = output_dir / "trajectory.md"
    trajectory_md = ""
    if trajectory_md_path.exists():
        trajectory_md = trajectory_md_path.read_text(encoding="utf-8")

    # Build the reflect prompt
    prompt = _build_reflect_prompt(
        judge_output_text=judge_output_text,
        generator_report=generator_report,
        trajectory_md=trajectory_md,
        iteration=iteration,
        max_iterations=max_iterations,
        criteria=criteria,
        primary=primary,
        artifact_type=artifact_type,
        search_space=search_space,
    )

    # Dispatch the LLM call
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    reflect_text = response.content[0].text

    # Parse the structured output
    parsed = _parse_reflect_output(
        text=reflect_text,
        iteration=iteration,
        max_iterations=max_iterations,
        criteria=criteria,
        judge_asi=judge_asi,
    )

    # Build the IterationRecord
    scores = parsed["scores"]
    key_change = parsed["key_change"]
    regression = parsed["regression"]

    record = IterationRecord(
        iteration=iteration,
        scores=scores,
        key_change=key_change,
        asi=parsed["asi"],
        regressed=regression,
        judge_mode=judge_mode,
    )

    # Write updated trajectory.md from LLM output
    trajectory_table = parsed["trajectory_table"]
    if trajectory_table:
        updated_content = f"# Simmer Trajectory\n\n{trajectory_table}"
        trajectory_md_path.write_text(updated_content, encoding="utf-8")

    return ReflectOutput(
        record=record,
        best_iteration=parsed["best_iteration"],
        best_composite=parsed["best_composite"],
        regression=regression,
        regression_rollback_to=parsed["regression_rollback_to"],
        iterations_remaining=parsed["iterations_remaining"],
        asi=parsed["asi"],
        exploration_status=parsed["exploration_status"],
        stable_wins=parsed["stable_wins"],
        direction=parsed["direction"],
        trajectory_table=trajectory_table,
    )
