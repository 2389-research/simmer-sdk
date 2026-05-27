"""Integration tests — full simmer loop using real API calls.

Run with:
    ANTHROPIC_API_KEY=... uv run pytest -m integration tests/test_integration.py -v

These tests are excluded from normal pytest runs to avoid incurring API costs.
Both tests use claude-haiku-4-5 for generator and judge to keep costs low.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from simmer_sdk.refine import refine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dnd_adventure_hook_seedless(has_api_key):
    """Full loop: seedless mode, single judge, 2 iterations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await refine(
            artifact=(
                "A level 5 party explores a haunted lighthouse on a rocky coast. "
                "The keeper vanished a week ago and ships have been crashing on the "
                "rocks since."
            ),
            criteria={
                "narrative_tension": (
                    "escalating stakes with time pressure and consequences"
                ),
                "player_agency": (
                    "genuine decision points that change the outcome, not a railroad"
                ),
                "specificity": (
                    "concrete names, locations, sensory details, not generic fantasy"
                ),
            },
            iterations=2,
            mode="seedless",
            judge_mode="single",
            output_dir=Path(tmpdir) / "simmer",
            generator_model="claude-haiku-4-5",
            judge_model="claude-haiku-4-5",
        )

    # Print trajectory for manual inspection
    print("\n--- DND Adventure Hook Trajectory ---")
    for rec in result.trajectory:
        print(
            f"  iteration={rec.iteration} composite={rec.composite} "
            f"regressed={rec.regressed} key_change={rec.key_change[:60]!r}"
        )
    print(f"  best_iteration={result.best_iteration} composite={result.composite}")
    print(f"  best_candidate[:200]={result.best_candidate[:200]!r}")

    # Structural assertions — do not assert specific score values (LLM-dependent)
    assert result.best_candidate, "best_candidate must be non-empty"
    assert result.composite > 0, "composite score must be positive"
    # seed (iteration 0) + 2 refinement iterations = 3 entries
    assert len(result.trajectory) == 3, (
        f"expected 3 trajectory entries (seed + 2 iterations), got {len(result.trajectory)}"
    )
    assert result.trajectory[0].iteration == 0, "first entry must be seed (iteration 0)"
    assert result.trajectory[1].iteration == 1
    assert result.trajectory[2].iteration == 2
    assert result.best_iteration in {0, 1, 2}, "best_iteration must be within range"
    assert isinstance(result.best_scores, dict), "best_scores must be a dict"
    assert len(result.best_scores) > 0, "best_scores must not be empty"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trajectory_logging_end_to_end(has_api_key):
    """The full refine() loop wires the trajectory logger: a JSONL event log is
    written with run/iteration/llm_call/outcome events, correctly correlated."""
    import glob

    from simmer_sdk.trajectory_view import load_run

    with tempfile.TemporaryDirectory() as tmpdir:
        logdir = Path(tmpdir) / "trajectories"
        result = await refine(
            artifact="A tagline for a CLI tool that refines prompts.",
            criteria={"punchiness": "tight, no filler", "clarity": "obvious what it does"},
            iterations=1,
            mode="from-paste",
            judge_mode="single",
            output_dir=Path(tmpdir) / "simmer",
            generator_model="claude-haiku-4-5",
            judge_model="claude-haiku-4-5",
            clerk_model="claude-haiku-4-5",
            trajectory_log_dir=str(logdir),
        )

        files = glob.glob(str(logdir / "*.jsonl"))
        assert len(files) == 1, f"expected one trajectory file, got {files}"
        view = load_run(files[0])

    counts = view.event_counts
    # The orchestration events are present
    assert counts.get("run") == 1
    assert counts.get("outcome") == 1
    assert counts.get("iteration", 0) >= 2          # seed (0) + iteration 1
    assert counts.get("llm_call", 0) >= 2           # at least generator + judge turns
    # Roles were captured at the client boundary
    roles = {s.role for it in view.iterations for s in it.sessions}
    assert "generator" in roles and "judge" in roles
    # Outcome agrees with the returned result
    assert view.outcome["best_iteration"] == result.best_iteration
    # Iterations 0 and 1 both recorded
    assert {0, 1}.issubset({it.iteration for it in view.iterations})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_refinement_from_paste(has_api_key):
    """Full loop: from-paste mode, single judge, 2 iterations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await refine(
            artifact=(
                "Hi, I wanted to reach out about our new product. It does a lot of "
                "things and I think you'd like it. Let me know if you want to chat."
            ),
            criteria={
                "value_clarity": (
                    "reader immediately understands the specific problem solved"
                ),
                "response_likelihood": (
                    "CTA is so low-friction the recipient replies without thinking"
                ),
            },
            iterations=2,
            mode="from-paste",
            output_dir=Path(tmpdir) / "simmer",
            generator_model="claude-haiku-4-5",
            judge_model="claude-haiku-4-5",
        )

    # Print trajectory for manual inspection
    print("\n--- Email Refinement Trajectory ---")
    for rec in result.trajectory:
        print(
            f"  iteration={rec.iteration} composite={rec.composite} "
            f"regressed={rec.regressed} key_change={rec.key_change[:60]!r}"
        )
    print(f"  best_iteration={result.best_iteration} composite={result.composite}")
    print(f"  best_candidate[:200]={result.best_candidate[:200]!r}")

    # Structural assertions — do not assert specific score values (LLM-dependent)
    assert result.best_candidate, "best_candidate must be non-empty"
    assert result.composite > 0, "composite score must be positive"
    # seed (iteration 0) + 2 refinement iterations = 3 entries
    assert len(result.trajectory) == 3, (
        f"expected 3 trajectory entries (seed + 2 iterations), got {len(result.trajectory)}"
    )
    assert result.trajectory[0].iteration == 0, "first entry must be seed (iteration 0)"
    assert result.trajectory[1].iteration == 1
    assert result.trajectory[2].iteration == 2
    assert result.best_iteration in {0, 1, 2}, "best_iteration must be within range"
    assert isinstance(result.best_scores, dict), "best_scores must be a dict"
    assert len(result.best_scores) > 0, "best_scores must not be empty"
