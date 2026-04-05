# Local Model Pipeline Guide

How to run simmer-sdk with local models via Ollama. Includes the actual prompts, step-by-step pipeline composition, and the decisions behind them.

## Quick Start

```bash
# Install Ollama and pull models
ollama pull gemma4:26b   # MoE, 4B active — judge/generator/synthesis
ollama pull gemma4:e4b   # 8B dense — extraction

# Simple creative writing (standard refine() works as-is)
```

```python
from simmer_sdk import refine

result = await refine(
    artifact="A one-shot DND adventure hook...",
    criteria={"tension": "escalating stakes", "agency": "player choices matter"},
    api_provider="ollama",
    generator_model="gemma4:26b",
    judge_model="gemma4:26b",
    clerk_model="gemma4:26b",
    iterations=3,
)
```

For **corpus-based tasks** (entity extraction, spec refinement), the standard `refine()` loop isn't enough — local models need the workflow decomposed. The rest of this guide shows how.

## Why Decomposition Is Needed

Cloud models (Sonnet) can do this in one call:
> "Here are 10 documents. Read them. Evaluate this taxonomy. Score it. Tell me what to fix."

Local models (8B-31B) skip steps. They'll score without reading, or read 3 docs and ignore 7. The quality isn't the issue — when they DO read docs, they produce good analysis. The issue is **reliably getting them to do each step**.

The fix: break each step into its own call where the model does ONE thing.

## Models Tested

| Model | Params | Active | Size | Best For |
|-------|--------|--------|------|----------|
| `gemma4:31b` | 31B dense | 31B | 19GB | Tool use, complex reasoning |
| `gemma4:26b` | 26B MoE | 4B | 17GB | Judging (with evidence), generation, synthesis |
| `gemma4:e4b` | 8B dense | 4B | 9.6GB | Extraction, instruction following |

**Key finding:** For extraction, smaller dense models (e4b) outperform larger MoE (26b). Dense params follow structured prompts more reliably. The 26b MoE returned 0 entities for 5/10 docs; the e4b extracted from all 10.

## Model Parameters

For structured/analytical tasks, use low temperature and disable thinking:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

response = await client.chat.completions.create(
    model="gemma4:26b",
    messages=[
        {"role": "system", "content": "You are an analyst. Do not use extended thinking. Respond directly."},
        {"role": "user", "content": prompt},
    ],
    max_tokens=4096,
    temperature=0.15,  # Near-deterministic
    top_p=0.85,
)
```

**System prompt placement matters.** Behavioral rules ("do not use extended thinking") go in the system message. Task details go in the user message. Local models comply with system-level instructions more reliably.

## The Pipeline: Entity Extraction Example

This mirrors the Noospheric Orrery's `simmer_general.py`. Full working code in `tests/orrery_full_pipeline.py`.

### Step 0: Setup

```python
from pathlib import Path
from openai import AsyncOpenAI

client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
sample_docs = list(Path("samples/").glob("*.md"))
```

### Step 1: Open Extraction (run once, reuse every iteration)

The first step discovers what's in your corpus WITHOUT any predefined taxonomy. This prevents the model from anchoring to existing categories and missing things that don't fit.

**System prompt:**
```
You are a knowledge graph analyst. Extract everything of value from documents.
Do not use extended thinking. Respond directly.
```

**User prompt (per document):**
```
Read this document and extract EVERYTHING that a knowledge graph would want to capture.

Do not use any predefined categories. Just find what's there.

DOCUMENT:
{doc_content}

For each item found, report:
- NAME: the exact text
- WHAT IT IS: describe it in plain language (a person, a company, a dollar amount,
  a software tool, a concept, a date, etc.)
- WHY IT MATTERS: what role does it play in this document?

Be exhaustive. Extract names, organizations, tools, money, dates, concepts,
relationships, roles — anything specific and meaningful. Skip generic words.
```

Run this against each document independently:

```python
all_extractions = []
for doc_path in sample_docs:
    content = doc_path.read_text()[:3000]
    result = await call_model(client, "gemma4:26b", system, prompt.format(doc_content=content))
    all_extractions.append(f"=== {doc_path.name} ===\n{result}")

evidence_base = "\n\n".join(all_extractions)
```

**Why per-doc and not all at once?** The model focuses on one document at a time. In a single call with 10 docs, it skims. In 10 separate calls, it's thorough — finding 30-50 entities per doc vs 10-15 when batched.

### Step 2: Condense the Evidence

Summarize all per-doc findings into categories. This becomes the reusable evidence base.

**Prompt:**
```
Here are entity extractions from {n} documents:

{evidence_base}

Group all found items by category:
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

Be comprehensive. Include everything found.
```

### Step 3: Judge (per iteration)

Compare the current taxonomy against the condensed evidence. This is a lightweight text-in-text-out call — no tool use needed.

**System prompt:**
```
You are a data architect evaluating taxonomy fitness against real corpus data.
Be precise and critical. Do not use extended thinking. Respond directly.
```

**User prompt:**
```
Here is an entity taxonomy (iteration {N}):

{current_taxonomy}

Here is what was actually found in a corpus of {n_docs} meeting notes:

{condensed_evidence}

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
[single most impactful change]
```

**What this produces (real output, seed taxonomy scored by gemma4:26b):**
```
- COVERED: PEOPLE → Person
- COVERED: COMPANIES → Organization
- PARTIALLY COVERED: SOFTWARE/TOOLS → Thing (loses distinction between physical and digital)
- NOT COVERED: DOLLAR AMOUNTS → no appropriate type exists
- NOT COVERED: BUSINESS PROCESSES → no appropriate type exists
- NOT COVERED: ROLES/TITLES → no appropriate type exists

coverage: 4/10
precision: 5/10
taxonomy_quality: 5/10
COMPOSITE: 4.7/10

ASI: Split "Thing" into "Artifact" (Digital/Software) and "Physical Object,"
and introduce a "Value/Quantity" type.
```

### Step 4: Generator (per iteration)

Takes the current taxonomy + ASI + condensed evidence and produces an improved version.

**System prompt:**
```
You are a golden set designer. Output ONLY the improved golden set — no commentary.
The golden set must contain:
1. An entity type taxonomy (the categories with descriptions)
2. A JSON array of EVERY entity found in the sample documents
Do not use extended thinking. Respond directly.
```

**User prompt:**
```
Current golden set:

{current_taxonomy}

Score: {composite}/10

ASI (improvement direction):
{asi}

Here is what was found across the sample documents (use this to populate the entity list):
{condensed_evidence}

Produce an improved golden set. You may:
- Add/remove/rename entity types
- Add disambiguation rules
- Add/remove/correct entities in the reference list
- Fix entity type assignments

The reference entity list MUST be a JSON array: [{"name": "...", "type": "..."}]
Every entity must actually appear in the sample documents.
```

**Key:** The generator gets the condensed evidence so it can compile the entity list. Without this, it asks for documents or produces an empty list.

### Step 5: Repeat Steps 3-4

Each iteration: judge scores the new taxonomy against the same evidence → ASI → generator improves → repeat.

**Results (gemma4:26b, 3 iterations):** 2.0/10 → 8.5/10 → 8.7/10 → 8.8/10. Produced 9 domain-specific types with 49 reference entities.

### Step 6: Phase 2 — Build the Extraction Spec

Phase 1 produced the golden set (what to extract). Phase 2 builds a prompt that a model can actually execute to extract those entities.

The critical difference: **Phase 2 has an evaluator.** Each iteration, we run the spec against the docs and measure real precision/recall.

**Evaluator flow (per iteration):**

```python
for doc_path in sample_docs:
    # Run extraction model with the candidate spec
    raw_output = await call_model(
        client, "gemma4:e4b",  # Small model does extraction
        system="You are an entity extraction system. Output valid JSON arrays only.",
        user=f"{spec}\n\nTEXT:\n{doc_text}\n\nRespond with JSON only: [...]",
        temperature=0.1,
    )
    entities = parse_json(raw_output)

    # Diff against golden set
    hits = extracted & golden_set
    false_positives = extracted - golden_set
```

**Judge prompt for Phase 2 (gets evaluator results):**
```
Iteration {N} extraction spec was tested against {n_docs} documents.

THE SPEC:
{current_spec}

EVALUATOR RESULTS:
{eval_summary}

GOLDEN SET (ground truth):
{golden_set_summary}

Score based on the ACTUAL extraction results, not what the spec looks like:
- coverage: [N]/10 — what fraction of golden set entities were extracted?
- precision: [N]/10 — what fraction of extracted entities are correct?
- format_compliance: [N]/10 — is the JSON output valid and consistent?
COMPOSITE: [N.N]/10

ASI (highest-leverage direction):
[single most impactful change to the spec to improve extraction results]
```

**Generator prompt for Phase 2:**
```
Current extraction spec:

{current_spec}

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

The spec must produce output as: [{"name": "...", "type": "..."}]
```

**Results (gemma4:26b judge, gemma4:e4b extraction, 3 iterations):** 4.6/10 → 7.3/10. Best iteration: 23% precision, 106% recall across 10 docs.

## Decisions and Why

### Why open extraction instead of taxonomy-anchored analysis?

When you give the model a taxonomy and say "find entities that match these types," it anchors. It finds Persons and Organizations (they match) and shoves everything else into "Topic" or "Thing." It doesn't discover that your corpus needs a "Monetary Value" type because it was never looking for one.

Open extraction with no taxonomy finds everything first. The taxonomy comparison happens in a separate call where the model can see the gap.

### Why per-doc calls instead of batching?

We tested both. In a single call with "read all 10 docs," the 26B read 3 (the first 3 alphabetically) and scored based on those. In 10 per-doc calls, it extracted 30-50 entities per doc. The per-doc approach is more expensive (10 calls vs 1) but produces 3-5x more evidence.

### Why e4b for extraction instead of 26B?

The 26B MoE (4B active) returned 0 entities for 5 out of 10 docs — inconsistently following the extraction prompt. The e4b (8B dense) extracted from all 10 docs with higher precision. Dense parameters follow structured instructions more reliably than sparse for this task.

### Why format-gating for investigation?

When the judge prompt says "read the sample docs before scoring," local models skip it and score abstractly. When the output FORMAT requires `<investigation>` and `<evidence>` sections, the model fills them because it's a format rule, not a behavioral suggestion.

Local models follow **format rules** reliably but **behavioral suggestions** poorly.

### Why condense the evidence?

The raw per-doc extractions total ~50KB across 10 docs. That's too large to pass to the judge in one prompt. The condensation step summarizes into ~3-4KB of structured categories that fit in a single call.

## Tradeoffs vs Cloud

| | Cloud (Sonnet) | Local (26B/e4b) |
|---|---|---|
| Investigation | Reads docs in one call | Needs pre-computed evidence |
| Mental simulation | Can simulate extraction | Needs actual evaluator |
| Format compliance | Follows any format | Needs explicit format-gating |
| Speed per iteration | ~30s (API latency) | ~1-5 min (inference) |
| Cost | ~$0.50-1.00/iteration | $0 (electricity only) |
| Setup complexity | API key | Ollama + model pulls + pipeline script |

## Test Results Summary

### Creative Writing (standard `refine()` works)

| Config | Best Score | Trajectory |
|--------|-----------|------------|
| gemma4:31b single judge | 9.3 | 7.7 → 8.3 → 9.3 |
| gemma4:31b board (2 judges) | 9.3 | 8.7 → 9.3 → 8.7 |
| gemma4:26b single judge | 7.7 | 6.3 → 7.3 → 7.7 |
| gemma4:e4b single judge | 9.0 | 7.3 → 8.3 → 9.0 |

### Orrery Entity Extraction (decomposed pipeline)

| Phase | Model(s) | Best Score | Entities |
|-------|----------|-----------|----------|
| Phase 1 golden set | 26b all | 8.8/10 | 49 reference entities |
| Phase 2 spec | 26b judge + e4b extract | 7.3/10 | 23% precision, 106% recall |

## Files

| File | What It Is |
|------|-----------|
| `tests/orrery_full_pipeline.py` | Complete Phase 1 + Phase 2 reference pipeline |
| `tests/evaluate_spec.py` | Standalone evaluator (runs extraction, diffs against golden set) |
| `tests/orrery_golden_set.py` | Phase 1 only, using simmer-sdk's `refine()` |
| `tests/smoke_ollama.py` | Basic connectivity and format compliance tests |
| `src/simmer_sdk/local_agent.py` | Tool-calling agent loop for Ollama |
| `src/simmer_sdk/client.py` | Ollama provider, `extract_text()` for reasoning models |
| `src/simmer_sdk/prompts.py` | `LOCAL_JUDGE_PREAMBLE` for format-gated investigation |
| `docs/local-models-guide.md` | This file |
