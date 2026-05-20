"""Minimal end-to-end test: simmer.refine() with api_provider='google'.

MANUAL RUN ONLY — not collected by pytest. Requires GEMINI_API_KEY.
Hits the real API and spends real money (~$0.20-$0.35 per run depending
on judge thinking level). For mocked unit tests of the same code paths,
see tests/test_gemini_adapter.py and the Google sections of
tests/test_client.py.

Usage:
    uv run python tests/smoke_gemini_dnd.py

Drives a 2-iteration simmer run against Gemini 3.5 Flash on a DnD adventure
hook artifact. Validates that generator + judge + clerk all work through
the new GeminiClient adapter.

Uses split_generator=True to bypass the agent loop (api_agent doesn't
speak Gemini's functionCall format — adapter doesn't forward tool_use).
String artifact, single-judge mode, no board.
"""

import asyncio
import os
import sys

from simmer_sdk import refine


DND_HOOK_SEED = (
    "The fishing village of Saltrest has stopped catching fish. For three "
    "weeks the nets have come up empty or full of bones — human bones, by "
    "the count. Mayor Halrik vanished last Thursday after rowing alone "
    "toward the sea caves on the north shore. The village's only cleric "
    "refuses to enter the water. A wandering necromancer was seen buying "
    "rope and lanterns at the market the day before the mayor disappeared."
)


CRITERIA = {
    "narrative_tension": "Stakes escalate; the hook conveys urgency and unease.",
    "player_agency": "Hook implies multiple investigative angles or factions, not a single rail.",
    "specificity": "Concrete names, places, and sensory details — not generic 'a town, a villain'.",
    "hook_clarity": "A new GM can read this once and know what's wrong and where to start.",
}


async def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set. Get one at https://aistudio.google.com/apikey")
        return 1

    print("="*60)
    print("  Gemini 3.5 Flash — DnD adventure hook refinement")
    print("="*60)
    print(f"\nSeed artifact ({len(DND_HOOK_SEED)} chars):\n{DND_HOOK_SEED}\n")
    print(f"Criteria: {list(CRITERIA.keys())}")
    print(f"Iterations: 2  |  judge=HIGH, generator/clerk=MINIMAL")
    print(f"Models: generator/judge/clerk all = gemini-3.5-flash")
    print(f"split_generator=True (bypasses agent tool_use path)\n")

    result = await refine(
        artifact=DND_HOOK_SEED,
        criteria=CRITERIA,
        evaluator="A skilled DnD DM evaluating an adventure hook for table-readiness.",
        iterations=2,
        mode="seedless",
        judge_mode="single",
        output_dir="docs/simmer/gemini-dnd-high-judge",
        # Google backend wiring
        api_provider="google",
        gemini_thinking_level="MINIMAL",       # default for everything else
        gemini_judge_thinking_level="HIGH",    # judge gets maximum reasoning depth
        gemini_generator_thinking_level="MINIMAL",
        gemini_clerk_thinking_level="MINIMAL",
        generator_model="gemini-3.5-flash",
        judge_model="gemini-3.5-flash",
        clerk_model="gemini-3.5-flash",
        # Use split generator to avoid the api_agent tool_use loop
        split_generator=True,
        split_generator_mode="always",
        executor_model="gemini-3.5-flash",
    )

    print("\n" + "="*60)
    print("  RESULT")
    print("="*60)
    print(f"\nBest iteration: {result.best_iteration}")
    print(f"Best composite: {result.composite}")
    print(f"Best scores: {result.best_scores}")
    print(f"\nTrajectory:")
    for rec in result.trajectory:
        reg = " [REGRESSED]" if rec.regressed else ""
        print(f"  iter {rec.iteration}: composite={rec.composite}{reg} | "
              f"key_change={rec.key_change[:80]}")

    if result.usage:
        print("\n" + result.usage.summary())

    print(f"\nOutput dir: {result.output_dir}")
    print(f"Best candidate ({len(result.best_candidate)} chars):\n")
    print(result.best_candidate[:1500])
    if len(result.best_candidate) > 1500:
        print(f"\n... [{len(result.best_candidate) - 1500} more chars truncated]")

    # Sanity assertions
    assert len(result.trajectory) >= 1, "No iterations completed"
    assert result.best_candidate, "No best candidate returned"
    assert all(len(r.scores) >= 3 for r in result.trajectory), \
        f"Judge failed to score all criteria: {[r.scores for r in result.trajectory]}"

    print("\n  PASS — refine() completed end-to-end on Gemini backend")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
