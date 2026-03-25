"""Orchestrator — Main Refinement Loop.

The public ``refine()`` entry point that ties all modules together:
setup -> seed judgment -> iterate (generate -> evaluate -> judge -> reflect) -> return result.
"""

from __future__ import annotations

import asyncio
import inspect
import subprocess
from pathlib import Path
from typing import Callable, Optional

from simmer_sdk.types import (
    IterationRecord,
    JudgeDefinition,
    JudgeOutput,
    SetupBrief,
    SimmerResult,
    StableWins,
)
from simmer_sdk.setup import classify_problem, resolve_brief
from simmer_sdk.generator import dispatch_generator
from simmer_sdk.judge import dispatch_judge
from simmer_sdk.judge_board import dispatch_board
from simmer_sdk.reflect import (
    record_iteration,
    find_best,
    check_plateau,
    track_stable_wins,
    track_exploration,
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _detect_artifact_type(artifact: str, mode: str) -> str:
    """Detect whether the artifact is a single file or a workspace.

    Returns ``"workspace"`` if the artifact points to a directory or mode
    is ``"from-workspace"``.  Otherwise ``"single-file"``.
    """
    if mode == "from-workspace":
        return "workspace"
    # Only check filesystem if the artifact looks like a path (short, no newlines)
    if len(artifact) < 260 and "\n" not in artifact:
        try:
            p = Path(artifact)
            if p.is_dir():
                return "workspace"
        except OSError:
            pass
    return "single-file"


def _detect_mode(artifact: str, artifact_type: str) -> str:
    """Auto-detect the operating mode from the artifact.

    Rules:
    - workspace -> ``"from-workspace"``
    - existing file -> ``"from-file"``
    - multi-line text or text with whitespace -> ``"from-paste"``
    - otherwise -> ``"seedless"`` (artifact is a description)
    """
    if artifact_type == "workspace":
        return "from-workspace"

    # Only check filesystem if the artifact looks like a path
    if len(artifact) < 260 and "\n" not in artifact:
        try:
            p = Path(artifact)
            if p.is_file():
                return "from-file"
        except OSError:
            pass

    # If it contains newlines or is long, treat as pasted content
    if "\n" in artifact or len(artifact) > 500:
        return "from-paste"

    return "seedless"


def _load_initial_candidate(brief: SetupBrief) -> str:
    """Load the initial candidate based on the mode."""
    if brief.mode == "from-file":
        return Path(brief.artifact).read_text(encoding="utf-8")
    if brief.mode == "from-paste":
        return brief.artifact
    if brief.mode == "seedless":
        return brief.artifact  # description; generator will create first candidate
    if brief.mode == "from-workspace":
        return f"[Workspace at {brief.artifact}]"
    return brief.artifact


def _load_candidate_at(brief: SetupBrief, out_path: Path, iteration: int) -> str:
    """Load a candidate written at a specific iteration."""
    if brief.artifact_type == "workspace":
        return f"[Workspace at {brief.artifact}]"
    candidate_file = out_path / f"iteration-{iteration}-candidate.md"
    if candidate_file.exists():
        return candidate_file.read_text(encoding="utf-8")
    return ""


def _run_evaluator(brief: SetupBrief) -> str:
    """Run the evaluator subprocess and return combined stdout+stderr."""
    if not brief.evaluator:
        return ""
    try:
        result = subprocess.run(
            brief.evaluator,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600,
            cwd=brief.artifact if brief.artifact_type == "workspace" else None,
        )
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(result.stderr)
        return "\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return "EVALUATOR TIMEOUT: command exceeded 3600s"
    except Exception as e:
        return f"EVALUATOR ERROR: {e}"


def _build_iteration_history(trajectory: list[IterationRecord]) -> str:
    """Build a text summary of the iteration trajectory for judge context."""
    if not trajectory:
        return ""
    lines: list[str] = []
    for rec in trajectory:
        score_str = ", ".join(f"{k}: {v}/10" for k, v in rec.scores.items())
        reg = " [REGRESSED]" if rec.regressed else ""
        lines.append(
            f"Iteration {rec.iteration}: {score_str} | "
            f"composite={rec.composite}{reg} | "
            f"change: {rec.key_change}"
        )
    return "\n".join(lines)


async def _call_callback(callback: Callable | None, *args) -> object:
    """Call a callback, handling both sync and async callables."""
    if callback is None:
        return None
    if inspect.iscoroutinefunction(callback):
        return await callback(*args)
    return callback(*args)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def refine(
    # Required
    artifact: str | Path,
    criteria: dict[str, str],
    # Optional — evaluation
    evaluator: str | None = None,
    primary: str | None = None,
    # Optional — loop control
    iterations: int = 3,
    mode: str = "auto",
    # Optional — judge configuration
    judge_mode: str = "auto",
    judge_panel: list[dict] | None = None,
    # Optional — workspace
    output_dir: str | Path = "docs/simmer",
    background: str | None = None,
    output_contract: str | None = None,
    validation_command: str | None = None,
    search_space: str | None = None,
    # Optional — models
    generator_model: str = "claude-sonnet-4-6",
    judge_model: str = "claude-sonnet-4-6",
    clerk_model: str = "claude-haiku-4-5",
    # Optional — callbacks
    on_iteration: Callable | None = None,
    on_plateau: Callable | None = None,
) -> SimmerResult:
    """Public entry point for the Simmer refinement loop.

    Orchestrates: setup -> seed judgment -> iterate (generate -> evaluate ->
    judge -> reflect) -> return result.
    """
    artifact_str = str(artifact)

    # ------------------------------------------------------------------
    # Step 0: Setup
    # ------------------------------------------------------------------
    artifact_type = _detect_artifact_type(artifact_str, mode)
    detected_mode = mode if mode != "auto" else _detect_mode(artifact_str, artifact_type)

    # Convert judge_panel dicts to JudgeDefinition objects if provided
    resolved_judge_panel: list[JudgeDefinition] | None = None
    if judge_panel is not None:
        resolved_judge_panel = [
            JudgeDefinition(**d) if isinstance(d, dict) else d
            for d in judge_panel
        ]

    brief = SetupBrief(
        artifact=artifact_str,
        artifact_type=artifact_type,
        criteria=criteria,
        iterations=iterations,
        mode=detected_mode,
        primary=primary,
        evaluator=evaluator,
        background=background,
        output_contract=output_contract,
        validation_command=validation_command,
        search_space=search_space,
        judge_mode=judge_mode,
        judge_panel=resolved_judge_panel,
        output_dir=str(output_dir),
        generator_model=generator_model,
        judge_model=judge_model,
        clerk_model=clerk_model,
    )

    brief = resolve_brief(brief)
    original_description = brief.artifact
    problem_class = classify_problem(brief)

    out_path = Path(brief.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Load initial candidate
    # ------------------------------------------------------------------
    current_candidate = _load_initial_candidate(brief)

    trajectory: list[IterationRecord] = []
    panel_summary: str | None = None
    exploration_status: str = ""
    seed_candidate: str | None = None
    seed_scores: dict[str, int] | None = None

    # ------------------------------------------------------------------
    # Step 2: Iteration 0 — Judge the seed
    # ------------------------------------------------------------------
    if detected_mode == "seedless":
        # Generator creates the first candidate
        gen_output = await dispatch_generator(
            brief=brief,
            iteration=0,
            current_candidate=current_candidate,
            asi="Create an initial high-quality candidate based on the description.",
            original_description=original_description,
        )
        current_candidate = gen_output.candidate

    # Write seed candidate
    if brief.artifact_type == "single-file":
        (out_path / "iteration-0-candidate.md").write_text(
            current_candidate, encoding="utf-8"
        )

    seed_candidate = current_candidate

    # Run evaluator on seed if present
    evaluator_output = _run_evaluator(brief) if brief.evaluator else ""

    # Judge the seed
    candidate_path = str(out_path / "iteration-0-candidate.md") if brief.artifact_type == "single-file" else None

    if brief.judge_mode == "board":
        judge_result = await dispatch_board(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output or None,
            candidate_path=candidate_path,
        )
    else:
        judge_result = await dispatch_judge(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output or None,
            candidate_path=candidate_path,
        )

    seed_scores = judge_result.scores

    record = record_iteration(
        iteration=0,
        scores=judge_result.scores,
        key_change="seed",
        asi=judge_result.asi,
        judge_mode=brief.judge_mode,
        trajectory=trajectory,
        primary=brief.primary,
    )
    trajectory.append(record)

    if judge_result.deliberation_summary:
        panel_summary = judge_result.deliberation_summary

    await _call_callback(on_iteration, 0, record)

    # ------------------------------------------------------------------
    # Step 3: Iterations 1-N
    # ------------------------------------------------------------------
    max_iterations = brief.iterations

    for i in range(1, max_iterations + 1):
        # a) Check for regression rollback
        best_idx = find_best(trajectory, brief.primary)
        regression_note = None
        if trajectory[-1].regressed:
            current_candidate = _load_candidate_at(brief, out_path, trajectory[best_idx].iteration)
            regression_note = (
                f"The previous iteration regressed. You are starting from the best version "
                f"(iteration {trajectory[best_idx].iteration}), not the latest."
            )

        # b) Generator
        exploration_status = track_exploration(trajectory, brief.search_space)

        gen_output = await dispatch_generator(
            brief=brief,
            iteration=i,
            current_candidate=current_candidate,
            asi=trajectory[-1].asi,
            panel_summary=panel_summary,
            exploration_status=exploration_status or None,
            original_description=original_description,
            regression_note=regression_note,
        )

        # For single-file mode, the generator should have written the candidate
        # to the output file via the Write tool. Read it back from there.
        # Fall back to the agent's text output if the file wasn't created.
        if brief.artifact_type == "single-file":
            candidate_file = out_path / f"iteration-{i}-candidate.md"
            if candidate_file.exists():
                current_candidate = candidate_file.read_text(encoding="utf-8")
            else:
                # Generator didn't write the file — use its output and write it ourselves
                current_candidate = gen_output.candidate
                candidate_file.write_text(current_candidate, encoding="utf-8")
        else:
            current_candidate = gen_output.candidate

        # c) Evaluator
        evaluator_output = _run_evaluator(brief) if brief.evaluator else ""

        # d) Judge
        # Context discipline: text/creative gets minimal context
        is_minimal_context = problem_class == "text/creative"

        iteration_history = _build_iteration_history(trajectory)
        candidate_path = str(out_path / f"iteration-{i}-candidate.md") if brief.artifact_type == "single-file" else None
        prior_candidate_paths = [
            str(out_path / f"iteration-{t.iteration}-candidate.md")
            for t in trajectory
        ] if brief.artifact_type == "single-file" else None

        if brief.judge_mode == "board":
            stable_wins = track_stable_wins(trajectory)
            judge_result = await dispatch_board(
                brief=brief,
                problem_class=problem_class,
                iteration=i,
                candidate=current_candidate,
                seed_candidate=seed_candidate,
                seed_scores=seed_scores,
                evaluator_output=evaluator_output or None,
                previous_asi=None if is_minimal_context else trajectory[-1].asi,
                iteration_history=None if is_minimal_context else iteration_history,
                exploration_status=None if is_minimal_context else (exploration_status or None),
                stable_wins=stable_wins,
                candidate_path=candidate_path,
                prior_candidate_paths=prior_candidate_paths,
            )
        else:
            judge_result = await dispatch_judge(
                brief=brief,
                problem_class=problem_class,
                iteration=i,
                candidate=current_candidate,
                seed_candidate=seed_candidate,
                seed_scores=seed_scores,
                evaluator_output=evaluator_output or None,
                previous_asi=None if is_minimal_context else trajectory[-1].asi,
                iteration_history=None if is_minimal_context else iteration_history,
                exploration_status=None if is_minimal_context else (exploration_status or None),
                candidate_path=candidate_path,
                prior_candidate_paths=prior_candidate_paths,
            )

        # e) Reflect
        key_change = gen_output.report[:200] if gen_output.report else f"iteration-{i}"

        record = record_iteration(
            iteration=i,
            scores=judge_result.scores,
            key_change=key_change,
            asi=judge_result.asi,
            judge_mode=brief.judge_mode,
            trajectory=trajectory,
            primary=brief.primary,
        )
        trajectory.append(record)

        if judge_result.deliberation_summary:
            panel_summary = judge_result.deliberation_summary

        stable_wins_obj = track_stable_wins(trajectory)
        exploration_status = track_exploration(trajectory, brief.search_space)

        await _call_callback(on_iteration, i, record)

        # f) Plateau detection
        if check_plateau(trajectory, brief.primary):
            if brief.judge_mode == "single" and on_plateau is not None:
                result = await _call_callback(on_plateau, trajectory)
                if result is True:
                    # Upgrade to board and add 2 iterations
                    brief.judge_mode = "board"
                    max_iterations = min(max_iterations + 2, i + 2 + (max_iterations - i))

    # ------------------------------------------------------------------
    # Step 4: Output
    # ------------------------------------------------------------------
    best_idx = find_best(trajectory, brief.primary)
    best_record = trajectory[best_idx]

    best_candidate = _load_candidate_at(brief, out_path, best_record.iteration)
    if not best_candidate:
        best_candidate = current_candidate

    # Write final result
    if brief.artifact_type == "single-file":
        (out_path / "result.md").write_text(best_candidate, encoding="utf-8")

    final_stable_wins = track_stable_wins(trajectory)

    return SimmerResult(
        best_candidate=best_candidate,
        best_iteration=best_record.iteration,
        best_scores=best_record.scores,
        composite=best_record.composite,
        trajectory=trajectory,
        stable_wins=final_stable_wins.working,
        not_working=final_stable_wins.not_working,
        output_dir=out_path,
    )
