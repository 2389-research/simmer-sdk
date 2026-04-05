"""Full orrery-matching local pipeline — Phase 1 (golden set) + Phase 2 (extraction spec).

Mirrors worker/src/jobs/simmer_general.py using local models.

Phase 1: Produces taxonomy + reference entity list (the golden set)
  - Open extraction across all docs (26B, upfront)
  - Iterative refinement of taxonomy + entity compilation
  - Output: golden set with types + JSON array of all entities

Phase 2: Produces executable extraction spec tested against golden set
  - Uses evaluator to run spec against docs each iteration
  - Judge sees quantitative metrics + raw extraction outputs
  - Output: prompt that reliably extracts golden set entities

Usage:
    uv run python tests/orrery_full_pipeline.py
"""

import asyncio
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "gemma4:26b"
EXTRACTION_MODEL = "gemma4:e4b"  # Smaller model for actual extraction in Phase 2
JUDGE_MODEL = "gemma4:26b"  # Same model for everything — judges get evaluator evidence
OLLAMA_URL = "http://localhost:11434"
PHASE1_ITERATIONS = 3
PHASE2_ITERATIONS = 3

ORRERY_TEST_DOCS = Path("/Users/michaelsugimura/Documents/GitHub/Noospheric-Orrery/test_docs")
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

# Orrery-matching seed
SEED_GOLDEN_SET = """\
# Golden Set

## Entity Type Taxonomy
- Person — people, speakers, authors, creators
- Organization — companies, groups, teams, brands
- Topic — concepts, ideas, theories, fields, subjects
- Event — happenings, milestones, dates, releases
- Location — places, regions, settings, venues
- Thing — objects, tools, products, materials, artifacts

## Reference Entities

Read every sample document and list ALL entities you find. Each entity must actually
appear in at least one sample document — do not invent entities.

Format as a JSON array:
```json
[
  {"name": "entity name lowercase", "type": "EntityType"},
  ...
]
```

The reference entity list is the ground truth that extraction specs will be tested against.
Be thorough — every named person, organization, product, concept, place, and event
mentioned in the sample documents should appear here.
"""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def call_model(client: AsyncOpenAI, model: str, system: str, user: str,
                     temperature: float = 0.15, max_tokens: int = 8192) -> str:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.85,
    )
    return response.choices[0].message.content or ""


def parse_scores(text: str) -> tuple[dict[str, int], float]:
    scores = {}
    for m in re.finditer(r"\*{0,2}(coverage|precision|taxonomy_quality|format_compliance)\*{0,2}:\s*(\d+)/10", text, re.IGNORECASE):
        scores[m.group(1).lower()] = int(m.group(2))
    composite = 0.0
    cm = re.search(r"COMPOSITE:\s*\*{0,2}([\d.]+)/10", text, re.IGNORECASE)
    if cm:
        composite = float(cm.group(1))
    elif scores:
        composite = round(sum(scores.values()) / len(scores), 1)
    return scores, composite


def extract_asi(text: str) -> str:
    m = re.search(r"ASI.*?:\s*\n?(.*)", text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip()[:500] if m else ""


# ---------------------------------------------------------------------------
# Phase 1: Golden Set
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = "You are a knowledge graph analyst. Extract everything of value. Do not use extended thinking. Respond directly."

EXTRACT_PROMPT = """\
Read this document and extract EVERYTHING a knowledge graph would capture.
No predefined categories. Just find what's there.

DOCUMENT:
{doc}

For each item:
- NAME: exact text
- WHAT IT IS: plain language description
- WHY IT MATTERS: role in this document

Be exhaustive. Extract names, organizations, tools, money, dates, concepts, roles — anything specific."""

PHASE1_JUDGE_SYSTEM = "You are a data architect evaluating a golden set against real corpus data. Be critical. Do not use extended thinking. Respond directly."

PHASE1_JUDGE_PROMPT = """\
Here is a golden set (entity taxonomy + reference entity list) for iteration {iteration}:

{golden_set}

Here is what was actually found across {n_docs} meeting notes via open extraction:

{evidence}

Evaluate:
1. TAXONOMY: Are the entity types right for this corpus? What types are missing or too broad?
2. ENTITY LIST: Does the reference list contain all entities from the evidence? What's missing?
3. QUALITY: Are entities correctly typed? Any hallucinations?

Score:
- coverage: [N]/10 — does the golden set capture everything in the corpus?
- precision: [N]/10 — are all listed entities real and correctly typed?
- taxonomy_quality: [N]/10 — are the types meaningful for this domain?
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[single most impactful improvement]"""

PHASE1_GEN_SYSTEM = """\
You are a golden set designer. Output ONLY the improved golden set — no commentary.
The golden set must contain:
1. An entity type taxonomy (the categories with descriptions)
2. A JSON array of EVERY entity found in the sample documents
Do not use extended thinking. Respond directly."""

PHASE1_GEN_PROMPT = """\
Current golden set:

{golden_set}

Score: {composite}/10

ASI (improvement direction):
{asi}

Here is what was found across the sample documents (use this to populate the entity list):
{evidence}

Produce an improved golden set. You may:
- Add/remove/rename entity types
- Add disambiguation rules
- Add/remove/correct entities in the reference list
- Fix entity type assignments

The reference entity list MUST be a JSON array: [{{"name": "...", "type": "..."}}]
Every entity must actually appear in the sample documents. Use the evidence above to compile the list."""


# ---------------------------------------------------------------------------
# Phase 2: Extraction Spec
# ---------------------------------------------------------------------------

PHASE2_EVAL_SYSTEM = "You are an entity extraction system. Output valid JSON arrays only. No commentary. Do not use extended thinking. Respond directly."

PHASE2_EVAL_PROMPT = """\
{spec}

TEXT:
{doc}

Respond with JSON only. Output a JSON array of extracted entities:
[{{"name": "entity name", "type": "EntityType"}}, ...]
If no entities found, output: []"""

PHASE2_JUDGE_SYSTEM = "You are evaluating an extraction spec based on empirical test results. Be precise. Do not use extended thinking. Respond directly."

PHASE2_JUDGE_PROMPT = """\
Iteration {iteration} extraction spec was tested against {n_docs} documents.

THE SPEC:
{spec}

EVALUATOR RESULTS:
{eval_results}

GOLDEN SET (ground truth):
{golden_set_summary}

Score based on the ACTUAL extraction results, not what the spec looks like:
- coverage: [N]/10 — what fraction of golden set entities were extracted?
- precision: [N]/10 — what fraction of extracted entities are correct?
- format_compliance: [N]/10 — is the JSON output valid and consistent?
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[single most impactful change to the spec to improve extraction results]"""

PHASE2_GEN_SYSTEM = """\
You are an extraction spec designer. Output ONLY the improved extraction prompt — no commentary.
The spec must be a complete, ready-to-use prompt that a model can execute against any document
to produce JSON entity output. Do not use extended thinking. Respond directly."""

PHASE2_GEN_PROMPT = """\
Current extraction spec:

{spec}

Score: {composite}/10

Evaluator found these problems:
{eval_results}

ASI (improvement direction):
{asi}

Produce an improved extraction spec. You may:
- Rewrite instructions for clarity
- Add/improve examples and counter-examples
- Add boundary rules (what to extract vs not)
- Change output format instructions
- Add disambiguation guidance

The spec must produce output as: [{{"name": "...", "type": "..."}}]"""


# ---------------------------------------------------------------------------
# Evaluator (Phase 2)
# ---------------------------------------------------------------------------

def parse_extraction_json(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [{"name": e.get("name", "").lower().strip(), "type": e.get("type", "")}
                    for e in data if isinstance(e, dict) and "name" in e]
        if isinstance(data, dict) and "entities" in data:
            return [{"name": e.get("name", "").lower().strip(), "type": e.get("type", "")}
                    for e in data["entities"] if isinstance(e, dict)]
    except json.JSONDecodeError:
        pass
    # JSONL fallback
    entities = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if "name" in obj and "type" in obj:
                    entities.append({"name": obj["name"].lower().strip(), "type": obj["type"]})
            except json.JSONDecodeError:
                continue
    return entities


def parse_golden_entities(golden_text: str) -> list[tuple[str, str]]:
    """Extract (name, type) tuples from golden set JSON array."""
    entities = []
    # Find JSON array in the text
    m = re.search(r'\[[\s\S]*\]', golden_text)
    if m:
        try:
            data = json.loads(m.group())
            for e in data:
                if isinstance(e, dict) and "name" in e and "type" in e:
                    entities.append((e["name"].lower().strip(), e["type"].strip()))
        except json.JSONDecodeError:
            pass
    return entities


async def run_evaluator(client: AsyncOpenAI, spec_text: str, samples_dir: Path,
                        golden_entities: list[tuple[str, str]], eval_dir: Path) -> str:
    """Run extraction spec against all docs, diff against golden set."""
    eval_dir.mkdir(parents=True, exist_ok=True)
    docs = sorted(samples_dir.glob("*.md"))

    total_hits = 0
    total_misses = 0
    total_fps = 0
    total_extracted = 0
    per_doc = []

    golden_set = set(golden_entities)

    for doc_path in docs:
        doc_text = doc_path.read_text(encoding="utf-8")[:3000]

        raw = await call_model(
            client, EXTRACTION_MODEL, PHASE2_EVAL_SYSTEM,
            PHASE2_EVAL_PROMPT.format(spec=spec_text, doc=doc_text),
            temperature=0.1,
        )
        entities = parse_extraction_json(raw)

        # Diff
        extracted_set = set((e["name"], e["type"]) for e in entities)
        hits = extracted_set & golden_set
        fps = extracted_set - golden_set
        # Misses: golden entities that could reasonably be in this doc
        # (we can't know which golden entities are in which doc, so track globally)

        total_hits += len(hits)
        total_fps += len(fps)
        total_extracted += len(entities)

        # Save raw
        (eval_dir / f"{doc_path.stem}.json").write_text(json.dumps({
            "doc": doc_path.name,
            "extracted": entities,
            "hits": [list(h) for h in hits],
            "false_positives": [list(f) for f in fps],
        }, indent=2))

        per_doc.append(f"  {doc_path.name}: extracted={len(entities)}, hits={len(hits)}, fps={len(fps)}")

    # Near-miss analysis: extracted name matches golden name but type differs
    all_extracted_names = set()
    for doc_path in docs:
        raw_file = eval_dir / f"{doc_path.stem}.json"
        data = json.loads(raw_file.read_text())
        for e in data["extracted"]:
            all_extracted_names.add(e["name"])

    near_misses = []
    for gname, gtype in golden_entities:
        if gname in all_extracted_names:
            # Check if it was extracted with wrong type
            for doc_path in docs:
                data = json.loads((eval_dir / f"{doc_path.stem}.json").read_text())
                for e in data["extracted"]:
                    if e["name"] == gname and e["type"] != gtype:
                        near_misses.append(f"{gname}: expected {gtype}, got {e['type']}")

    precision = total_hits / total_extracted if total_extracted > 0 else 0
    recall = total_hits / len(golden_set) if golden_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    summary = (
        f"=== Spec Evaluation ===\n"
        f"Golden set: {len(golden_set)} entities\n"
        f"Total extracted: {total_extracted} across {len(docs)} docs\n"
        f"Hits: {total_hits} | False positives: {total_fps}\n"
        f"Precision: {precision:.0%} | Recall: {recall:.0%} | F1: {f1:.0%}\n"
        f"\nPer-doc:\n" + "\n".join(per_doc)
    )
    if near_misses:
        summary += f"\n\nNear-misses (name match, type differs):\n" + "\n".join(f"  {nm}" for nm in near_misses[:20])

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    client = AsyncOpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")

    run_id = f"full_pipeline_{datetime.now().strftime('%m%d_%H%M')}"
    output_dir = Path("tests/orrery_runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy samples
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(exist_ok=True)
    for doc_name in SAMPLE_DOCS:
        src = ORRERY_TEST_DOCS / doc_name
        if src.exists():
            shutil.copy(src, samples_dir / doc_name)

    print(f"Run: {run_id}")
    print(f"Extraction model: {MODEL}")
    print(f"Judge model: {JUDGE_MODEL}")
    print(f"Output: {output_dir}\n")

    # Save config
    (output_dir / "config.json").write_text(json.dumps({
        "model": MODEL, "judge_model": JUDGE_MODEL,
        "phase1_iterations": PHASE1_ITERATIONS, "phase2_iterations": PHASE2_ITERATIONS,
        "timestamp": datetime.now().isoformat(),
    }, indent=2))

    # =================================================================
    # PHASE 1: Golden Set
    # =================================================================
    phase1_dir = output_dir / "phase1_golden"
    phase1_dir.mkdir(exist_ok=True)

    print(f"{'='*60}")
    print("PHASE 1: Golden Set (taxonomy + reference entities)")
    print(f"{'='*60}")

    # Step 1: Open extraction
    print("\nOpen extraction (10 docs)...")
    all_extractions = []
    for i, doc_name in enumerate(SAMPLE_DOCS):
        doc_path = samples_dir / doc_name
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding="utf-8")[:3000]
        print(f"  [{i+1}/10] {doc_name}...", end=" ", flush=True)
        result = await call_model(client, MODEL, EXTRACT_SYSTEM,
                                  EXTRACT_PROMPT.format(doc=content))
        all_extractions.append(f"=== {doc_name} ===\n{result}")
        print(f"({len(result)} chars)")

    evidence_base = "\n\n".join(all_extractions)
    (phase1_dir / "evidence_base.md").write_text(evidence_base)

    # Condense evidence
    print("Condensing evidence...", end=" ", flush=True)
    evidence_condensed = await call_model(
        client, MODEL,
        "Summarize extraction results by category. Do not use extended thinking. Respond directly.",
        f"Extractions from {len(SAMPLE_DOCS)} documents:\n\n{evidence_base[:12000]}\n\n"
        "Group all found items by category (PEOPLE, COMPANIES, SOFTWARE, MONEY, DATES, CONCEPTS, ROLES, etc). "
        "Be comprehensive — include everything.",
        temperature=0.1,
    )
    (phase1_dir / "evidence_condensed.md").write_text(evidence_condensed)
    print(f"({len(evidence_condensed)} chars)")

    # Step 2: Iterative refinement
    current_golden = SEED_GOLDEN_SET
    best_golden = current_golden
    best_composite = 0.0
    trajectory = []

    for iteration in range(PHASE1_ITERATIONS + 1):
        print(f"\n--- Phase 1, Iteration {iteration} ---")

        # Judge
        print("  Judge...", end=" ", flush=True)
        judge_result = await call_model(
            client, JUDGE_MODEL, PHASE1_JUDGE_SYSTEM,
            PHASE1_JUDGE_PROMPT.format(
                iteration=iteration, golden_set=current_golden,
                n_docs=len(SAMPLE_DOCS), evidence=evidence_condensed,
            ),
        )
        (phase1_dir / f"iteration-{iteration}-judgment.md").write_text(judge_result)

        scores, composite = parse_scores(judge_result)
        asi = extract_asi(judge_result)
        regressed = composite < best_composite and iteration > 0

        if composite >= best_composite:
            best_composite = composite
            best_golden = current_golden

        trajectory.append({"iteration": iteration, "scores": scores,
                           "composite": composite, "regressed": regressed})
        print(f"{composite}/10 {'REGRESSION' if regressed else ''}")

        (phase1_dir / f"iteration-{iteration}-candidate.md").write_text(current_golden)

        # Generator
        if iteration < PHASE1_ITERATIONS:
            print("  Generator...", end=" ", flush=True)
            gen_input = best_golden if regressed else current_golden
            current_golden = await call_model(
                client, MODEL, PHASE1_GEN_SYSTEM,
                PHASE1_GEN_PROMPT.format(golden_set=gen_input, composite=composite,
                                         asi=asi, evidence=evidence_condensed),
                temperature=0.3, max_tokens=16384,
            )
            print(f"({len(current_golden)} chars)")

    print(f"\nPhase 1 best: {best_composite}/10")
    (phase1_dir / "best_golden_set.md").write_text(best_golden)

    # Extract golden entities for Phase 2
    golden_entities = parse_golden_entities(best_golden)
    print(f"Golden set: {len(golden_entities)} reference entities")

    if not golden_entities:
        print("WARNING: No entities parsed from golden set. Phase 2 may not work well.")

    # =================================================================
    # PHASE 2: Extraction Spec
    # =================================================================
    phase2_dir = output_dir / "phase2_spec"
    phase2_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print("PHASE 2: Extraction Spec (with evaluator)")
    print(f"{'='*60}")

    # Seed: the golden set itself becomes the starting extraction prompt
    current_spec = best_golden
    best_spec = current_spec
    best_spec_composite = 0.0
    golden_summary = best_golden[:2000]
    spec_trajectory = []

    for iteration in range(PHASE2_ITERATIONS + 1):
        print(f"\n--- Phase 2, Iteration {iteration} ---")

        # Evaluator: run spec against all docs
        print("  Evaluator...", end=" ", flush=True)
        eval_dir = phase2_dir / f"eval-{iteration}"
        eval_results = await run_evaluator(
            client, current_spec, samples_dir, golden_entities, eval_dir)
        (phase2_dir / f"iteration-{iteration}-eval.md").write_text(eval_results)
        # Extract key metrics for display
        recall_match = re.search(r"Recall: (\d+%)", eval_results)
        print(f"{recall_match.group(1) if recall_match else '?'} recall")

        # Judge
        print("  Judge...", end=" ", flush=True)
        judge_result = await call_model(
            client, JUDGE_MODEL, PHASE2_JUDGE_SYSTEM,
            PHASE2_JUDGE_PROMPT.format(
                iteration=iteration, n_docs=len(SAMPLE_DOCS),
                spec=current_spec[:3000], eval_results=eval_results,
                golden_set_summary=golden_summary,
            ),
        )
        (phase2_dir / f"iteration-{iteration}-judgment.md").write_text(judge_result)

        scores, composite = parse_scores(judge_result)
        asi = extract_asi(judge_result)
        regressed = composite < best_spec_composite and iteration > 0

        if composite >= best_spec_composite:
            best_spec_composite = composite
            best_spec = current_spec

        spec_trajectory.append({"iteration": iteration, "scores": scores,
                                "composite": composite, "regressed": regressed})
        print(f"{composite}/10 {'REGRESSION' if regressed else ''}")

        (phase2_dir / f"iteration-{iteration}-candidate.md").write_text(current_spec)

        # Generator
        if iteration < PHASE2_ITERATIONS:
            print("  Generator...", end=" ", flush=True)
            gen_input = best_spec if regressed else current_spec
            current_spec = await call_model(
                client, MODEL, PHASE2_GEN_SYSTEM,
                PHASE2_GEN_PROMPT.format(
                    spec=gen_input, composite=composite,
                    eval_results=eval_results[:3000], asi=asi,
                ),
                temperature=0.3, max_tokens=16384,
            )
            print(f"({len(current_spec)} chars)")

    # =================================================================
    # Results
    # =================================================================
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")

    print(f"\nPhase 1 (Golden Set): best {best_composite}/10")
    for r in trajectory:
        print(f"  iter {r['iteration']}: {r['composite']}/10 {'REGR' if r['regressed'] else ''}")

    print(f"\nPhase 2 (Extraction Spec): best {best_spec_composite}/10")
    for r in spec_trajectory:
        print(f"  iter {r['iteration']}: {r['composite']}/10 {'REGR' if r['regressed'] else ''}")

    print(f"\nGolden set entities: {len(golden_entities)}")
    print(f"\nBest extraction spec ({len(best_spec)} chars):")
    print(best_spec[:1000])

    (phase2_dir / "best_spec.md").write_text(best_spec)
    (output_dir / "summary.json").write_text(json.dumps({
        "phase1_trajectory": trajectory,
        "phase1_best_composite": best_composite,
        "phase1_golden_entities": len(golden_entities),
        "phase2_trajectory": spec_trajectory,
        "phase2_best_composite": best_spec_composite,
        "best_spec_length": len(best_spec),
    }, indent=2))

    print(f"\nAll results saved to {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
