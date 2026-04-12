# Split Generator Findings: Architect/Executor Pattern for Simmer

Research conducted April 2026 on simmer-sdk. Compares four generator configurations on the same creative writing task (DND adventure hook, 300-500 words, 2 iterations).

## The Pattern

Inspired by [speed-run](https://github.com/2389-research/speed-run), where Claude writes structural contracts and a cheaper model executes them.

In simmer's split generator:
1. **Architect** (Sonnet) reads the current artifact + judge ASI → writes a detailed contract specifying structure, content decisions, names, mechanics
2. **Executor** (cheaper model) takes the contract + current artifact → produces the full new version

The architect makes all architectural decisions. The executor writes prose.

## Configurations Tested

| Config | Generator | Judge | Clerk | Split? |
|--------|-----------|-------|-------|--------|
| All Sonnet | sonnet-4-6 | sonnet-4-6 | sonnet-4-6 | No |
| All Haiku | haiku-4-5 | haiku-4-5 | haiku-4.5 | No |
| Sonnet→Haiku | sonnet architect | sonnet-4-6 | haiku executor | Yes |
| Sonnet→GPT-OSS | sonnet architect | sonnet-4-6 | gpt-oss-120b executor | Yes |

All runs used Bedrock, single judge, same DND adventure task and criteria.

## Score Trajectories

Reminder: scores are internally relative to each run's judge — not comparable across runs. What IS comparable is whether the loop improves.

| Config | Iter 0 | Iter 1 | Iter 2 | Improved? |
|--------|--------|--------|--------|-----------|
| All Sonnet | 7.0 | 7.7 | 8.0 | Yes, every iteration |
| All Haiku | 7.0 | 7.0 | 7.0 | No — flatlined |
| Sonnet→Haiku | 4.3 | 7.3 | — | Yes, +3.0 in one iteration |
| Sonnet→GPT-OSS | 5.3 | 5.3 | 5.3 | No — flatlined |

## Cost Analysis

### Generator cost only (judge/reflect held constant)

| Config | Architect cost | Executor cost | Generator total | Savings vs Sonnet |
|--------|---------------|---------------|-----------------|-------------------|
| All Sonnet | — | ~$0.15 | ~$0.15 | baseline |
| All Haiku | — | ~$0.02 | ~$0.02 | 87% |
| Sonnet→Haiku | ~$0.04 | ~$0.017 | ~$0.057 | 62% |
| Sonnet→GPT-OSS | ~$0.04 | ~$0.003 | ~$0.043 | 71% |

### Cost per successful improvement

This is the metric that matters for pricing — cost per output that actually gets better, not cost per attempt.

| Config | Total run cost | Improvements made | Cost per improvement |
|--------|---------------|-------------------|---------------------|
| All Sonnet | $0.36 | 2 | **$0.18** |
| Sonnet→Haiku | $0.26 | 1 | **$0.26** |
| All Haiku | $0.13 | 0 | ∞ (never improved) |
| Sonnet→GPT-OSS | $0.43 | 0 | ∞ (never improved) |

All-Haiku is cheap per attempt but infinite cost per improvement — it can't iterate on its own output. GPT-OSS produces decent first drafts but can't apply modification contracts to improve iteratively.

## Executor Model Comparison (Same Contract)

We gave the exact same Sonnet-written contract to 5 executor models and compared outputs:

| Model | Params | Output/1M | Followed Structure | Added Creative Value | Quality |
|-------|--------|-----------|-------------------|---------------------|---------|
| **Haiku 4.5** | ? | $4.00 | All sections correct | Yes — atmosphere, detail, expansion | Best |
| **GPT-OSS 120B** | 120B | ~$1.80 | All sections correct | Some — good phrases, clean | Close second |
| **Llama 4 Maverick** | 17B/400B MoE | $0.97 | All sections correct | Minimal — near verbatim from contract | Functional |
| **Nova Lite** | ~20B | $0.24 | Lost structure | None — wrote a flat summary | Poor |
| **Nova Micro** | ~11B | $0.14 | Failed — echoed contract back | N/A — reproduced instructions | Failed |

### Key findings:
- **Nova models** (11-20B) can't reliably separate "instructions for me" from "content I should produce"
- **Llama 4 Maverick** follows contracts faithfully but adds nothing — it's a transcription machine
- **GPT-OSS 120B** follows contracts and adds some creative value — close to Haiku on a single pass
- **Haiku** follows contracts AND expands with atmosphere, detail, and creative additions
- Model size isn't the only factor — GPT-OSS (120B dense) matched Maverick (400B MoE) on contract following but outperformed on creative expansion

## Qualitative Assessment of Best Outputs

### All Sonnet (8.0/10)
**Publishable quality.** Features a ticking clock (6 hours with visible events at hours 2/4/5), three structurally distinct paths (dive for the mayor, expose a merchant conspiracy, shatter a magical anchor with moral consequences), and NPCs with personality (pipe-smoke merchant, tattooed fortune teller). A DM could run this cold tonight with zero prep.

### All Haiku (7.0/10)
**Broken output.** Best candidate was a report about the adventure ("Generated an initial adventure hook featuring...") not the adventure itself. The model returned its summary instead of the artifact. Unusable.

### Sonnet→Haiku (7.3/10)
**Most complete and detailed.** ~3000 words with 5 named dungeon rooms, each with DCs, encounter details, and environmental mechanics. Features a puzzle (Tide Organ with tonal sequence), negotiation scene with specific terms and mechanical levers, and multiple resolution paths with consequences. The contract pattern forced Sonnet to make specific architectural decisions (room layouts, DCs, negotiation clauses) that it wouldn't have bothered with when generating directly. Haiku expanded each into vivid prose. Too long for the 300-500 word target but the most runnable adventure of the four.

### Sonnet→GPT-OSS (5.3/10)
**Solid outline, thin on mechanics.** Correct structure, concrete locations, clear three-outcome resolution. Includes DM pacing notes (Hour 1/2/3) that no other version had. But each location gets one paragraph, NPCs get two sentences, and the climactic confrontation has no DCs or environmental details. A DM would need prep time to fill in the encounter mechanics.

## The Contract Format That Works

The key insight from speed-run: the architect must make ALL structural decisions. Early experiments with vague contracts ("preserve section 1, modify section 2, add section 3") produced no improvement. The format that works:

```
Write a CONTRACT for a less capable model to execute.
You make the architectural decisions — structure, what goes where,
what specific content to include. The executor writes it out.

Your contract should:
- Specify the exact structure (sections, order, approximate length)
- Make every important content decision (names, concepts, specifics)
- State what to preserve from the current version
- State what NOT to do (common mistakes to avoid)

Think of it like writing a detailed ticket for a junior colleague.
They can write well but shouldn't be making design decisions.
```

Example contract (produced by Sonnet for Haiku):
```
### TITLE (1 line)
"The Tithe of Empty Waters"

### SITUATION SUMMARY (3-4 sentences, ~60 words)
Establish: the town of Saltmere, fishing village on a rocky coast. For one
week, nets come up full of bones. Mayor Aldric Voss vanished three days ago.

### KEY NPCS (short list, ~60 words)
- Maren, Harbormaster — pragmatic, hiding guilt (witnessed Voss make the deal)
- Vel, Sea Hag — cunning, contractual, not needlessly cruel

### DO NOT
- Do not invent additional villains
- Do not exceed 500 words
- Do not use the word "eldritch"
```

Sonnet makes every name, plot point, structure, and mechanical decision. The executor writes prose around this skeleton.

## When to Use Each Configuration

| Situation | Recommended Config | Why |
|-----------|--------------------|-----|
| Quality is paramount, budget flexible | All Sonnet | Only config that reliably improves every iteration |
| Budget constrained, simple artifacts | All Haiku | Cheapest per attempt, decent first-pass quality |
| Complex artifacts needing iteration | Sonnet→Haiku split | Sonnet drives architecture, Haiku fills detail at 62% generator savings |
| Very long artifacts (5K+ words) | Sonnet→Haiku or Sonnet→GPT-OSS split | Output token savings compound with length |
| Prototyping / first drafts | All Haiku or GPT-OSS | Cheap, fast, good enough to evaluate direction |

## What Doesn't Work

- **Cheap executors iterating on their own** — Haiku and GPT-OSS flatline when asked to improve without an architect
- **Vague modification contracts** — "preserve/modify/add/remove" format never produced improvement (5.7 → 5.7 → 5.7)
- **Nova models as executors** — too small to separate instructions from output, or lose document structure entirely
- **Llama 4 Maverick as creative executor** — follows contracts but contradicts content decisions or adds nothing beyond verbatim reproduction

## Implementation

Available in simmer-sdk on the `feat/cost-tracking-split-gen` branch:

```python
result = await refine(
    artifact="...",
    criteria={...},
    split_generator=True,                      # Enable architect/executor split
    generator_model="claude-sonnet-4-6",       # Architect
    executor_model="claude-haiku-4-5",         # Executor (defaults to clerk_model)
    judge_model="claude-sonnet-4-6",
    clerk_model="claude-haiku-4-5",
    api_provider="bedrock",
)

# Usage tracking
print(result.usage.summary())
# Run cost breakdown:
#   generator_architect:  3 calls, ... = $0.04
#   generator_executor:   3 calls, ... = $0.02
#   judge:                3 calls, ... = $0.16
#   Total: $0.26
```

Non-Anthropic Bedrock models (Nova, Llama, GPT-OSS) work as executors via the Converse API:

```python
result = await refine(
    ...,
    split_generator=True,
    executor_model="amazon.nova-lite-v1:0",    # Any Bedrock model
)
```

Contracts are saved to `iteration-N-contract.md` in the output directory for inspection.

## Files

| File | Purpose |
|------|---------|
| `src/simmer_sdk/generator.py` | `_split_generate()` — architect/executor two-call pattern |
| `src/simmer_sdk/usage.py` | `UsageTracker` — token/cost tracking with pricing table |
| `src/simmer_sdk/client.py` | `invoke_bedrock_model()` — generic Bedrock Converse API for non-Anthropic models |
| `tests/compare_configs.py` | Three-config comparison runner |
| `tests/executor_comparison/` | Same-contract multi-executor test outputs |
