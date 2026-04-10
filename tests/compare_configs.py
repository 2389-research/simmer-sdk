"""Compare three generator configs on the same task with cost tracking.

Config 1: All Sonnet (baseline)
Config 2: All Haiku (cheap)
Config 3: Sonnet architect + Haiku executor (split generator)

Usage:
    uv run python tests/compare_configs.py

Requires Bedrock credentials (uses orrery's AWS config).
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import anyio

from simmer_sdk import refine

# Bedrock creds — pull from env or orrery's .env
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY", "")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

ARTIFACT = (
    "A one-shot DND adventure hook for a party of 4 level-5 characters. "
    "The setting: a coastal town where fishermen have been pulling up bones "
    "instead of fish for the past week. The town's mayor has gone missing. "
    "Should be 300-500 words, playable in a 3-4 hour session."
)

CRITERIA = {
    "narrative_tension": (
        "scenes have escalating stakes, time pressure, and meaningful "
        'consequences — 10/10 means every scene raises the question '
        '"what happens if we don\'t act?"'
    ),
    "player_agency": (
        "multiple decision points where the party's choices genuinely "
        "change the outcome — 10/10 means no railroading, at least 3 "
        "distinct paths through the adventure"
    ),
    "specificity": (
        "concrete names, locations, sensory details, NPC motivations — "
        "10/10 means a DM could run this cold without inventing anything"
    ),
}

CONFIGS = [
    {
        "name": "all-sonnet",
        "generator_model": "claude-sonnet-4-6",
        "judge_model": "claude-sonnet-4-6",
        "clerk_model": "claude-sonnet-4-6",
        "split_generator": False,
    },
    {
        "name": "all-haiku",
        "generator_model": "claude-haiku-4-5",
        "judge_model": "claude-haiku-4-5",
        "clerk_model": "claude-haiku-4-5",
        "split_generator": False,
    },
    {
        "name": "sonnet-architect-haiku-executor",
        "generator_model": "claude-sonnet-4-6",  # architect
        "judge_model": "claude-sonnet-4-6",       # judge stays sonnet
        "clerk_model": "claude-haiku-4-5",        # executor + synthesis
        "split_generator": True,
    },
]


async def run_config(config: dict, output_base: Path) -> dict:
    """Run a single config and return results."""
    name = config["name"]
    output_dir = output_base / name

    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"  Generator: {config['generator_model']}")
    print(f"  Judge: {config['judge_model']}")
    print(f"  Clerk: {config['clerk_model']}")
    print(f"  Split generator: {config['split_generator']}")
    print(f"{'='*60}")

    start = datetime.now()
    result = await refine(
        artifact=ARTIFACT,
        criteria=CRITERIA,
        primary="player_agency",
        iterations=2,
        mode="seedless",
        judge_mode="single",
        output_dir=output_dir,
        generator_model=config["generator_model"],
        judge_model=config["judge_model"],
        clerk_model=config["clerk_model"],
        split_generator=config["split_generator"],
        api_provider="bedrock",
        aws_access_key=AWS_ACCESS_KEY,
        aws_secret_key=AWS_SECRET_KEY,
        aws_region=AWS_REGION,
    )
    elapsed = (datetime.now() - start).total_seconds()

    # Usage summary
    usage = result.usage
    usage_summary = usage.summary() if usage else "No usage data"
    usage_dict = usage.to_dict() if usage else {}

    print(f"\nResults: {name}")
    print(f"  Best: iteration {result.best_iteration} ({result.composite}/10)")
    print(f"  Scores: {result.best_scores}")
    print(f"  Time: {elapsed:.0f}s")
    print(f"\n{usage_summary}")

    for r in result.trajectory:
        print(f"  iter {r.iteration}: {r.composite} — {r.key_change}")

    summary = {
        "config": config,
        "best_iteration": result.best_iteration,
        "best_scores": result.best_scores,
        "composite": result.composite,
        "trajectory": [
            {"iteration": r.iteration, "composite": r.composite, "key_change": r.key_change}
            for r in result.trajectory
        ],
        "elapsed_seconds": elapsed,
        "usage": usage_dict,
        "candidate_length": len(result.best_candidate),
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


async def main():
    if not AWS_ACCESS_KEY:
        # Try loading from orrery .env
        env_path = Path.home() / "Documents/GitHub/Noospheric-Orrery/.env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

        global AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION
        AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY", "")
        AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY", "")
        AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    if not AWS_ACCESS_KEY:
        print("ERROR: No AWS credentials. Set AWS_ACCESS_KEY/AWS_SECRET_KEY or have orrery .env available.")
        return

    output_base = Path("tests/config_comparison") / datetime.now().strftime("%Y%m%d_%H%M")
    output_base.mkdir(parents=True, exist_ok=True)

    results = []
    for config in CONFIGS:
        summary = await run_config(config, output_base)
        results.append(summary)

    # Final comparison table
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")
    print(f"{'Config':<35} {'Score':>6} {'Cost':>10} {'Time':>8} {'Tokens':>10}")
    print("-" * 75)
    for r in results:
        name = r["config"]["name"]
        score = r["composite"]
        cost = r["usage"].get("estimated_cost_usd", 0)
        time = r["elapsed_seconds"]
        tokens = r["usage"].get("total_tokens", 0)
        print(f"{name:<35} {score:>6.1f} ${cost:>9.4f} {time:>7.0f}s {tokens:>10,}")

    (output_base / "comparison.json").write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {output_base}")


if __name__ == "__main__":
    anyio.run(main)
