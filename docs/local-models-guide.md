# Local Model Pipeline Guide

Reference implementation and findings for running simmer-sdk with local models via Ollama.

## Overview

The standard simmer-sdk pipeline uses Claude (Sonnet/Haiku) via Anthropic API or Bedrock. This guide documents how to run the full pipeline on local models, what adaptations are needed, and the tradeoffs involved.

**Key finding:** Local models (8B-31B) can run the simmer pipeline effectively, but the workflow needs to be decomposed into smaller, focused steps rather than relying on single large calls. Cloud models reason well in one shot; local models need structured evidence at each step.

## Models Tested

| Model | Params | Active | Size | Best Role |
|-------|--------|--------|------|-----------|
| gemma4:31b | 31B | 31B (dense) | 19GB | Judge (when tool use needed) |
| gemma4:26b | 26B MoE | 4B | 17GB | Judge, generator, synthesis |
| gemma4:e4b | 8B | 4B (dense) | 9.6GB | Extraction, simple generation |

## Architecture Differences from Cloud

### Cloud (Sonnet)
```
Judge gets: spec + sample doc paths + tools
Judge does: reads docs, mentally evaluates, scores, produces ASI
→ One call does investigation + evaluation + scoring
```

### Local Models
```
Phase A: Open extraction (once, upfront)
  → 26B reads each doc independently, extracts everything
  → Produces reusable evidence base

Phase B: Judge gets: spec + pre-computed evidence
  → Scores by comparing spec against evidence
  → No tool use needed, just text-in-text-out
```

**Why:** Local models follow format rules reliably but skip multi-step behavioral instructions (like "read files before scoring"). Breaking investigation into a separate step ensures it actually happens.

### Evaluator (Phase 2)
Cloud judges mentally simulate extraction. Local judges can't do this reliably. Instead, we actually run extraction each iteration and give the judge hard metrics:
```
Each Phase 2 iteration:
  1. Run extraction model against all docs with current spec
  2. Diff results against golden set → precision/recall/F1
  3. Judge sees real numbers + raw outputs → scores + ASI
```

## Reference Pipeline: Orrery Golden Set + Extraction Spec

Full working example in `tests/orrery_full_pipeline.py`. Mirrors the Noospheric Orrery's `simmer_general.py` two-phase approach.

### Phase 1: Golden Set (taxonomy + reference entities)

**Goal:** Determine what entity types exist in the corpus and compile a reference list.

**Flow:**
1. **Open extraction** — 26B analyzes each doc with no predefined taxonomy. Finds everything: people, orgs, tools, money, dates, concepts, roles.
2. **Condense** — Summarize all findings by category across all docs.
3. **Judge** — Compare current taxonomy against condensed evidence. Score coverage/precision/taxonomy_quality.
4. **Generator** — Improve taxonomy based on ASI. Has access to condensed evidence to compile entity list.
5. **Repeat** steps 3-4.

**Output:** Golden set with entity type taxonomy + JSON array of all reference entities found in the corpus.

**Results (gemma4:26b):** Seed 5.0/10 → 8.8/10 in 3 iterations. Discovered 9 domain-specific types (Person, Organization, Concept/Technology, Business/Market Dynamics, Event, Location, Monetary Value, Role/Attribute, Metadata) with 49 reference entities.

### Phase 2: Extraction Spec (with evaluator)

**Goal:** Build a prompt that a model can execute against any document to reliably extract the golden set entities.

**Flow:**
1. **Generator** — Produces/improves extraction spec based on ASI.
2. **Evaluator** — Runs spec against all sample docs using extraction model (e4b). Diffs output against golden set. Produces precision/recall metrics + raw JSON per doc.
3. **Judge** — Sees evaluator metrics + can read raw outputs. Scores coverage/precision/format_compliance based on actual results.
4. **Repeat** steps 1-3.

**Output:** Executable extraction prompt (~3-4KB) with entity definitions, boundary rules, examples, and output format.

**Results (gemma4:26b judge, gemma4:e4b extraction):** Seed 4.6/10 → 7.3/10 in 3 iterations. Best iteration: 23% precision, 106% recall across 10 docs.

## Model Selection Guide

### For extraction (running the spec against docs)
**Use the smallest model that follows instructions.** gemma4:e4b (8B dense) outperformed gemma4:26b (MoE, 4B active) on extraction — higher precision, fewer zero-entity docs. Dense models follow structured prompts more reliably than MoE for this task.

### For judging/synthesis
**Use 26B+ when evidence is provided.** The 26B MoE handles taxonomy comparison and evaluator analysis well when given structured evidence. It struggles when asked to investigate on its own (skips tool use, misspells paths).

**Use 31B when tool use is required.** If the judge needs to read files via tools (Read/Grep/Glob), 31B is reliable. 26B and e4b make execution errors (typos in paths, giving up on errors).

### For generation
**26B works for structured specs.** It follows ASI instructions and produces improved taxonomies. e4b works for creative tasks (DND adventures) but returns change reports instead of artifacts for spec tasks.

## Key Prompt Patterns for Local Models

### Format-gating investigation
Local models skip investigation steps unless investigation is part of the required output format:
```
YOUR OUTPUT MUST FOLLOW THIS FORMAT:

<investigation>
Use tools here. You MUST call glob then read at least 3 files.
</investigation>

<evidence>
Quote specific content from files you read.
</evidence>

<scoring>
ITERATION N SCORES:
  criterion: N/10 — reasoning referencing evidence
</scoring>

A score without <investigation> and <evidence> sections is INVALID.
```

### Tuned parameters for structured output
```python
temperature=0.15   # Near-deterministic for classification
top_p=0.85
# System prompt: "Do not use extended thinking. Respond directly."
```

### System prompt placement
Place behavioral rules in the system prompt, task details in user prompt. Local models comply with system-level instructions more reliably.

## Tradeoffs vs Cloud

| | Cloud (Sonnet) | Local (26B/e4b) |
|---|---|---|
| Investigation | Reads docs in one call | Needs pre-computed evidence |
| Mental simulation | Can simulate extraction | Needs actual evaluator |
| Format compliance | Follows any format | Needs explicit format-gating |
| Speed per iteration | ~30s (API latency) | ~1-5 min (inference) |
| Cost | ~$0.50-1.00/iteration | $0 (electricity only) |
| Setup complexity | API key | Ollama + model pulls + pipeline script |

## Files

| File | Purpose |
|------|---------|
| `src/simmer_sdk/local_agent.py` | Tool-calling agent loop for Ollama (replaces ClaudeSDKClient) |
| `src/simmer_sdk/client.py` | Ollama provider support in create_async_client, get_agent_env |
| `src/simmer_sdk/prompts.py` | LOCAL_JUDGE_PREAMBLE for format-gated investigation |
| `tests/orrery_full_pipeline.py` | Complete Phase 1 + Phase 2 reference pipeline |
| `tests/orrery_golden_set.py` | Phase 1 only, uses simmer-sdk's refine() |
| `tests/evaluate_spec.py` | Standalone evaluator for Phase 2 |
| `tests/smoke_ollama.py` | Basic connectivity and format compliance tests |
| `tests/orrery_runs/` | All test run outputs with configs and trajectories |

## DND Creative Writing Results (for comparison)

The standard simmer loop (`refine()` with `api_provider="ollama"`) works well for creative writing tasks without the multi-stage decomposition:

| Config | Best Score | Trajectory |
|--------|-----------|------------|
| gemma4:31b single judge | 9.3 | 7.7 → 8.3 → 9.3 |
| gemma4:31b board (2 judges) | 9.3 | 8.7 → 9.3 → 8.7 |
| gemma4:26b single judge | 7.7 | 6.3 → 7.3 → 7.7 |
| gemma4:e4b single judge | 9.0 | 7.3 → 8.3 → 9.0 |

Creative writing doesn't need corpus investigation — the candidate text is self-contained. The standard `refine()` flow works as-is for these tasks.
