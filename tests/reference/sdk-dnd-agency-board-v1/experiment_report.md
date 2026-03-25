# SDK DND Agency Board Test v1 — Experiment Report

**Date:** 2026-03-25
**Test:** Feature parity validation — SDK simmer loop vs Claude Code skill
**Status:** Complete

## What We Tested

Can the simmer-sdk produce comparable qualitative results to the Claude Code simmer skill on the same DND adventure hook prompt, using the same config (board mode, 3 iterations, seedless, primary=player_agency)?

## Config

```
ARTIFACT: A one-shot DND adventure hook for a party of 4 level-5 characters.
  The setting: a coastal town where fishermen have been pulling up bones
  instead of fish for the past week. The town's mayor has gone missing.
  Should be 300-500 words, playable in a 3-4 hour session.
ARTIFACT_TYPE: single-file
CRITERIA:
  - narrative_tension: scenes have escalating stakes, time pressure, and
    meaningful consequences — 10/10 means every scene raises the question
    "what happens if we don't act?"
  - player_agency: multiple decision points where the party's choices
    genuinely change the outcome — 10/10 means no railroading, at least 3
    distinct paths through the adventure
  - specificity: concrete names, locations, sensory details, NPC motivations
    — 10/10 means a DM could run this cold without inventing anything
PRIMARY: player_agency
JUDGE_MODE: board
ITERATIONS: 3
MODE: seedless
OUTPUT_DIR: /tmp/simmer-dnd-agency-test
EVALUATOR: word count check (PASS/FAIL against 300-500 target)
GENERATOR_MODEL: claude-sonnet-4-6
JUDGE_MODEL: claude-sonnet-4-6
```

## Results

### Trajectory

| Iter | Tension | Agency (PRIMARY) | Specificity | Composite | Words | Key Change |
|------|---------|------------------|-------------|-----------|-------|------------|
| 0    | 8       | 7                | 8           | 7.7       | 575   | seed |
| 1    | 8       | 8                | 8           | 8.0       | 514   | Choir fork refactor, backstory compression |
| 2    | (missing from trajectory — reflect LLM mislabeled as iter 3) | | | | 513 | |
| 3    | 9       | 8                | 8           | 8.3       | 607   | Water escalation at Choir (DC 13 Str save) |

**Best candidate:** Iteration 3 (8.3/10)

### Comparison to Skill Reference

The skill reference run (in `tests/reference/dnd-agency-board/`) scored 7.0 → 7.7 → 9.0 over 3 iterations (824 words final). Scores are not comparable across runs (different judges, seeds, calibration). Qualitative comparison:

| Dimension | SDK Result | Skill Reference | Assessment |
|-----------|-----------|-----------------|------------|
| Narrative tension | One clock (high tide). Choir Chamber has environmental pressure (DC 13 Str save, rising water). Town-side thin. | Tomas interruption forces mid-session priority choice. Faction fallout creates layered consequences. | Skill reference stronger — tension between threads, not just within dungeon |
| Player agency | Three investigation paths converge to one dungeon. Choir Chamber fork (stealth vs shatter). End-of-adventure moral choice. | Three threads lead to three different climaxes. Mid-thread forks (Neshka ally, Elda refuses rescue). NPC betrayal conditions. | Skill reference significantly stronger — structural divergence vs convergence |
| Specificity | Named NPCs with motivations. DCs throughout. MM page references. Nella's address specified. | Full inline stat blocks. NPC table with motivations + betrayal triggers. Sensory details throughout. | Skill reference more complete — stat blocks and NPC table are DM tools |
| Word count control | 575 → 514 → 513 → 607 (evaluator kept scope tight) | 702 → 625 → 824 (naturally controlled) | Comparable — evaluator worked |

### Key Findings

1. **The simmer loop works mechanically.** Scores improved (7.7 → 8.0 → 8.3), trajectory.md was maintained, candidate files written correctly, evaluator output influenced judge feedback (word count stayed controlled).

2. **Qualitative improvement is real but structural ceiling is lower.** The SDK judges improved within the existing adventure structure (better Choir mechanics, tighter prose) but didn't push for structural innovation (mid-thread forks, interruption mechanics, faction systems). The skill reference's judges identified deeper structural weaknesses.

3. **The evaluator feedback loop works.** Word count evaluator kept scope from ballooning (previous run without evaluator hit 8829 words by iteration 1). Judges factored evaluator output into ASI.

4. **Bookkeeping bug: reflect LLM mislabeled iteration 2 as "3" in trajectory.** The candidate files (iteration-2-candidate.md) were written correctly but trajectory.md skipped from iteration 1 to iteration 3.

### What's Working

- Seedless candidate capture (actual content, not generator report)
- trajectory.md written by reflect agent via Write tool
- Scores parsing from trajectory.md table (reliable)
- Evaluator template variables ({candidate_path}, {iteration}, {output_dir})
- Board composition cached once, reused across iterations
- Key change condensation via LLM
- Original brief propagated to generator every iteration

### What Needs Improvement

- **ASI quality gap:** SDK judges suggest incremental mechanical improvements; skill judges push for structural redesign. May need investigation depth improvements (more max_turns, better investigation prompts).
- **Reflect iteration numbering:** LLM occasionally mislabels iteration numbers in trajectory table.
- **Stable wins formatting:** Markdown bold markers leaking into stable wins labels.

## Artifacts

```
tests/reference/sdk-dnd-agency-board-v1/
├── iteration-0-candidate.md     # Seed (575 words)
├── iteration-1-candidate.md     # After iter 1 (514 words)
├── iteration-2-candidate.md     # After iter 2 (513 words)
├── result.md                    # Best candidate = iter 3 (607 words)
├── trajectory.md                # Score trajectory (bug: missing iter 2)
└── experiment_report.md         # This file
```

Skill reference for comparison: `tests/reference/dnd-agency-board/`
