"""Gemini-backed simmer pipeline — Noospheric Orrery style taxonomy refinement.

MANUAL RUN ONLY — not collected by pytest. Requires GEMINI_API_KEY.
Hits the real API and spends real money (~$0.25 per full 3-iter run
with judge=HIGH).

Mirrors orrery_local_pipeline.py but swaps Ollama for Gemini 3.5 Flash via
the new simmer_sdk._gemini_adapter. Two-phase pipeline:

  Phase A: Open extraction across 5 meeting notes — build corpus evidence
  Phase B: Iterative refinement of the entity taxonomy against the evidence

Per-phase thinking levels (calibrated against earlier DnD A/B):
  extraction / condense / generator → MINIMAL (cheap structured output)
  judge → HIGH (the only setting that gave critical, non-saturated scores)

Usage:
    GEMINI_API_KEY=... uv run python tests/orrery_gemini_pipeline.py
"""

import asyncio
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from simmer_sdk._gemini_adapter import GeminiClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = "gemini-3.5-flash"
ITERATIONS = 3

FIXTURE_DOCS = Path(__file__).parent / "fixtures" / "sample_docs"
SAMPLE_DOCS = [
    "2024-04-05-Initial-Meeting.md",
    "2024-05-09-Product-Demo.md",
    "2024-06-14-Strategy-Sync.md",
    "2024-12-18-Knowledge-Graph-Design.md",
    "2025-07-16-Agent-Architecture.md",
]

# Orrery-identical seed taxonomy (matches orrery_local_pipeline.py exactly)
SEED_TAXONOMY = """\
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
# Prompts (kept identical to orrery_local_pipeline.py so results are comparable)
# ---------------------------------------------------------------------------
EXTRACT_SYSTEM = (
    "You are a knowledge graph analyst. Extract everything of value from "
    "documents. Respond directly."
)
EXTRACT_USER = """\
Read this document and extract EVERYTHING that a knowledge graph would want to capture.

Do not use any predefined categories. Just find what's there.

DOCUMENT:
{doc}

For each item found, report:
- NAME: the exact text
- WHAT IT IS: describe it in plain language (a person, a company, a dollar amount, a software tool, a concept, a date, etc.)
- WHY IT MATTERS: what role does it play in this document?

Be exhaustive. Extract names, organizations, tools, money, dates, concepts, relationships, roles — anything specific and meaningful. Skip generic words."""

CONDENSE_SYSTEM = "You are a data analyst. Summarize extraction results into categories. Respond directly."
CONDENSE_USER = """\
Here are entity extractions from {n_docs} documents:

{evidence}

Summarize what was found across ALL documents. Group by category:
- PEOPLE: [list all unique names]
- COMPANIES: [list all]
- SOFTWARE/TOOLS: [list all]
- DOLLAR AMOUNTS: [list all]
- DATES/TIMESTAMPS: [examples]
- DURATIONS: [list all]
- BUSINESS CONCEPTS: [list all]
- TECHNICAL CONCEPTS: [list all]
- BUSINESS PROCESSES: [list all]
- ROLES/TITLES: [list all]
- PRODUCTS/PROJECTS: [list all]
- SYSTEM IDS: [examples]
- EMAIL ADDRESSES: [list all]
- OTHER: [anything that doesn't fit above]

Be comprehensive. Include everything found."""

JUDGE_SYSTEM = (
    "You are a data architect evaluating taxonomy fitness against real corpus "
    "data. Be precise and critical. Respond directly."
)
JUDGE_USER = """\
Here is an entity taxonomy (iteration {iteration}):

{taxonomy}

Here is what was actually found in a corpus of {n_docs} meeting notes:

{evidence}

Evaluate: How well does this taxonomy capture what's in the corpus?

For each category of items found, state whether the taxonomy handles it:
- COVERED: [category] → maps to [type]
- PARTIALLY COVERED: [category] → sort of fits [type] but loses meaning
- NOT COVERED: [category] → no appropriate type exists

Then score:
- coverage: [N]/10 — what percentage of found items have a good home?
- precision: [N]/10 — will the types cause misclassification or ambiguity?
- taxonomy_quality: [N]/10 — does the taxonomy reflect what's actually in this corpus?
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[single most impactful change]"""

GENERATOR_SYSTEM = """\
You are an entity taxonomy designer. You improve extraction specifications
based on judge feedback. Output ONLY the improved specification — no commentary,
no explanation of changes. The output should be a complete, ready-to-use
extraction prompt."""
GENERATOR_USER = """\
Here is the current entity extraction specification:

{taxonomy}

The judge evaluated this against real meeting notes and scored it {composite}/10.

The single most impactful improvement direction (ASI):
{asi}

Produce an improved version of the specification. You may:
- Add new entity types
- Remove or rename existing types
- Add disambiguation rules
- Add examples
- Add boundary rules (what to extract vs what NOT to extract)
- Restructure the taxonomy

The improved spec must maintain the JSON output format: {{"name": "...", "type": "..."}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _call(client: GeminiClient, system: str, user: str, max_tokens: int = 4096) -> tuple[str, dict]:
    """Call Gemini through the adapter, return (text, usage_dict)."""
    response = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = response.content[0].text if response.content else ""
    return text, {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def parse_scores(judge_text: str) -> dict:
    scores: dict[str, int] = {}
    for match in re.finditer(
        r"\*{0,2}(coverage|precision|taxonomy_quality)\*{0,2}:\s*(\d+)/10",
        judge_text, re.IGNORECASE,
    ):
        scores[match.group(1).lower()] = int(match.group(2))
    composite = 0.0
    comp_match = re.search(r"COMPOSITE:\s*\*{0,2}([\d.]+)/10", judge_text, re.IGNORECASE)
    if comp_match:
        composite = float(comp_match.group(1))
    elif scores:
        composite = round(sum(scores.values()) / len(scores), 1)
    return {"scores": scores, "composite": composite}


def extract_asi(judge_text: str) -> str:
    m = re.search(r"ASI.*?:\s*\n?(.*)", judge_text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
async def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        return 1

    # Two clients — judge gets HIGH thinking, everything else MINIMAL.
    minimal_client = GeminiClient(api_key=api_key, thinking_level="MINIMAL")
    judge_client = GeminiClient(api_key=api_key, thinking_level="HIGH")

    run_id = f"gemini_pipeline_{datetime.now().strftime('%H%M')}"
    output_dir = Path("tests/orrery_runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    samples_dir = output_dir / "samples"
    samples_dir.mkdir(exist_ok=True)
    for doc_name in SAMPLE_DOCS:
        src = FIXTURE_DOCS / doc_name
        if src.exists():
            shutil.copy(src, samples_dir / doc_name)

    print(f"Run: {run_id}")
    print(f"Model: {MODEL}  (thinking: extract/condense/generator=MINIMAL, judge=HIGH)")
    print(f"Iterations: {ITERATIONS}")
    print(f"Output: {output_dir}\n")

    total_in = 0
    total_out_minimal = 0
    total_out_high = 0

    # =====================================================================
    # Phase A: Open extraction
    # =====================================================================
    print("=" * 60)
    print(f"PHASE A: Open extraction ({len(SAMPLE_DOCS)} docs)")
    print("=" * 60)

    all_extractions = []
    for i, doc_name in enumerate(SAMPLE_DOCS):
        doc_path = samples_dir / doc_name
        if not doc_path.exists():
            print(f"  [{i+1}/{len(SAMPLE_DOCS)}] SKIP: {doc_name}")
            continue
        content = doc_path.read_text(encoding="utf-8")[:3000]
        print(f"  [{i+1}/{len(SAMPLE_DOCS)}] {doc_name}...", end=" ", flush=True)
        result, usage = await _call(minimal_client, EXTRACT_SYSTEM, EXTRACT_USER.format(doc=content))
        total_in += usage["input_tokens"]
        total_out_minimal += usage["output_tokens"]
        all_extractions.append(f"=== {doc_name} ===\n{result}")
        print(f"({len(result)} chars, {usage['output_tokens']} out tok)")

    evidence_base = "\n\n".join(all_extractions)
    (output_dir / "evidence_base.md").write_text(evidence_base)
    print(f"\nEvidence base: {len(evidence_base)} chars saved")

    # Condense
    print("Condensing...", end=" ", flush=True)
    condense_result, usage = await _call(
        minimal_client,
        CONDENSE_SYSTEM,
        CONDENSE_USER.format(n_docs=len(SAMPLE_DOCS), evidence=evidence_base[:12000]),
        max_tokens=6000,
    )
    total_in += usage["input_tokens"]
    total_out_minimal += usage["output_tokens"]
    (output_dir / "evidence_condensed.md").write_text(condense_result)
    print(f"({len(condense_result)} chars, {usage['output_tokens']} out tok)")

    # =====================================================================
    # Phase B: Iterative refinement
    # =====================================================================
    print(f"\n{'=' * 60}")
    print("PHASE B: Iterative refinement (judge=HIGH)")
    print("=" * 60)

    current_taxonomy = SEED_TAXONOMY
    trajectory: list[dict] = []
    best_composite = 0.0
    best_iteration = 0
    best_taxonomy = current_taxonomy

    for iteration in range(ITERATIONS + 1):
        print(f"\n--- Iteration {iteration} ---")

        # Judge
        print("  Judge (HIGH)...", end=" ", flush=True)
        judge_result, j_usage = await _call(
            judge_client,
            JUDGE_SYSTEM,
            JUDGE_USER.format(
                iteration=iteration,
                taxonomy=current_taxonomy,
                n_docs=len(SAMPLE_DOCS),
                evidence=condense_result,
            ),
            max_tokens=4096,
        )
        total_in += j_usage["input_tokens"]
        total_out_high += j_usage["output_tokens"]
        (output_dir / f"iteration-{iteration}-judgment.md").write_text(judge_result)

        parsed = parse_scores(judge_result)
        asi = extract_asi(judge_result)
        scores = parsed["scores"]
        composite = parsed["composite"]

        regressed = composite < best_composite and iteration > 0
        if composite >= best_composite:
            best_composite = composite
            best_iteration = iteration
            best_taxonomy = current_taxonomy

        trajectory.append({
            "iteration": iteration,
            "scores": scores,
            "composite": composite,
            "asi": asi[:200],
            "regressed": regressed,
        })

        status = " REGRESSION" if regressed else ""
        print(f"{composite}/10{status} ({j_usage['output_tokens']} out tok)")
        print(f"    Scores: {scores}")
        print(f"    ASI: {asi[:150]}")

        (output_dir / f"iteration-{iteration}-candidate.md").write_text(current_taxonomy)

        # Generator (skip on last iteration)
        if iteration < ITERATIONS:
            print("  Generator (MINIMAL)...", end=" ", flush=True)
            gen_input = best_taxonomy if regressed else current_taxonomy
            gen_result, g_usage = await _call(
                minimal_client,
                GENERATOR_SYSTEM,
                GENERATOR_USER.format(
                    taxonomy=gen_input, composite=composite, asi=asi,
                ),
                max_tokens=4096,
            )
            total_in += g_usage["input_tokens"]
            total_out_minimal += g_usage["output_tokens"]
            current_taxonomy = gen_result
            print(f"({len(gen_result)} chars, {g_usage['output_tokens']} out tok)")

    # =====================================================================
    # Results
    # =====================================================================
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"Best: iteration {best_iteration} ({best_composite}/10)")
    print(f"\nTrajectory:")
    for r in trajectory:
        reg = " REGRESSION" if r["regressed"] else ""
        print(f"  iter {r['iteration']}: {r['composite']}/10  scores={r['scores']}{reg}")

    # Cost — Gemini 3.5 Flash @ $1.50 in / $9 out
    input_cost = (total_in / 1_000_000) * 1.50
    minimal_cost = (total_out_minimal / 1_000_000) * 9.00
    high_cost = (total_out_high / 1_000_000) * 9.00
    total_cost = input_cost + minimal_cost + high_cost
    print(f"\nUsage: input={total_in} tok, output(MINIMAL)={total_out_minimal} tok, output(HIGH judge)={total_out_high} tok")
    print(f"Cost: ${input_cost:.4f} in + ${minimal_cost:.4f} minimal out + ${high_cost:.4f} HIGH judge out = ${total_cost:.4f}")

    print(f"\nBest taxonomy ({len(best_taxonomy)} chars):")
    print(best_taxonomy[:2000])
    if len(best_taxonomy) > 2000:
        print(f"\n... [{len(best_taxonomy) - 2000} more chars]")

    summary = {
        "run_id": run_id,
        "model": MODEL,
        "iterations": ITERATIONS,
        "judge_thinking_level": "HIGH",
        "other_thinking_level": "MINIMAL",
        "trajectory": trajectory,
        "best_iteration": best_iteration,
        "best_composite": best_composite,
        "best_taxonomy_length": len(best_taxonomy),
        "usage": {
            "input_tokens": total_in,
            "output_tokens_minimal": total_out_minimal,
            "output_tokens_high_judge": total_out_high,
            "estimated_cost_usd": round(total_cost, 4),
        },
        "timestamp": datetime.now().isoformat(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (output_dir / "best_taxonomy.md").write_text(best_taxonomy)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
