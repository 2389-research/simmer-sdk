# ABOUTME: Main orchestrator for the simmer refinement loop.
# ABOUTME: Coordinates setup, generator, evaluator, judge, and reflect across iterations.

"""Orchestrator — Main Refinement Loop.

The public ``refine()`` entry point that ties all modules together:
setup -> seed judgment -> iterate (generate -> evaluate -> judge -> reflect) -> return result.
"""

from __future__ import annotations

import inspect
import re
import shlex
import subprocess
from pathlib import Path
from typing import Callable, Optional

from simmer_sdk.types import (
    IterationRecord,
    JudgeDefinition,
    JudgeOutput,
    OnIterationCallback,
    OnPlateauCallback,
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
    check_regression,
    track_stable_wins,
    track_exploration,
    write_trajectory_md,
    format_trajectory_table,
    dispatch_reflect,
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


# ---------------------------------------------------------------------------
# Git operations for workspace mode
# ---------------------------------------------------------------------------


def _git_run(workspace: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in the workspace directory."""
    return subprocess.run(
        ["git"] + list(args),
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _git_commit_iteration(workspace: str, iteration: int) -> str | None:
    """Stage all changes and commit. Returns the commit SHA or None on failure."""
    _git_run(workspace, "add", "-A")
    result = _git_run(
        workspace, "commit", "-m", f"simmer: iteration {iteration}",
        "--allow-empty",
    )
    if result.returncode != 0:
        return None
    # Get the commit SHA
    sha_result = _git_run(workspace, "rev-parse", "HEAD")
    return sha_result.stdout.strip() if sha_result.returncode == 0 else None


def _git_rollback_workspace(
    workspace: str,
    target_sha: str,
    output_dir: str,
) -> None:
    """Selectively restore workspace files from a previous commit.

    Matches the skill: ``git checkout <best-commit> -- .``
    but excludes trajectory.md and other tracking files in output_dir.
    """
    # Get list of files at the target commit
    result = _git_run(workspace, "diff", "--name-only", target_sha, "HEAD")
    if result.returncode != 0:
        return

    changed_files = [f for f in result.stdout.strip().split("\n") if f.strip()]

    # Exclude tracking files (trajectory.md, etc.) in the output dir
    output_rel = str(Path(output_dir).relative_to(workspace)) if output_dir.startswith(workspace) else None

    for filepath in changed_files:
        # Skip tracking files
        if output_rel and filepath.startswith(output_rel):
            continue
        _git_run(workspace, "checkout", target_sha, "--", filepath)

    # Stage the rollback
    _git_run(workspace, "add", "-A")
    _git_run(workspace, "commit", "-m", f"simmer: rollback to {target_sha[:8]}", "--allow-empty")


async def _run_evaluator(
    brief: SetupBrief,
    candidate_path: str | None = None,
    iteration: int = 0,
    output_dir: str | None = None,
) -> str:
    """Run the evaluator subprocess without blocking the event loop.

    The evaluator command supports template variables matching the skill's behavior:
    - ``{candidate_path}`` — absolute path to the current candidate file
    - ``{output_dir}`` — the simmer output directory
    - ``{iteration}`` — current iteration number

    For workspace mode, the evaluator runs in the workspace directory (``cd {ARTIFACT}``).
    For single-file mode, it runs in the output directory so relative paths resolve.
    """
    if not brief.evaluator:
        return ""

    # Template the evaluator command — quote path vars to prevent shell injection.
    # Note: shlex.quote wraps in single-quotes, so evaluator commands must NOT
    # add their own quotes around {candidate_path} or {output_dir} placeholders.
    cmd = brief.evaluator
    if candidate_path:
        cmd = cmd.replace("{candidate_path}", shlex.quote(candidate_path))
    if output_dir:
        cmd = cmd.replace("{output_dir}", shlex.quote(output_dir))
    cmd = cmd.replace("{iteration}", str(iteration))

    # Set cwd: workspace dir for workspace mode, output dir for single-file
    if brief.artifact_type == "workspace":
        cwd = brief.artifact
    else:
        cwd = output_dir or brief.output_dir

    try:
        import anyio
        with anyio.fail_after(3600):
            result = await anyio.run_process(
                ["sh", "-c", cmd],
                cwd=cwd,
                check=False,
            )
        output_parts = []
        stdout = result.stdout.decode() if result.stdout else ""
        stderr = result.stderr.decode() if result.stderr else ""
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(stderr)
        if result.returncode != 0:
            output_parts.append(f"EXIT CODE: {result.returncode}")
        return "\n".join(output_parts)
    except TimeoutError:
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
    judge_count: int = 3,
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
    # Optional — API provider
    api_provider: str = "anthropic",
    aws_access_key: str | None = None,
    aws_secret_key: str | None = None,
    aws_region: str | None = None,
    ollama_url: str = "http://localhost:11434",
    judge_preamble: str | None = None,
    custom_tools: dict | None = None,
    split_generator: bool = False,
    executor_model: str | None = None,
    # Optional — callbacks
    on_iteration: OnIterationCallback | None = None,
    on_plateau: OnPlateauCallback | None = None,
) -> SimmerResult:
    """Public entry point for the Simmer refinement loop.

    Orchestrates: setup -> seed judgment -> iterate (generate -> evaluate ->
    judge -> reflect) -> return result.
    """
    artifact_str = str(artifact)

    # Input validation
    if not criteria:
        raise ValueError("criteria must be a non-empty dict")
    if iterations < 0:
        raise ValueError("iterations must be >= 0")
    valid_modes = {"auto", "seedless", "from-file", "from-paste", "from-workspace"}
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}, got {mode!r}")
    valid_judge_modes = {"auto", "single", "board"}
    if judge_mode not in valid_judge_modes:
        raise ValueError(f"judge_mode must be one of {valid_judge_modes}, got {judge_mode!r}")
    valid_providers = {"anthropic", "bedrock", "ollama"}
    if api_provider not in valid_providers:
        raise ValueError(f"api_provider must be one of {valid_providers}, got {api_provider!r}")
    if judge_count < 2:
        raise ValueError("judge_count must be >= 2")

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
        judge_count=judge_count,
        output_dir=str(output_dir),
        generator_model=generator_model,
        judge_model=judge_model,
        clerk_model=clerk_model,
        api_provider=api_provider,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        aws_region=aws_region,
        ollama_url=ollama_url,
        judge_preamble=judge_preamble,
        custom_tools=custom_tools,
        split_generator=split_generator,
        executor_model=executor_model,
    )

    brief = resolve_brief(brief)
    original_description = brief.artifact
    problem_class = classify_problem(brief)

    # Usage tracking — attach to brief so all call sites can record
    from simmer_sdk.usage import UsageTracker
    usage_tracker = UsageTracker()
    brief._usage_tracker = usage_tracker  # type: ignore[attr-defined]

    out_path = Path(brief.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Gap Fix 5: Compute evaluator_path so judges can read the evaluator script
    evaluator_path: str | None = None
    if brief.evaluator:
        try:
            parts_eval = shlex.split(brief.evaluator)
            for part in parts_eval:
                if part.endswith(('.py', '.sh', '.bash', '.rb', '.js')):
                    evaluator_path = part
                    break
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Step 1: Load initial candidate
    # ------------------------------------------------------------------
    current_candidate = _load_initial_candidate(brief)

    trajectory: list[IterationRecord] = []
    panel_summary: str | None = None
    exploration_status: str = ""
    seed_candidate: str | None = None
    seed_scores: dict[str, int] | None = None
    current_direction: str = ""

    # Workspace mode: git commit tracking for rollback support
    # Maps iteration number -> commit SHA
    iteration_commits: dict[int, str] = {}
    is_workspace = brief.artifact_type == "workspace"

    if is_workspace:
        # Snapshot seed state before any changes
        sha = _git_commit_iteration(brief.artifact, 0)
        if sha:
            iteration_commits[0] = sha

    # ------------------------------------------------------------------
    # Step 2: Iteration 0 — Judge the seed
    # ------------------------------------------------------------------
    if detected_mode == "seedless":
        # Generator creates the first candidate
        gen_output = await dispatch_generator(
            brief=brief,
            iteration=0,
            current_candidate=current_candidate,
            asi="First iteration — generate initial candidate from the description and criteria.",
            original_description=original_description,
        )
        # Read candidate from file if generator wrote it via Write tool
        candidate_file = out_path / "iteration-0-candidate.md"
        if candidate_file.exists():
            current_candidate = candidate_file.read_text(encoding="utf-8")
        else:
            # Fallback: use agent output, write it ourselves
            current_candidate = gen_output.candidate
            candidate_file.write_text(current_candidate, encoding="utf-8")
    else:
        # Non-seedless: write the existing candidate as seed
        if brief.artifact_type == "single-file":
            (out_path / "iteration-0-candidate.md").write_text(
                current_candidate, encoding="utf-8"
            )

    seed_candidate = current_candidate

    # Judge the seed
    candidate_path = str(out_path / "iteration-0-candidate.md") if brief.artifact_type == "single-file" else None

    # Run evaluator on seed if present
    evaluator_output = await _run_evaluator(
        brief, candidate_path=candidate_path, iteration=0, output_dir=str(out_path)
    ) if brief.evaluator else ""

    # Gap Fix 6: Cache board composition before the loop
    cached_board_judges: list[JudgeDefinition] | None = None
    if brief.judge_mode == "board":
        from simmer_sdk.judge_board import compose_judges
        cached_board_judges = await compose_judges(
            brief=brief,
            problem_class=problem_class,
            candidate_summary=current_candidate[:500],
        )

    if brief.judge_mode == "board":
        judge_result = await dispatch_board(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output or None,
            candidate_path=candidate_path,
            evaluator_path=evaluator_path,
            cached_judges=cached_board_judges,
        )
    else:
        judge_result = await dispatch_judge(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output or None,
            candidate_path=candidate_path,
            evaluator_path=evaluator_path,
        )

    # Write raw judge output for downstream consumers
    if judge_result.raw_text:
        (out_path / "iteration-0-judgment.md").write_text(
            judge_result.raw_text, encoding="utf-8"
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
    write_trajectory_md(trajectory, list(brief.criteria.keys()), find_best(trajectory, brief.primary), brief.primary, out_path)

    if judge_result.deliberation_summary:
        panel_summary = judge_result.deliberation_summary
        # Gap Fix 8: Parse DIRECTION from deliberation summary
        direction_match = re.search(
            r'DIRECTION:\s*\n?(.*?)(?:\n\n|\Z)',
            judge_result.deliberation_summary,
            re.DOTALL | re.IGNORECASE,
        )
        if direction_match:
            current_direction = direction_match.group(1).strip()

    # Gap Fix 9: Pass trajectory table to callback
    trajectory_table = format_trajectory_table(
        trajectory, list(brief.criteria.keys()),
        find_best(trajectory, brief.primary), brief.primary,
    )
    await _call_callback(on_iteration, record, trajectory, trajectory_table)

    # ------------------------------------------------------------------
    # Step 3: Iterations 1-N
    # ------------------------------------------------------------------
    max_iterations = brief.iterations

    for i in range(1, max_iterations + 1):
        # a) Check for regression rollback
        best_idx = find_best(trajectory, brief.primary)
        regression_note = None
        if trajectory[-1].regressed:
            if is_workspace:
                # Workspace: git rollback to best iteration's commit
                best_iter = trajectory[best_idx].iteration
                best_sha = iteration_commits.get(best_iter)
                if best_sha:
                    _git_rollback_workspace(
                        brief.artifact, best_sha, str(out_path)
                    )
                current_candidate = f"[Workspace at {brief.artifact}]"
            else:
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

        # Capture candidate after generator
        if is_workspace:
            # Workspace: generator edited files in place. Commit the changes.
            sha = _git_commit_iteration(brief.artifact, i)
            if sha:
                iteration_commits[i] = sha
            current_candidate = f"[Workspace at {brief.artifact}]"
        else:
            # Single-file: read candidate from file the generator wrote via Write tool.
            candidate_file = out_path / f"iteration-{i}-candidate.md"
            if candidate_file.exists():
                current_candidate = candidate_file.read_text(encoding="utf-8")
            else:
                # Generator didn't write the file — use its output and write it ourselves
                current_candidate = gen_output.candidate
                candidate_file.write_text(current_candidate, encoding="utf-8")

        # c) Evaluator
        candidate_path = str(out_path / f"iteration-{i}-candidate.md") if brief.artifact_type == "single-file" else None
        evaluator_output = await _run_evaluator(
            brief, candidate_path=candidate_path, iteration=i, output_dir=str(out_path)
        ) if brief.evaluator else ""

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
                evaluator_path=evaluator_path,
                prior_candidate_paths=prior_candidate_paths,
                cached_judges=cached_board_judges,
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
                evaluator_path=evaluator_path,
                prior_candidate_paths=prior_candidate_paths,
            )

        # Write raw judge output for downstream consumers
        if judge_result.raw_text:
            (out_path / f"iteration-{i}-judgment.md").write_text(
                judge_result.raw_text, encoding="utf-8"
            )

        # e) Reflect — LLM-based reflect mirroring the skill
        reflect_output = await dispatch_reflect(
            judge_output_text=judge_result.raw_text,
            generator_report=gen_output.report,
            iteration=i,
            max_iterations=max_iterations,
            criteria=brief.criteria,
            primary=brief.primary,
            artifact_type=brief.artifact_type,
            search_space=brief.search_space,
            output_dir=out_path,
            model=brief.clerk_model,
            judge_asi=judge_result.asi,
            judge_mode=brief.judge_mode,
            brief=brief,
        )

        record = reflect_output.record
        trajectory.append(record)

        if judge_result.deliberation_summary:
            panel_summary = judge_result.deliberation_summary

        # Use reflect output for stable wins, exploration, direction
        stable_wins_obj = reflect_output.stable_wins
        if reflect_output.direction:
            current_direction = reflect_output.direction
            stable_wins_obj.direction = current_direction
        elif current_direction:
            stable_wins_obj.direction = current_direction

        exploration_status = reflect_output.exploration_status

        # Pass trajectory table from reflect output to callback
        trajectory_table = reflect_output.trajectory_table
        if not trajectory_table:
            # Fallback: generate from Python if LLM didn't produce one
            trajectory_table = format_trajectory_table(
                trajectory, list(brief.criteria.keys()),
                find_best(trajectory, brief.primary), brief.primary,
            )
        await _call_callback(on_iteration, record, trajectory, trajectory_table)

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

    # Ensure final state matches best iteration
    if is_workspace:
        best_sha = iteration_commits.get(best_record.iteration)
        if best_sha and best_record.iteration != trajectory[-1].iteration:
            _git_rollback_workspace(brief.artifact, best_sha, str(out_path))

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
        usage=usage_tracker,
    )
