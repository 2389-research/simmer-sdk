"""Spec evaluator for local model testing — matches orrery's evaluate_spec.py design.

Runs a candidate extraction spec against sample documents using a local model,
diffs results against the golden set, writes raw outputs, prints summary.

Designed to be called as a simmer-sdk evaluator:
    evaluator="uv run python tests/evaluate_spec.py --candidate {candidate_path} --samples-dir /path/to/samples --golden-set /path/to/golden.md --output-dir {output_dir} --iteration {iteration}"

Also callable standalone for testing.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path


def parse_golden_set(text: str) -> list[tuple[str, str]]:
    """Parse golden set into (name, type) tuples.

    Handles:
    - JSON: {"name": "...", "type": "..."}
    - Taxonomy lines: - TypeName — description
    """
    entities = []

    # Try JSON objects
    for m in re.finditer(r'\{"name":\s*"([^"]+)",\s*"type":\s*"([^"]+)"\}', text):
        entities.append((m.group(1).lower().strip(), m.group(2).strip()))

    if entities:
        return entities

    # Fall back to taxonomy lines — extract type names as expected types
    for m in re.finditer(r'^-\s+(\w[\w/\s]*?)\s*—', text, re.MULTILINE):
        entities.append(("__type__", m.group(1).strip()))

    return entities


def parse_extraction_output(text: str) -> list[dict]:
    """Parse model extraction output into entity dicts."""
    entities = []

    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    # Try JSON array
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [{"name": e.get("name", "").lower().strip(), "type": e.get("type", "")} for e in data if isinstance(e, dict)]
        if isinstance(data, dict) and "entities" in data:
            return [{"name": e.get("name", "").lower().strip(), "type": e.get("type", "")} for e in data["entities"] if isinstance(e, dict)]
    except json.JSONDecodeError:
        pass

    # Try JSONL (one object per line)
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


async def run_extraction(spec_text: str, doc_text: str, model: str, ollama_url: str) -> str:
    """Run extraction spec against a document using local model."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=f"{ollama_url}/v1", api_key="ollama")

    prompt = f"""{spec_text}

TEXT:
{doc_text}

Respond with JSON only. Output a JSON array of extracted entities:
[{{"name": "entity name", "type": "EntityType"}}, ...]

If no entities found, output: []"""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an entity extraction system. Output valid JSON arrays only. No commentary. Do not use extended thinking. Respond directly."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.1,
        top_p=0.85,
    )
    return response.choices[0].message.content or "[]"


def diff_entities(extracted: list[dict], golden_types: list[str]) -> dict:
    """Compare extracted entities against expected golden set types.

    Since the golden set defines types (not specific entity instances),
    we check: does the extraction produce entities for each expected type?
    """
    extracted_types = set()
    for e in extracted:
        extracted_types.add(e.get("type", "").strip())

    golden_type_set = set(golden_types)

    type_hits = extracted_types & golden_type_set
    type_misses = golden_type_set - extracted_types
    unexpected_types = extracted_types - golden_type_set

    return {
        "total_extracted": len(extracted),
        "unique_types_extracted": sorted(extracted_types),
        "type_hits": sorted(type_hits),
        "type_misses": sorted(type_misses),
        "unexpected_types": sorted(unexpected_types),
        "entities": extracted,
    }


async def evaluate(
    candidate_path: str,
    samples_dir: str,
    golden_set_path: str,
    output_dir: str,
    iteration: int,
    model: str = "gemma4:26b",
    ollama_url: str = "http://localhost:11434",
):
    """Run full evaluation: extract from each doc, diff, report."""

    spec_text = Path(candidate_path).read_text(encoding="utf-8")
    golden_text = Path(golden_set_path).read_text(encoding="utf-8")

    # Parse golden set to get expected entity types
    golden_types = []
    for m in re.finditer(r'^-\s+([\w/\s]+?)\s*—', golden_text, re.MULTILINE):
        golden_types.append(m.group(1).strip())

    if not golden_types:
        # Fallback: try to extract type names from the candidate spec itself
        for m in re.finditer(r'^-\s+([\w/\s]+?)\s*—', spec_text, re.MULTILINE):
            golden_types.append(m.group(1).strip())

    # Setup eval output dir
    eval_dir = Path(output_dir) / f"eval-{iteration}"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Process each sample doc
    sample_path = Path(samples_dir)
    docs = sorted(sample_path.glob("*.md")) + sorted(sample_path.glob("*.txt"))

    all_results = []
    total_extracted = 0
    total_type_hits = 0
    total_type_checks = 0

    for doc_path in docs:
        doc_text = doc_path.read_text(encoding="utf-8")[:3000]
        raw_output = await run_extraction(spec_text, doc_text, model, ollama_url)

        # Parse and diff
        entities = parse_extraction_output(raw_output)
        diff = diff_entities(entities, golden_types)

        # Save raw output
        raw_file = eval_dir / f"{doc_path.stem}.json"
        raw_file.write_text(json.dumps({
            "doc": doc_path.name,
            "raw_output": raw_output,
            "parsed_entities": entities,
            "diff": diff,
        }, indent=2))

        all_results.append((doc_path.name, diff))
        total_extracted += diff["total_extracted"]
        total_type_hits += len(diff["type_hits"])
        total_type_checks += len(golden_types)

    # Compute aggregate metrics
    type_recall = total_type_hits / total_type_checks if total_type_checks > 0 else 0

    # Collect all unique extracted types and missed types across docs
    all_extracted_types = set()
    all_missed_types = set()
    all_unexpected_types = set()
    for _, diff in all_results:
        all_extracted_types.update(diff["unique_types_extracted"])
        all_missed_types.update(diff["type_misses"])
        all_unexpected_types.update(diff["unexpected_types"])

    # Print summary (captured by simmer-sdk as evaluator_output)
    print(f"=== Spec Evaluation — Iteration {iteration} ===")
    print()
    print(f"Golden set types: {golden_types}")
    print(f"Type recall (avg across docs): {type_recall:.0%}")
    print(f"Total entities extracted: {total_extracted} across {len(docs)} docs")
    print(f"Types found across corpus: {sorted(all_extracted_types)}")
    print(f"Types consistently missed: {sorted(all_missed_types)}")
    print(f"Unexpected types: {sorted(all_unexpected_types)}")
    print()
    print("--- Per-doc breakdown ---")
    for doc_name, diff in all_results:
        print(f"  {doc_name}: extracted={diff['total_extracted']}, "
              f"types_hit={diff['type_hits']}, "
              f"types_missed={diff['type_misses']}, "
              f"unexpected={diff['unexpected_types']}")
    print()
    print(f"--- Raw outputs ---")
    print(f"Read full extraction results at: {eval_dir}/")
    print(f"Files: {[f'{d.stem}.json' for d, _ in zip(docs, all_results)]}")


def main():
    parser = argparse.ArgumentParser(description="Spec evaluator for local model testing")
    parser.add_argument("--candidate", required=True, help="Path to candidate spec file")
    parser.add_argument("--samples-dir", required=True, help="Directory with sample documents")
    parser.add_argument("--golden-set", required=True, help="Path to golden set file")
    parser.add_argument("--output-dir", required=True, help="Simmer output directory")
    parser.add_argument("--iteration", type=int, required=True, help="Current iteration number")
    parser.add_argument("--model", default="gemma4:26b", help="Extraction model")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    args = parser.parse_args()

    asyncio.run(evaluate(
        candidate_path=args.candidate,
        samples_dir=args.samples_dir,
        golden_set_path=args.golden_set,
        output_dir=args.output_dir,
        iteration=args.iteration,
        model=args.model,
        ollama_url=args.ollama_url,
    ))


if __name__ == "__main__":
    main()
