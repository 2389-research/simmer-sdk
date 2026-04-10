# ABOUTME: Trajectory tracking, regression detection, plateau analysis, stable wins.
# ABOUTME: Pure Python functions for iteration math plus LLM-based reflect dispatch.

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

from simmer_sdk.types import IterationRecord, SetupBrief, StableWins


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


async def condense_key_change_llm(report: str, brief: SetupBrief | None = None, model: str = "claude-haiku-4-5") -> str:
    """Condense a generator report to a meaningful key_change using an LLM.

    The key_change is used in the trajectory table, stable wins tracking,
    and exploration status — it needs to be semantically meaningful, not
    just truncated. Uses the clerk model (haiku) for one cheap call.

    Accepts an optional brief to route through the configured provider
    (e.g. Bedrock). Falls back to direct Anthropic when brief is None.

    Returns under 60 characters capturing WHAT changed, not WHY.
    Falls back to regex condensation if the LLM call fails.
    """
    if not report or report == "seed":
        return report
    try:
        if brief:
            from simmer_sdk.client import create_async_client, map_model_id
            client = create_async_client(brief)
            resolved_model = map_model_id(model, brief)
        else:
            import anthropic
            client = anthropic.AsyncAnthropic()
            resolved_model = model
        response = await client.messages.create(
            model=resolved_model,
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
        if brief and hasattr(brief, "_usage_tracker") and brief._usage_tracker:
            brief._usage_tracker.record(resolved_model, "clerk", response)
        from simmer_sdk.client import extract_text
        result = extract_text(response).strip().strip('"\'')
        if len(result) <= 60 and result:
            return result
    except Exception:
        logger.debug("condense_key_change_llm failed, falling back to regex", exc_info=True)
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

    best_iter = trajectory[best_idx].iteration if best_idx < len(trajectory) else best_idx
    table_lines = [header_line, sep_line] + rows
    table_lines.append("")
    table_lines.append(f"Best candidate: iteration {best_iter} (composite: {best_composite:.1f}/10)")

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
# Trajectory table parsing — read scores from the file the agent wrote
# ---------------------------------------------------------------------------

def _extract_scores_from_trajectory(
    trajectory_md: str,
    iteration: int,
    criteria: dict[str, str],
) -> dict[str, int]:
    """Extract scores for a specific iteration from trajectory.md.

    The trajectory table is a well-defined markdown format written by the
    reflect agent. This is much more reliable than parsing free-text LLM output.
    """
    scores: dict[str, int] = {}
    if not trajectory_md:
        return scores

    lines = trajectory_md.strip().split("\n")
    # Find the header row to get column positions
    header_line = None
    for line in lines:
        if "| Iteration" in line or "| Iter" in line:
            header_line = line
            break
    if not header_line:
        return scores

    headers = [h.strip() for h in header_line.split("|") if h.strip()]

    # Find the row for this iteration
    for line in lines:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not cells:
            continue
        try:
            if int(cells[0]) == iteration:
                for i, header in enumerate(headers):
                    if i < len(cells):
                        # Match header to criteria keys
                        for crit_key in criteria:
                            if header.lower().replace(" ", "_") == crit_key.lower().replace(" ", "_"):
                                try:
                                    scores[crit_key] = int(cells[i])
                                except (ValueError, IndexError):
                                    pass
                break
        except (ValueError, IndexError):
            continue

    return scores


def _find_best_from_trajectory(
    trajectory_md: str,
    criteria: dict[str, str],
    primary: str | None,
) -> tuple[int, float]:
    """Find the best iteration and its composite from trajectory.md.

    Returns (best_iteration, best_composite). Returns (-1, 0.0) if not found.
    """
    # Look for "Best candidate: iteration N (composite: N.N/10)"
    best_match = re.search(
        r"Best candidate:\s*iteration\s*(\d+)\s*\(composite:\s*([\d.]+)/10\)",
        trajectory_md,
        re.IGNORECASE,
    )
    if best_match:
        return int(best_match.group(1)), float(best_match.group(2))
    return -1, 0.0


def _get_primary_from_trajectory(
    trajectory_md: str,
    iteration: int,
    primary: str,
) -> int | None:
    """Get the primary criterion score for a specific iteration from trajectory.md."""
    lines = trajectory_md.strip().split("\n")
    header_line = None
    for line in lines:
        if "| Iteration" in line or "| Iter" in line:
            header_line = line
            break
    if not header_line:
        return None

    headers = [h.strip() for h in header_line.split("|") if h.strip()]
    primary_col = None
    for i, h in enumerate(headers):
        if h.lower().replace(" ", "_") == primary.lower().replace(" ", "_"):
            primary_col = i
            break
    if primary_col is None:
        return None

    for line in lines:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if not cells:
            continue
        try:
            if int(cells[0]) == iteration and primary_col < len(cells):
                return int(cells[primary_col])
        except (ValueError, IndexError):
            continue
    return None


def _fix_iteration_numbering(trajectory_md: str, expected_latest: int) -> str:
    """Verify and fix iteration numbers in trajectory.md.

    The reflect LLM sometimes mislabels iteration numbers (e.g., writes "3"
    instead of "2"). This function checks that iteration numbers are sequential
    (0, 1, 2, ...) and fixes the last row if it doesn't match expected_latest.
    """
    if not trajectory_md:
        return trajectory_md

    lines = trajectory_md.split("\n")
    fixed_lines = []
    data_rows_seen = 0

    for line in lines:
        # Match table data rows (start with | followed by a number)
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("| Iter") and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if cells:
                try:
                    row_iter = int(cells[0])
                    # The last data row should have iteration == expected_latest
                    # We'll fix it on the final pass below
                    data_rows_seen += 1
                except (ValueError, IndexError):
                    pass
        fixed_lines.append(line)

    # Now fix: find the last data row and ensure its iteration matches
    for i in range(len(fixed_lines) - 1, -1, -1):
        stripped = fixed_lines[i].strip()
        if stripped.startswith("|") and not stripped.startswith("| Iter") and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if cells:
                try:
                    row_iter = int(cells[0])
                    if row_iter != expected_latest:
                        # Fix the iteration number
                        cells[0] = str(expected_latest)
                        fixed_lines[i] = "| " + " | ".join(cells) + " |"
                    break
                except (ValueError, IndexError):
                    break

    return "\n".join(fixed_lines)


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
    if not text:
        text = ""
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
    brief: "SetupBrief | None" = None,
) -> ReflectOutput:
    """Dispatch the reflect step as an Agent SDK subagent.

    The reflect agent has Read + Write + Glob tools — it reads trajectory.md,
    updates it, and writes it back. Exactly like the skill in Claude Code.
    No parsing of scores by the orchestrator.
    """
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage

    # Read current trajectory.md to pass in the prompt
    trajectory_md_path = output_dir / "trajectory.md"
    trajectory_md = ""
    if trajectory_md_path.exists():
        trajectory_md = trajectory_md_path.read_text(encoding="utf-8")

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

    # Local mode: use Ollama agent loop instead of Claude CLI
    if brief and brief.api_provider == "ollama":
        from simmer_sdk.local_agent import run_local_agent
        reflect_text = await run_local_agent(
            prompt=prompt,
            model=brief.clerk_model,
            ollama_url=brief.ollama_url,
            tools=["Read", "Write", "Glob"],
            custom_tools=brief.custom_tools if brief else None,
            cwd=str(output_dir),
            max_turns=5,
        )
    else:
        # Dispatch as Agent SDK subagent with Read + Write + Glob
        from simmer_sdk.client import map_model_id, get_agent_env, get_cli_path
        agent_env = get_agent_env(brief) if brief else {}
        resolved_model = map_model_id(model, brief) if brief else model

        options = ClaudeAgentOptions(
            tools=["Read", "Write", "Glob"],
            model=resolved_model,
            permission_mode="bypassPermissions",
            cwd=str(output_dir),
            max_turns=5,
            env=agent_env,
            cli_path=get_cli_path(),
        )

        reflect_text = ""
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    reflect_text = (message.result or "") if hasattr(message, "result") else str(message)
                    if brief and hasattr(brief, "_usage_tracker") and brief._usage_tracker:
                        brief._usage_tracker.record_agent(brief.clerk_model, "reflect", message)

    # Ensure reflect_text is a string
    if not reflect_text:
        reflect_text = ""

    # Parse the structured text output for control flow data
    parsed = _parse_reflect_output(
        text=reflect_text,
        iteration=iteration,
        max_iterations=max_iterations,
        criteria=criteria,
        judge_asi=judge_asi,
    )

    # Read trajectory.md back — the agent wrote it via Write tool.
    # This is the source of truth for scores, not the text output.
    trajectory_table = ""
    if trajectory_md_path.exists():
        trajectory_table = trajectory_md_path.read_text(encoding="utf-8")

    # Verify iteration numbers are correct — the LLM sometimes mislabels them.
    # Fix any mislabeled iteration number for the current row.
    trajectory_table = _fix_iteration_numbering(trajectory_table, iteration)
    if trajectory_table:
        trajectory_md_path.write_text(trajectory_table, encoding="utf-8")

    # Extract scores from trajectory.md — it's a well-defined markdown table
    scores = _extract_scores_from_trajectory(trajectory_table, iteration, criteria)
    # If we got scores from the table, compute composite and best-so-far
    if scores:
        composite = round(sum(scores.values()) / len(scores), 1)
    else:
        # Fall back to parsed output
        scores = parsed["scores"]
        composite = parsed["best_composite"]

    # Determine best-so-far from the trajectory table
    best_iteration, best_composite = _find_best_from_trajectory(
        trajectory_table, criteria, primary
    )
    # Check regression: is this iteration's composite < best before it?
    regression = parsed["regression"]
    if scores and best_composite > 0:
        this_composite = round(sum(scores.values()) / len(scores), 1)
        if primary and primary in scores:
            # Check primary first
            best_primary = _get_primary_from_trajectory(trajectory_table, best_iteration, primary)
            regression = scores[primary] < best_primary if best_primary is not None else False
        else:
            regression = this_composite < best_composite and best_iteration != iteration

    key_change = parsed["key_change"]
    regression_rollback = best_iteration if regression and best_iteration != iteration else None

    record = IterationRecord(
        iteration=iteration,
        scores=scores,
        key_change=key_change,
        asi=parsed["asi"],
        regressed=regression,
        judge_mode=judge_mode,
    )

    return ReflectOutput(
        record=record,
        best_iteration=best_iteration if best_iteration >= 0 else parsed["best_iteration"],
        best_composite=best_composite if best_composite > 0 else parsed["best_composite"],
        regression=regression,
        regression_rollback_to=regression_rollback,
        iterations_remaining=max_iterations - iteration,
        asi=parsed["asi"],
        exploration_status=parsed["exploration_status"],
        stable_wins=parsed["stable_wins"],
        direction=parsed["direction"],
        trajectory_table=trajectory_table,
    )
