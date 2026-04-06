"""Smoke tests for Ollama integration — run manually with models available.

Usage:
    uv run python tests/smoke_ollama.py

Tests the Anthropic-compatible endpoint, extract_text with reasoning models,
and the direct SDK client path. Does NOT test full simmer runs (see
test_integration.py for that).
"""

import asyncio
import sys

# ---------------------------------------------------------------------------
# Config — change these to match your local Ollama setup
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434"
JUDGE_MODEL = "gemma4:31b"
CLERK_MODEL = "gemma4:26b"


def header(msg: str) -> None:
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


async def test_1_raw_endpoint():
    """Test: Ollama's /v1/messages endpoint responds correctly."""
    header("Test 1: Raw Anthropic endpoint")
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/v1/messages",
            json={
                "model": JUDGE_MODEL,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": "Say hello in exactly 5 words. Be concise, no explanation."}],
            },
            headers={"x-api-key": "ollama", "Content-Type": "application/json"},
            timeout=120.0,
        )
        data = resp.json()
        print(f"  Status: {resp.status_code}")
        print(f"  Content blocks: {[b['type'] for b in data.get('content', [])]}")
        for block in data.get("content", []):
            if block["type"] == "text":
                print(f"  Text: {block['text'][:200]}")
        print(f"  Stop reason: {data.get('stop_reason')}")
        print(f"  Usage: {data.get('usage')}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        # Reasoning models return [thinking, text] — check we got content
        has_text = any(b["type"] == "text" for b in data.get("content", []))
        has_thinking = any(b["type"] == "thinking" for b in data.get("content", []))
        if has_thinking:
            print("  Note: reasoning model detected (thinking blocks present)")
        assert has_text, "No text block — model may need higher max_tokens for thinking overhead"
        print("  PASS")


async def test_2_sdk_client():
    """Test: AsyncAnthropic client works with Ollama base_url."""
    header("Test 2: Anthropic SDK client via Ollama")
    from simmer_sdk.client import create_async_client, extract_text
    from simmer_sdk.types import SetupBrief

    brief = SetupBrief(
        artifact="test",
        artifact_type="prompt",
        criteria={"quality": "Is it good?"},
        iterations=1,
        mode="seedless",
        api_provider="ollama",
        ollama_url=OLLAMA_URL,
        judge_model=JUDGE_MODEL,
        clerk_model=CLERK_MODEL,
    )

    client = create_async_client(brief)
    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": "What is 2+2? Answer in one word."}],
    )

    text = extract_text(response)
    print(f"  Content blocks: {[b.type for b in response.content]}")
    print(f"  Extracted text: {text[:200]}")
    print(f"  Has thinking: {'thinking' in [b.type for b in response.content]}")
    assert len(text) > 0, "extract_text returned empty"
    print("  PASS")


async def test_3_clerk_model():
    """Test: Clerk model (26b MoE) works for synthesis-style prompts."""
    header("Test 3: Clerk model (MoE) synthesis")
    from simmer_sdk.client import create_async_client, extract_text
    from simmer_sdk.types import SetupBrief

    brief = SetupBrief(
        artifact="test",
        artifact_type="prompt",
        criteria={"quality": "Is it good?"},
        iterations=1,
        mode="seedless",
        api_provider="ollama",
        ollama_url=OLLAMA_URL,
        clerk_model=CLERK_MODEL,
    )

    client = create_async_client(brief)
    response = await client.messages.create(
        model=CLERK_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": (
            "Three judges scored an essay:\n"
            "- Judge A: clarity 7/10, depth 6/10\n"
            "- Judge B: clarity 8/10, depth 7/10\n"
            "- Judge C: clarity 7/10, depth 8/10\n\n"
            "Synthesize their feedback into a single improvement direction."
        )}],
    )

    text = extract_text(response)
    print(f"  Content blocks: {[b.type for b in response.content]}")
    print(f"  Response length: {len(text)} chars")
    print(f"  First 300 chars: {text[:300]}")
    assert len(text) > 20, "Synthesis response too short"
    print("  PASS")


async def test_4_score_format():
    """Test: Model can produce the score format simmer expects."""
    header("Test 4: Judge scoring format")
    from simmer_sdk.client import create_async_client, extract_text
    from simmer_sdk.judge import parse_judge_output
    from simmer_sdk.types import SetupBrief

    brief = SetupBrief(
        artifact="test",
        artifact_type="prompt",
        criteria={
            "narrative_tension": "scenes have escalating stakes",
            "player_agency": "multiple decision points",
            "specificity": "concrete names, locations, details",
        },
        iterations=1,
        mode="seedless",
        api_provider="ollama",
        ollama_url=OLLAMA_URL,
        judge_model=JUDGE_MODEL,
    )

    client = create_async_client(brief)
    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": (
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
        )}],
    )

    text = extract_text(response)
    print(f"  Raw output:\n{text[:600]}")

    parsed = parse_judge_output(text, brief.criteria)
    print(f"\n  Parsed scores: {parsed.scores}")
    print(f"  Parsed ASI: {parsed.asi[:200] if parsed.asi else '(empty)'}")
    print(f"  Composite: {parsed.composite}")

    if len(parsed.scores) == 3:
        print("  PASS - all 3 criteria scored")
    elif len(parsed.scores) > 0:
        print(f"  PARTIAL - only {len(parsed.scores)}/3 criteria parsed")
    else:
        print("  FAIL - no scores parsed")


async def main():
    # Check models are available
    import subprocess
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    available = result.stdout

    models_needed = [JUDGE_MODEL, CLERK_MODEL]
    for model in models_needed:
        tag = model.split(":")[0]
        if tag not in available:
            print(f"ERROR: {model} not found in ollama list. Pull it first: ollama pull {model}")
            sys.exit(1)

    print(f"Using judge/generator: {JUDGE_MODEL}")
    print(f"Using clerk: {CLERK_MODEL}")

    await test_1_raw_endpoint()
    await test_2_sdk_client()
    await test_3_clerk_model()
    await test_4_score_format()

    header("All smoke tests complete")


if __name__ == "__main__":
    asyncio.run(main())
