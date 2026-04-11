# Hybrid Generator: Prompt Reference & Task Decomposition

Complete prompt reference for the hybrid architect/executor pattern. Copy-paste ready for integration into any pipeline.

## The Pattern

A refinement loop where a strong model (Sonnet) drives improvement and a cheap model (Haiku/GPT-OSS/any) handles bulk generation:

```
Iteration 0:  Sonnet architect writes contract → cheap model produces first draft
Iteration 1+: Sonnet reads artifact + judge feedback → makes surgical edits directly
```

The strong model never does bulk generation. It either writes a short contract (iter 0) or makes targeted patches (iter 1+). The expensive output tokens are spent on decisions and edits, not full artifact production.

## Why This Works

- **Cheap models can't iterate on themselves** — Haiku and GPT-OSS flatline when asked to improve their own output across iterations (tested: 0 improvements in 3 iterations)
- **Cheap models follow contracts well** — given specific enough instructions, Haiku produces 80-90% correct first drafts
- **Strong models are efficient editors** — Sonnet's edit calls produce ~1,100 output tokens vs ~3,300 for full generation. 3x fewer expensive tokens.
- **The contract forces better architecture** — when Sonnet has to specify everything for a junior executor, it makes more deliberate structural decisions than when generating directly

## Task Decomposition

### Iteration 0: Contract → Execute

Two calls. The strong model makes all decisions. The cheap model writes it out.

**Call 1 — Architect (strong model, ~1,000 output tokens)**

Reads the task description and criteria. Produces a structural contract.

**Call 2 — Executor (cheap model, ~2,000-4,000 output tokens)**

Reads the contract + task description. Produces the full artifact.

### Iterations 1+: Read → Edit

One call. The strong model reads the current artifact and the judge's feedback, then makes targeted changes.

**Single call — Editor (strong model, ~1,100 output tokens)**

Reads the full artifact + ASI feedback. Outputs the complete artifact with surgical changes applied.

## Exact Prompts

### Iteration 0, Call 1: Architect Prompt

Sent to the **strong model** (e.g., Sonnet 4.6).

```
You are the architect in a simmer refinement loop (iteration 0).

CURRENT ARTIFACT:
{current_candidate}

ASI (single most impactful improvement):
{asi}

ORIGINAL DESCRIPTION:
{original_description}

Write a CONTRACT for a less capable model to execute. You make the
architectural decisions — structure, what goes where, what specific
content to include. The executor writes it out.

Your contract should:
- Specify the exact structure (sections, order, approximate length)
- Make every important content decision (names, concepts, specifics)
- State what to preserve from the current version
- State what NOT to do (common mistakes to avoid)

Think of it like writing a detailed ticket for a junior colleague.
They can write well but shouldn't be making design decisions.
```

**What the strong model produces (example):**

```markdown
# CONTRACT: Coastal Town Adventure Hook

## OVERVIEW
Write a one-shot D&D 5e adventure hook called "The Tithe of Empty Waters"
for 4 level-5 characters. Tone: gothic mystery with nautical horror.

## SECTIONS — IN THIS ORDER

### 1. TITLE + TAGLINE (1 line)
Title: "The Tithe of Empty Waters"
Tagline: "The sea has started sending things back."

### 2. SITUATION (60-80 words)
Establish these facts in flowing prose:
- Town: Saltmere, fishing village, ~400 people
- For one week, nets return only bones
- Mayor Aldric Voss disappeared three days ago
- Harbormaster Maren hired the party

### 3. THREE ACT STRUCTURE (~50-60 words each)
Scene 1 — Crestholm Docks: investigation/social, clues from fishermen
Scene 2 — The Drowned Altar: exploration/puzzle, flooded ruin
Scene 3 — Vel's Bargain: roleplay/combat, negotiation with sea hag

### KEY NPCS
- Maren, Harbormaster — pragmatic, hiding guilt
- Aldric Voss, Mayor — ashamed, not evil
- Vel, Sea Hag — cunning, contractual

### DO NOT
- Do not invent additional villains
- Do not exceed 500 words
- Do not add boxed read-aloud text
```

The architect decides every name, every plot point, every structural element. The executor gets zero creative latitude on architecture.

### Iteration 0, Call 2: Executor Prompt

Sent to the **cheap model** (e.g., Haiku 4.5, GPT-OSS 120B).

```
You are a writer executing a contract. The contract specifies the
STRUCTURE, CONTENT, and RULES. Your job is to write excellent prose
that follows the contract exactly. Do not make structural decisions —
those are decided for you.

CURRENT ARTIFACT (reference for style and any preserved content):
{current_candidate}

CONTRACT (follow exactly — every name, plot point, and structure
is specified):
{contract}

Output ONLY the complete artifact. No commentary, no explanations.
```

### Iterations 1+: Direct Edit Prompt

Sent to the **strong model** (e.g., Sonnet 4.6). This is the surgical edit call.

```
You are improving an artifact based on judge feedback (iteration {N}).

CURRENT ARTIFACT:
{current_candidate}

JUDGE FEEDBACK (ASI — single most impactful improvement):
{asi}

ORIGINAL DESCRIPTION:
{original_description}

Make SURGICAL changes to address the ASI feedback. Do not rewrite
from scratch. Preserve everything that works. Add, modify, or
restructure only what the ASI identifies as the highest-leverage
improvement.

Output the COMPLETE improved artifact — not a diff, not commentary.
```

If the previous iteration regressed, an additional block is prepended:

```
REGRESSION NOTE:
{regression_note}
```

## Model Configuration

### What we tested

| Role | Model | Cost (output/1M) |
|------|-------|-------------------|
| Architect (iter 0) | Claude Sonnet 4.6 | $15.00 |
| Executor (iter 0) | Claude Haiku 4.5 | $4.00 |
| Executor (iter 0) | GPT-OSS 120B | ~$1.80 |
| Editor (iter 1+) | Claude Sonnet 4.6 | $15.00 |
| Judge | Claude Sonnet 4.6 | $15.00 |

### Results

| Config | Trajectory | Improved? | Gen Cost |
|--------|-----------|-----------|----------|
| All Sonnet (baseline) | 7.0 → 7.7 → 8.0 | +2 iters | ~$0.15 |
| Hybrid Haiku | 5.3 → 7.0 → 7.0 | +1 iter | ~$0.06 |
| Hybrid GPT-OSS | 5.3 → 6.3 → 7.3 | +2 iters | ~$0.06 |
| All Haiku (no architect) | 7.0 → 7.0 → 7.0 | 0 | ~$0.02 |

Scores are internal to each run (different seeds, same judge model). The comparable metric is whether the loop improved.

### Executor model selection

For the executor (iter 0), the model needs to:
1. Follow structural contracts without going off-script
2. Not leak contract instructions into the output
3. Produce substantive prose, not just echo the contract

**What works:** Haiku 4.5, GPT-OSS 120B

**What doesn't:** Nova Micro (echoes contract back), Nova Lite (loses structure), Llama 4 Maverick (contradicts contract decisions)

## Integration Example

### With simmer-sdk

```python
from simmer_sdk import refine

result = await refine(
    artifact="...",
    criteria={...},
    split_generator=True,
    split_generator_mode="hybrid",     # iter 0 = contract, iter 1+ = direct edit
    generator_model="claude-sonnet-4-6",  # architect + editor
    executor_model="claude-haiku-4-5",    # cheap first draft
    judge_model="claude-sonnet-4-6",
    clerk_model="claude-haiku-4-5",
    api_provider="bedrock",
    # ... aws creds ...
)
```

### Without simmer-sdk (standalone implementation)

```python
async def hybrid_generate(
    task: str,
    criteria: dict,
    current_artifact: str,
    asi: str,
    iteration: int,
    strong_model: str,
    cheap_model: str,
    client,  # Anthropic or Bedrock client
):
    if iteration == 0:
        # Step 1: Architect contract
        contract = await client.messages.create(
            model=strong_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": f"""
You are the architect in a refinement loop (iteration 0).

CURRENT ARTIFACT:
{current_artifact}

ASI (single most impactful improvement):
{asi}

Write a CONTRACT for a less capable model to execute. You make the
architectural decisions — structure, what goes where, what specific
content to include. The executor writes it out.

Your contract should:
- Specify the exact structure (sections, order, approximate length)
- Make every important content decision (names, concepts, specifics)
- State what to preserve from the current version
- State what NOT to do (common mistakes to avoid)

Think of it like writing a detailed ticket for a junior colleague.
They can write well but shouldn't be making design decisions.
"""}],
        )
        contract_text = contract.content[0].text

        # Step 2: Executor produces artifact
        result = await client.messages.create(
            model=cheap_model,
            max_tokens=16384,
            messages=[{"role": "user", "content": f"""
You are a writer executing a contract. The contract specifies the
STRUCTURE, CONTENT, and RULES. Your job is to write excellent prose
that follows the contract exactly. Do not make structural decisions —
those are decided for you.

CURRENT ARTIFACT (reference for style and any preserved content):
{current_artifact}

CONTRACT (follow exactly):
{contract_text}

Output ONLY the complete artifact. No commentary, no explanations.
"""}],
        )
        return result.content[0].text

    else:
        # Iterations 1+: Sonnet direct surgical edit
        result = await client.messages.create(
            model=strong_model,
            max_tokens=16384,
            messages=[{"role": "user", "content": f"""
You are improving an artifact based on judge feedback (iteration {iteration}).

CURRENT ARTIFACT:
{current_artifact}

JUDGE FEEDBACK (ASI — single most impactful improvement):
{asi}

Make SURGICAL changes to address the ASI feedback. Do not rewrite
from scratch. Preserve everything that works. Add, modify, or
restructure only what the ASI identifies as the highest-leverage
improvement.

Output the COMPLETE improved artifact — not a diff, not commentary.
"""}],
        )
        return result.content[0].text
```

## Cost Model

For a 2-iteration run (seed + 2 improvements):

```
Iteration 0:
  Architect (Sonnet):  ~325 input tokens, ~1,000 output tokens = $0.016
  Executor (Haiku):    ~1,200 input tokens, ~750 output tokens = $0.004
  Subtotal: $0.020

Iteration 1:
  Editor (Sonnet):     ~1,300 input tokens, ~1,100 output tokens = $0.020
  Subtotal: $0.020

Iteration 2:
  Editor (Sonnet):     ~1,300 input tokens, ~1,100 output tokens = $0.020
  Subtotal: $0.020

Generator total: $0.060
vs All Sonnet:   $0.150 (60% savings)
```

The judge dominates total run cost (~$0.21 of ~$0.35). Generator savings are real but the biggest cost lever is judge optimization, not generator optimization.
