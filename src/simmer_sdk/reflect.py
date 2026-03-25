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
    """Condense a generator report to under 60 characters for the trajectory table.

    Matches simmer-reflect/SKILL.md: 'condensed to a few words (under 60 characters).'
    """
    if not report or report == "seed":
        return report
    # Strip markdown bold markers
    text = re.sub(r'\*\*', '', report)
    # Strip common prefixes like "What changed:", "Report:", etc.
    text = re.sub(r'^(What changed.*?:|Report:?|Summary:?|Changes?:?)\s*', '', text, flags=re.IGNORECASE)
    # Strip leading newlines and whitespace
    text = text.strip()
    # Take first line
    text = text.split('\n')[0]
    # Take first sentence
    text = text.split('. ')[0]
    # Truncate to 57 chars + "..." if needed
    if len(text) > 57:
        text = text[:57] + "..."
    return text.strip() or "update"


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
