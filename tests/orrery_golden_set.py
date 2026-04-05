"""Orrery golden set integration test — mirrors worker/src/jobs/simmer_general.py exactly.

This test validates that simmer-sdk produces correct results for the orrery's
golden set refinement phase using local models. The seed, criteria, judge panel,
and sample docs are identical to the orrery pipeline.

Usage:
    # Full run with specified models
    uv run python tests/orrery_golden_set.py --generator gemma4:e4b --judge gemma4:31b --clerk gemma4:e4b

    # All e4b (fast, lower quality)
    uv run python tests/orrery_golden_set.py --generator gemma4:e4b --judge gemma4:e4b --clerk gemma4:e4b

    # All 31b (slow, higher quality)
    uv run python tests/orrery_golden_set.py --generator gemma4:31b --judge gemma4:31b --clerk gemma4:31b
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import anyio

from simmer_sdk import refine

# ---------------------------------------------------------------------------
# Orrery-identical seed ontology (from simmer_general.py)
# ---------------------------------------------------------------------------

SEED_ONTOLOGY = """\
Entity types to extract:
- Person — people, speakers, authors, creators
- Organization — companies, groups, teams, brands
- Topic — concepts, ideas, theories, fields, subjects
- Event — happenings, milestones, dates, releases
- Location — places, regions, settings, venues
- Thing — objects, tools, products, materials, artifacts

For each entity found in the text, output:
{"name": "entity name", "type": "EntityType"}

Rules:
- Only extract entities explicitly mentioned in the text
- Normalize names to lowercase
- Do not hallucinate entities not present in the source
"""

# ---------------------------------------------------------------------------
# Orrery-identical criteria and judge panel (from simmer_general.py)
# ---------------------------------------------------------------------------

CRITERIA = {
    "coverage": "Captures all entity types present in sample documents",
    "precision": "No hallucinated entities, no noise",
    "taxonomy_quality": "Entity types are meaningful, consistent, and cover the domain",
}

JUDGE_PANEL = [
    {
        "name": "Coverage & Depth",
        "lens": "Focus on whether the spec captures all entity types and important entities present in the sample documents",
    },
    {
        "name": "Precision & Quality",
        "lens": "Focus on whether extracted entities are accurate, well-typed, and free of noise or hallucination",
    },
]

# ---------------------------------------------------------------------------
# Sample doc selection — 10 docs matching orrery's LIMIT 10
# ---------------------------------------------------------------------------

# Orrery uses: SELECT ... ORDER BY RANDOM() LIMIT 10
# We use a fixed set for reproducibility across runs.
SAMPLE_DOCS = [
    "2024-04-05-Initial Betaworks meeting.md",
    "2024-04-08-Jordan from Betaworks.md",
    "2024-04-10-Adhoc Meet with James Cham.md",
    "2024-05-09-Meeting with Paul Hunkin (jsonify).md",
    "2024-06-14-Harper - Nate.md",
    "2024-12-18-Knowledge Graph Hacking.md",
    "2025-07-16-Applying Organization Theory to Specialized Agents.md",
    "2025-09-08-Justin McCarthy.md",
    "2026-01-23-Harper Reed and Joseph Turian.md",
    "2026-02-26 Future Business Strategies and Our Edge.md",
]

ORRERY_TEST_DOCS = Path("/Users/michaelsugimura/Documents/GitHub/Noospheric-Orrery/test_docs")


def setup_samples(output_dir: Path) -> Path:
    """Copy sample docs to the output directory, matching orrery's pattern."""
    sample_dir = output_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    found = 0
    for doc_name in SAMPLE_DOCS:
        src = ORRERY_TEST_DOCS / doc_name
        if src.exists():
            # Orrery uses doc ID as filename; we use the original name
            shutil.copy(src, sample_dir / doc_name)
            found += 1
        else:
            print(f"  WARNING: sample doc not found: {doc_name}")

    print(f"  Copied {found}/{len(SAMPLE_DOCS)} sample docs to {sample_dir}")
    return sample_dir


async def run_golden_set(
    generator_model: str,
    judge_model: str,
    clerk_model: str,
    judge_mode: str,
    iterations: int,
    output_base: Path,
    ollama_url: str,
) -> None:
    """Run the golden set phase matching orrery's simmer_general.py."""

    # Build run ID from model config
    run_id = f"{generator_model.replace(':', '-')}_judge-{judge_model.replace(':', '-')}_{judge_mode}_{datetime.now().strftime('%H%M')}"
    output_dir = output_base / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup sample docs
    sample_dir = setup_samples(output_dir)

    # Write seed (orrery writes this to specs_dir/general_seed.md)
    seed_path = output_dir / "seed.md"
    seed_path.write_text(SEED_ONTOLOGY)

    # Log config
    config = {
        "generator_model": generator_model,
        "judge_model": judge_model,
        "clerk_model": clerk_model,
        "judge_mode": judge_mode,
        "iterations": iterations,
        "ollama_url": ollama_url,
        "sample_docs": SAMPLE_DOCS,
        "timestamp": datetime.now().isoformat(),
    }
    (output_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(f"\nRun: {run_id}")
    print(f"  Generator: {generator_model}")
    print(f"  Judge: {judge_model}")
    print(f"  Clerk: {clerk_model}")
    print(f"  Mode: {judge_mode}, {iterations} iterations")
    print(f"  Output: {output_dir}")

    # Iteration callback — matches orrery's on_iteration
    async def on_iteration(record, trajectory, trajectory_table):
        print(f"  [golden_set] iter {record.iteration}: {record.composite}/10 — {record.key_change}", flush=True)

    # The refine() call — identical to orrery's simmer_general.py Phase 1
    golden_dir = output_dir / "golden"
    result = await refine(
        artifact=str(seed_path),
        criteria=CRITERIA,
        primary="coverage",
        iterations=iterations,
        judge_mode=judge_mode,
        judge_panel=JUDGE_PANEL if judge_mode == "board" else None,
        output_dir=golden_dir,
        generator_model=generator_model,
        judge_model=judge_model,
        clerk_model=clerk_model,
        background=f"Sample documents are in {sample_dir}. Read them to understand what entity types exist in this corpus.",
        on_iteration=on_iteration,
        api_provider="ollama",
        ollama_url=ollama_url,
    )

    # Write results
    print(f"\n{'='*60}")
    print(f"RESULTS — {run_id}")
    print(f"{'='*60}")
    print(f"Best: iteration {result.best_iteration} ({result.composite}/10)")
    print(f"Scores: {result.best_scores}")
    print(f"\nTrajectory:")
    for r in result.trajectory:
        print(f"  iter {r.iteration}: {r.composite} — {r.key_change}")

    print(f"\nBest candidate ({len(result.best_candidate)} chars):")
    print(result.best_candidate)

    # Save summary
    summary = {
        "run_id": run_id,
        "config": config,
        "best_iteration": result.best_iteration,
        "best_scores": result.best_scores,
        "composite": result.composite,
        "trajectory": [
            {"iteration": r.iteration, "composite": r.composite, "key_change": r.key_change, "scores": r.scores}
            for r in result.trajectory
        ],
        "best_candidate_length": len(result.best_candidate),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved to {output_dir / 'summary.json'}")


def main():
    parser = argparse.ArgumentParser(description="Orrery golden set test — mirrors simmer_general.py Phase 1")
    parser.add_argument("--generator", default="gemma4:e4b", help="Generator model (default: gemma4:e4b)")
    parser.add_argument("--judge", default="gemma4:31b", help="Judge model (default: gemma4:31b)")
    parser.add_argument("--clerk", default="gemma4:e4b", help="Clerk model (default: gemma4:e4b)")
    parser.add_argument("--judge-mode", default="single", choices=["single", "board"], help="Judge mode (default: single)")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations (default: 3)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    parser.add_argument("--output", default="tests/orrery_runs", help="Output base directory")
    args = parser.parse_args()

    output_base = Path(args.output)
    output_base.mkdir(parents=True, exist_ok=True)

    anyio.run(
        run_golden_set,
        args.generator,
        args.judge,
        args.clerk,
        args.judge_mode,
        args.iterations,
        output_base,
        args.ollama_url,
    )


if __name__ == "__main__":
    main()
