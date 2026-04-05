"""Local model simmer pipeline — orrery golden set reference configuration.

Validates the two-phase approach for local models:
  Phase A: Open extraction (once, upfront) — build corpus evidence base
  Phase B: Iterative refinement — judge/generate loop using evidence base

Usage:
    uv run python tests/orrery_local_pipeline.py
"""

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemma4:26b"
OLLAMA_URL = "http://localhost:11434"
ITERATIONS = 3

FIXTURE_DOCS = Path(__file__).parent / "fixtures" / "sample_docs"
SAMPLE_DOCS = [
    "2024-04-05-Initial-Meeting.md",
    "2024-05-09-Product-Demo.md",
    "2024-06-14-Strategy-Sync.md",
    "2024-12-18-Knowledge-Graph-Design.md",
    "2025-07-16-Agent-Architecture.md",
]

# Orrery-identical seed
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
# Prompts
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = "You are a knowledge graph analyst. Extract everything of value from documents. Do not use extended thinking. Respond directly."

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

JUDGE_SYSTEM = "You are a data architect evaluating taxonomy fitness against real corpus data. Be precise and critical. Do not use extended thinking. Respond directly."

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
extraction prompt. Do not use extended thinking. Respond directly."""

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
# Pipeline
# ---------------------------------------------------------------------------

async def call_model(client: AsyncOpenAI, system: str, user: str, temperature: float = 0.15) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=4096,
        temperature=temperature,
        top_p=0.85,
    )
    return response.choices[0].message.content or ""


def parse_scores(judge_text: str) -> dict:
    """Extract scores from judge output."""
    import re
    scores = {}
    for match in re.finditer(r"(coverage|precision|taxonomy_quality):\s*(\d+)/10", judge_text, re.IGNORECASE):
        scores[match.group(1).lower()] = int(match.group(2))

    composite = 0.0
    comp_match = re.search(r"COMPOSITE:\s*([\d.]+)/10", judge_text, re.IGNORECASE)
    if comp_match:
        composite = float(comp_match.group(1))
    elif scores:
        composite = round(sum(scores.values()) / len(scores), 1)

    return {"scores": scores, "composite": composite}


def extract_asi(judge_text: str) -> str:
    """Extract ASI from judge output."""
    import re
    m = re.search(r"ASI.*?:\s*\n?(.*)", judge_text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


async def main():
    client = AsyncOpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")

    # Output dir
    run_id = f"local_pipeline_{MODEL.replace(':', '-')}_{datetime.now().strftime('%H%M')}"
    output_dir = Path("tests/orrery_runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy sample docs
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(exist_ok=True)
    for doc_name in SAMPLE_DOCS:
        src = FIXTURE_DOCS / doc_name
        if src.exists():
            shutil.copy(src, samples_dir / doc_name)

    print(f"Run: {run_id}")
    print(f"Model: {MODEL}")
    print(f"Iterations: {ITERATIONS}")
    print(f"Output: {output_dir}\n")

    # =====================================================================
    # Phase A: Open extraction (once)
    # =====================================================================
    print(f"{'='*60}")
    print("PHASE A: Open extraction (10 docs)")
    print(f"{'='*60}")

    all_extractions = []
    for i, doc_name in enumerate(SAMPLE_DOCS):
        doc_path = samples_dir / doc_name
        if not doc_path.exists():
            print(f"  [{i+1}/10] SKIP: {doc_name}")
            continue

        content = doc_path.read_text(encoding="utf-8")[:3000]
        print(f"  [{i+1}/10] {doc_name}...", end=" ", flush=True)

        result = await call_model(client, EXTRACT_SYSTEM, EXTRACT_USER.format(doc=content))
        all_extractions.append(f"=== {doc_name} ===\n{result}")
        print(f"({len(result)} chars)")

    evidence_base = "\n\n".join(all_extractions)
    (output_dir / "evidence_base.md").write_text(evidence_base)
    print(f"\nEvidence base: {len(evidence_base)} chars saved")

    # Condense evidence for judge prompt (full evidence can be too long)
    # Summarize by category across all docs
    print("\nCondensing evidence...", end=" ", flush=True)
    condense_result = await call_model(
        client,
        "You are a data analyst. Summarize extraction results into categories. Do not use extended thinking. Respond directly.",
        f"Here are entity extractions from {len(SAMPLE_DOCS)} documents:\n\n{evidence_base[:12000]}\n\n"
        "Summarize what was found across ALL documents. Group by category:\n"
        "- PEOPLE: [list all unique names]\n"
        "- COMPANIES: [list all]\n"
        "- SOFTWARE/TOOLS: [list all]\n"
        "- DOLLAR AMOUNTS: [list all]\n"
        "- DATES/TIMESTAMPS: [examples]\n"
        "- DURATIONS: [list all]\n"
        "- BUSINESS CONCEPTS: [list all]\n"
        "- TECHNICAL CONCEPTS: [list all]\n"
        "- BUSINESS PROCESSES: [list all]\n"
        "- ROLES/TITLES: [list all]\n"
        "- PRODUCTS/PROJECTS: [list all]\n"
        "- SYSTEM IDS: [examples]\n"
        "- EMAIL ADDRESSES: [list all]\n"
        "- OTHER: [anything that doesn't fit above]\n\n"
        "Be comprehensive. Include everything found.",
        temperature=0.1,
    )
    (output_dir / "evidence_condensed.md").write_text(condense_result)
    print(f"({len(condense_result)} chars)")

    # =====================================================================
    # Phase B: Iterative refinement
    # =====================================================================
    print(f"\n{'='*60}")
    print("PHASE B: Iterative refinement")
    print(f"{'='*60}")

    current_taxonomy = SEED_TAXONOMY
    trajectory = []
    best_composite = 0.0
    best_iteration = 0
    best_taxonomy = current_taxonomy

    for iteration in range(ITERATIONS + 1):  # 0 = seed scoring, 1..N = improvements
        print(f"\n--- Iteration {iteration} ---")

        # Judge
        print("  Judge...", end=" ", flush=True)
        judge_result = await call_model(
            client,
            JUDGE_SYSTEM,
            JUDGE_USER.format(
                iteration=iteration,
                taxonomy=current_taxonomy,
                n_docs=len(SAMPLE_DOCS),
                evidence=condense_result,
            ),
        )
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

        record = {
            "iteration": iteration,
            "scores": scores,
            "composite": composite,
            "asi": asi[:200],
            "regressed": regressed,
        }
        trajectory.append(record)

        status = "REGRESSION" if regressed else ""
        print(f"{composite}/10 {status}")
        print(f"  Scores: {scores}")
        print(f"  ASI: {asi[:150]}...")

        # Save current taxonomy
        (output_dir / f"iteration-{iteration}-candidate.md").write_text(current_taxonomy)

        # Generator (skip on last iteration)
        if iteration < ITERATIONS:
            print("  Generator...", end=" ", flush=True)

            # On regression, use best taxonomy instead of current
            gen_input = best_taxonomy if regressed else current_taxonomy

            gen_result = await call_model(
                client,
                GENERATOR_SYSTEM,
                GENERATOR_USER.format(
                    taxonomy=gen_input,
                    composite=composite,
                    asi=asi,
                ),
                temperature=0.3,
            )
            current_taxonomy = gen_result
            print(f"({len(gen_result)} chars)")

    # =====================================================================
    # Results
    # =====================================================================
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Best: iteration {best_iteration} ({best_composite}/10)")
    print(f"\nTrajectory:")
    for r in trajectory:
        reg = " REGRESSION" if r["regressed"] else ""
        print(f"  iter {r['iteration']}: {r['composite']}/10{reg}")

    print(f"\nBest taxonomy ({len(best_taxonomy)} chars):")
    print(best_taxonomy)

    # Save summary
    summary = {
        "run_id": run_id,
        "model": MODEL,
        "iterations": ITERATIONS,
        "trajectory": trajectory,
        "best_iteration": best_iteration,
        "best_composite": best_composite,
        "best_taxonomy_length": len(best_taxonomy),
        "timestamp": datetime.now().isoformat(),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # Save trajectory table
    header = "| Iteration | " + " | ".join(scores.keys()) + " | Composite | Regressed |"
    sep = "|" + "|".join(["---"] * (len(scores) + 2)) + "|"
    rows = []
    for r in trajectory:
        vals = " | ".join(str(r["scores"].get(k, "?")) for k in scores.keys())
        rows.append(f"| {r['iteration']} | {vals} | {r['composite']} | {r['regressed']} |")
    (output_dir / "trajectory.md").write_text(f"# Trajectory\n\n{header}\n{sep}\n" + "\n".join(rows))

    print(f"\nSaved to {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
