# SDK Shakespeare Scene Test v1 — Experiment Report

**Date:** 2026-03-25
**Test:** Creative writing outside DND domain — verse drama with board judges

## Config

```
ARTIFACT: A single scene from a Shakespearean tragedy. Two former allies
  meet after one has betrayed the other. The betrayer has come to ask
  forgiveness but the betrayed holds a secret that changes everything.
  Should be 200-400 words in iambic pentameter with modern vocabulary.
CRITERIA:
  - dramatic_tension (PRIMARY): escalating scene, power shifts, gut-punch reveal
  - character_voice: distinct psychology per character, subtext carries weight
  - craft: iambic pentameter maintained, modern vocab natural in verse structure
PRIMARY: dramatic_tension
JUDGE_MODE: board
ITERATIONS: 3
MODE: seedless
EVALUATOR: word count (target 200-400)
MODELS: claude-sonnet-4-6 for generator + judge
```

## Results

| Iter | Tension (PRIMARY) | Voice | Craft | Composite | Words | Key Change |
|------|-------------------|-------|-------|-----------|-------|------------|
| 0 | 7 | 7 | 8 | 7.3 | 427 | seed |
| 1 | 7 | 6.5 | 7 | 6.8 | ~430 | REGRESSION — missed Marcus voice |
| 2 | 7.5 | 7 | 7 | 7.2 | ~430 | REGRESSION from seed — doubled vocative |
| 3 | 7.5 | 7.5 | 6.5 | 7.2 | 442 | Lateral move — recognition beat added but craft broke |

**Best candidate: Iteration 0 (seed) at 7.3/10**

## Analysis

### What Worked
- **Board composition**: Judges self-composed as "Audience Experience", "Psychological Realist", "Verse Technician" — domain-appropriate without hardcoded hints
- **Regression detection**: Correctly identified iterations 1 and 2 as regressions, rolled back to best candidate
- **Judge analysis depth**: Specific structural critiques ("Marcus's passive absorption of the warrant through two consecutive truncations", "shared-line dismantled at pivotal moment")
- **Evaluator integration**: Word count reported each iteration, judges noted "word count overrun (442 vs 400 ceiling)"
- **Domain-agnostic research**: Judges researched verse drama craft without being told what to look for

### What Didn't Work
- **Generator couldn't improve on a strong seed**: Verse drama is fragile — edits to one aspect (tension) broke another (craft). The generator's changes were net-negative across all 3 iterations.
- **ASI specificity vs execution gap**: ASIs were specific ("Marcus needs active response at warrant reveal") but the generator couldn't execute without regressing on craft.
- **No improvement trajectory**: 7.3 → 6.8 → 7.2 → 7.2. The loop correctly protected quality via regression rollback but never advanced.

### Key Finding
The simmer loop works differently on verse drama than on adventure design. Adventure hooks have many independent axes to improve (add paths, add NPCs, add mechanics). Verse has tightly coupled elements where improving one often degrades another. The loop correctly recognized it couldn't beat the seed — that's the system working. But 3 iterations of zero improvement suggests the generator needs more guidance on *preserving* craft while addressing ASI feedback.

## Artifacts

```
tests/reference/sdk-shakespeare-v1/
├── iteration-0-candidate.md     # Seed = best (427 words)
├── iteration-1-candidate.md     # Regression
├── iteration-2-candidate.md     # Regression from seed
├── iteration-3-candidate.md     # Lateral move
├── result.md                    # = iteration 0
├── trajectory.md                # Full trajectory with evaluator details
└── experiment_report.md         # This file
```
