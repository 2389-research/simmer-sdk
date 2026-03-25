# simmer-sdk Design Spec

**Date:** 2026-03-25
**Status:** Approved
**Reference:** `docs/spec.md` (API spec), Claude Code skill source (6 SKILL.md files)

## What This Builds

A Python library (`simmer-sdk`) that implements the simmer iterative refinement loop as code, using the Claude Agent SDK for subagent dispatch. Full functionality match with the Claude Code skill — same architecture, same context discipline, same prompt patterns.

## Architecture

1:1 translation of the 6 skill files into Python modules. The Agent SDK dispatches generator and judge subagents with isolated contexts and tool access.

### Core Loop

```
refine() called
  -> Setup (classify problem, select judge mode)
  -> Iteration 0: seed judgment
  -> Iterations 1-N: generate -> evaluate -> judge -> reflect
  -> Return SimmerResult
```

### Module Map

| Skill File | SDK Module | Responsibility |
|---|---|---|
| `SKILL.md` (orchestrator) | `refine.py` | Main loop |
| `simmer-setup/SKILL.md` | `setup.py` | Problem classification, judge mode auto-selection |
| `simmer-generator/SKILL.md` | `generator.py` | Dispatch generator via Agent SDK |
| `simmer-judge/SKILL.md` | `judge.py` | Dispatch single judge via Agent SDK |
| `simmer-judge-board/SKILL.md` | `judge_board.py` | Board: compose, parallel dispatch, deliberation, synthesis |
| `simmer-reflect/SKILL.md` | `reflect.py` | Trajectory, regression, plateau, stable wins |
| (primitives in board skill) | `primitives.py` | Judge primitive library |
| (prompt blocks from all skills) | `prompts.py` | All prompt templates |
| (data classes) | `types.py` | SimmerResult, IterationRecord, StableWins, etc. |

## Key Design Decisions

### Agent SDK for Subagents
Generator gets `[Read, Edit, Write, Bash, Glob, Grep]`. Judges get `[Read, Grep, Glob]`. Investigation-first judges read files via tools — not pre-digested summaries. Matches the skill exactly.

### Prompts Match the Skill Verbatim
Prompt templates are direct translations of the skill's prompt blocks. The skill's prompts are battle-tested — verbose is correct.

### Reflect Stays Python
No LLM call. Trajectory math, best-so-far, regression detection, stable wins, exploration status. Pure dataclass operations.

### Setup is Caller-Provided
The interactive setup skill doesn't translate to a library. Callers provide the brief via `refine()` parameters. Auto-selection logic runs as Python functions.

### Model Configuration
Every LLM call gets its model from config. Per-role overrides:

```python
result = await refine(
    artifact="...",
    criteria={...},
    generator_model="claude-sonnet-4-6",  # default
    judge_model="claude-sonnet-4-6",       # default — depth comes from investigation, not model tier
    clerk_model="claude-haiku-4-5",        # default, used for board synthesis
)
```

All three independently configurable. For dev/testing, pass haiku for everything.

Judge quality comes from investigation-first prompts (reading files, understanding the evaluator, researching solutions) and sufficient tool turns — not from using opus. The skill's INVESTIGATE step is what forces depth.

### Context Discipline (matching skill exactly)

| Role | Receives | Excluded |
|---|---|---|
| Generator | Current candidate, criteria, ASI, background, panel summary | Scores, previous candidates, evaluator output |
| Judge (text/creative) | Current candidate, criteria, iteration #, seed + seed scores | Intermediate scores, previous candidates, previous ASI |
| Judge (code/pipeline) | Above + evaluator output, previous ASI, iteration history, exploration status | Full candidate history |
| Judge Board | Same per-judge rules + cross-judge scores in deliberation | Cross-judge ASI (withheld until synthesis) |

Rationale: Subjective (creative) judges are isolated from prior scores to prevent anchoring bias. Objective (code/pipeline) judges get history to enable strategic ASI reasoning.

## Public API

See `docs/spec.md` for full API surface: `refine()`, `SimmerResult`, `IterationRecord`, callbacks.

## Testing Strategy

- **Unit tests** (no API): reflect logic, plateau detection, setup classification, board consensus math, type construction
- **Integration test** (real API, haiku): DND adventure hook, seedless, 2 iterations. Validates full loop.
- Models configurable per test — default haiku for cost.

## Dependencies

- `anthropic>=0.40.0`
- `claude-agent-sdk>=0.1.50`
- `pytest`, `pytest-asyncio` (dev)
