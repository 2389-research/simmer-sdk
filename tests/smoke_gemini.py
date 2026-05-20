"""Smoke tests for Gemini Flash — MANUAL RUN ONLY.

Not collected by pytest. Requires GEMINI_API_KEY. Hits the real API and
spends real money (~$0.01 per full run at time of writing).

Usage:
    uv run python tests/smoke_gemini.py

Hits Google's native generativelanguage.googleapis.com endpoint directly
via httpx (Gemini's response shape is not Anthropic-compatible, so the
simmer SDK client factory cannot be used as-is). Validates that Gemini
Flash can produce the judge-score format simmer expects, and measures
latency / thinking-token cost across all four thinkingLevel settings.

Gemini 3.x uses thinkingLevel (minimal/low/medium/high), not the
deprecated thinkingBudget. Default is medium.

Does NOT modify simmer-sdk source. If results look good the follow-up
is a google backend in src/simmer_sdk/client.py.
"""

import asyncio
import os
import sys
import time

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-3.5-flash"

THINKING_LEVELS = ["MINIMAL", "LOW", "MEDIUM", "HIGH"]


def header(msg: str) -> None:
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def _gemini_text(data: dict) -> str:
    """Extract text from Gemini response (parts list, not Anthropic shape)."""
    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def _usage_summary(data: dict) -> dict:
    u = data.get("usageMetadata", {})
    return {
        "prompt": u.get("promptTokenCount", 0),
        "candidates": u.get("candidatesTokenCount", 0),
        "thoughts": u.get("thoughtsTokenCount", 0),
        "total": u.get("totalTokenCount", 0),
    }


def _print_usage(data: dict) -> None:
    u = _usage_summary(data)
    print(f"  Usage: prompt={u['prompt']} candidates={u['candidates']} "
          f"thoughts={u['thoughts']} total={u['total']}")


async def _call_gemini(client, payload: dict) -> tuple[float, dict]:
    t0 = time.perf_counter()
    resp = await client.post(
        f"{GEMINI_ENDPOINT}/{MODEL}:generateContent",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": os.environ["GEMINI_API_KEY"],
        },
        timeout=180.0,
    )
    elapsed = time.perf_counter() - t0
    resp.raise_for_status()
    return elapsed, resp.json()


async def test_1_default():
    """Test: default behavior (no thinkingLevel set) — should be 'medium'."""
    header("Test 1: Default (no thinkingLevel — docs say MEDIUM)")
    import httpx

    async with httpx.AsyncClient() as client:
        elapsed, data = await _call_gemini(client, {
            "contents": [{"parts": [{"text": "Say hello in exactly 5 words."}]}],
        })
        text = _gemini_text(data)
        print(f"  Latency: {elapsed:.2f}s")
        print(f"  Text: {text[:200]}")
        _print_usage(data)
        assert text, "No text in candidates"
        print("  PASS")


async def test_2_minimal():
    """Test: thinkingLevel=MINIMAL should produce ~0 thought tokens."""
    header("Test 2: thinkingLevel=MINIMAL")
    import httpx

    async with httpx.AsyncClient() as client:
        elapsed, data = await _call_gemini(client, {
            "contents": [{"parts": [{"text": "Say hello in exactly 5 words."}]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "MINIMAL"}},
        })
        text = _gemini_text(data)
        print(f"  Latency: {elapsed:.2f}s")
        print(f"  Text: {text[:200]}")
        _print_usage(data)
        thoughts = _usage_summary(data)["thoughts"]
        # Don't hard-assert thoughts==0 — docs don't say MINIMAL is a hard zero.
        # Just observe.
        print(f"  Thoughts: {thoughts} (expect very low / 0)")
        assert text, "No text in candidates"
        print("  PASS")


async def test_3_clerk_synthesis():
    """Test: clerk-style synthesis at MINIMAL (no reasoning needed)."""
    header("Test 3: Clerk-style synthesis (thinkingLevel=MINIMAL)")
    import httpx

    prompt = (
        "Three judges scored an essay:\n"
        "- Judge A: clarity 7/10, depth 6/10\n"
        "- Judge B: clarity 8/10, depth 7/10\n"
        "- Judge C: clarity 7/10, depth 8/10\n\n"
        "Synthesize their feedback into a single improvement direction."
    )

    async with httpx.AsyncClient() as client:
        elapsed, data = await _call_gemini(client, {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "MINIMAL"}},
        })
        text = _gemini_text(data)
        print(f"  Latency: {elapsed:.2f}s")
        print(f"  Response length: {len(text)} chars")
        print(f"  First 300 chars: {text[:300]}")
        _print_usage(data)
        assert len(text) > 20, "Synthesis response too short"
        print("  PASS")


async def test_4_judge_level_sweep():
    """Test: same judge prompt across all four thinkingLevel settings.

    Reports latency / thought tokens / parse success for each. This is the
    main measurement — answers: which level is the sweet spot for simmer
    judges, and does score-format compliance hold across levels?
    """
    header("Test 4: Judge prompt sweep across all thinkingLevel values")
    import httpx
    from simmer_sdk.judge import parse_judge_output

    criteria = {
        "narrative_tension": "scenes have escalating stakes",
        "player_agency": "multiple decision points",
        "specificity": "concrete names, locations, details",
    }
    prompt = (
        "You are evaluating a DND adventure hook. Score it on these criteria.\n"
        "Output EXACTLY this format:\n\n"
        "ITERATION 0 SCORES:\n"
        "  narrative_tension: [N]/10 -- [reasoning]\n"
        "  player_agency: [N]/10 -- [reasoning]\n"
        "  specificity: [N]/10 -- [reasoning]\n"
        "COMPOSITE: [N.N]/10\n\n"
        "ASI (highest-leverage direction):\n"
        "[your single most impactful improvement]\n\n"
        "The adventure: A coastal town where fishermen pull up bones instead of fish. "
        "The mayor is missing. A necromancer in an underwater cave is raising an army."
    )

    results: list[dict] = []

    async with httpx.AsyncClient() as client:
        for level in THINKING_LEVELS:
            print(f"\n  --- thinkingLevel={level} ---")
            elapsed, data = await _call_gemini(client, {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"thinkingConfig": {"thinkingLevel": level}},
            })
            text = _gemini_text(data)
            usage = _usage_summary(data)
            parsed = parse_judge_output(text, criteria)

            print(f"    Latency: {elapsed:.2f}s")
            print(f"    Tokens: candidates={usage['candidates']} thoughts={usage['thoughts']} total={usage['total']}")
            print(f"    Parsed: {len(parsed.scores)}/3 criteria — {parsed.scores}")
            print(f"    Composite: {parsed.composite}")
            print(f"    ASI (first 120 chars): {parsed.asi[:120] if parsed.asi else '(empty)'}")

            results.append({
                "level": level,
                "latency": elapsed,
                "candidates": usage["candidates"],
                "thoughts": usage["thoughts"],
                "parsed_count": len(parsed.scores),
                "scores": parsed.scores,
                "composite": parsed.composite,
            })

    # Summary table
    print("\n  --- SUMMARY ---")
    print(f"  {'Level':<10} {'Latency':>8} {'Cands':>7} {'Thoughts':>9} {'Parsed':>8} {'Composite':>10}")
    for r in results:
        print(f"  {r['level']:<10} {r['latency']:>7.2f}s {r['candidates']:>7} {r['thoughts']:>9} "
              f"{r['parsed_count']}/3{'':>4} {r['composite']:>10.1f}")

    all_full_parse = all(r["parsed_count"] == 3 for r in results)
    if all_full_parse:
        print("\n  PASS — all 4 levels produced parseable judge output")
    else:
        print("\n  PARTIAL — some levels failed to produce 3 criteria")


async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set. Get one at https://aistudio.google.com/apikey")
        sys.exit(1)

    print(f"Using model: {MODEL}")
    print(f"Endpoint: {GEMINI_ENDPOINT}")

    await test_1_default()
    await test_2_minimal()
    await test_3_clerk_synthesis()
    await test_4_judge_level_sweep()

    header("All smoke tests complete")


if __name__ == "__main__":
    asyncio.run(main())
