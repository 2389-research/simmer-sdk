# Simmer Trajectory — Local Extraction Prompt

| Iter | Coverage | Noise | Specificity | Conceptual Depth | Composite | Key Change |
|------|----------|-------|-------------|-----------------|-----------|------------|
| 0    | 4.7      | 5.0   | 4.3         | 3.3             | 4.3       | seed       |
| 1    | 5.6      | 4.2   | 4.1         | 3.3             | 4.3       | correction table + compound rules + expanded taxonomy |

| 2    | 5.5      | 5.5   | 4.7         | 4.3             | 5.0       | restructured: correction at end, type-gating, discourse examples |

| 3    | 5.2      | 5.3   | 6.0         | 5.25            | 5.4       | contrast pairs, closed type set, recovered glazing+outlining+NMM hyphen |

| 4    | 6.3      | 4.0   | 5.0         | 5.3             | 5.2       | REVIEW STEP (failed), high contrast extracted |

| 5    | 6.3      | 5.7   | 6.7         | 5.3             | 6.0       | removed failed REVIEW STEP, added brush/orange to examples, display piece NEW |

Best: iteration 5 (6.0/10).

## Iteration 0 — Seed
- 34 entities extracted, 27 ground truth
- ~14 true positives, ~17 false positives, 13 ground truth missed
- Major issues: compound entities split, caption garbles uncorrected, missing type taxonomy, no dedup
- ASI → Add caption correction table + compound entity preservation rule

## Iteration 1
- 36 entities extracted. Coverage up (rhinox hide corrected, outlines/power weapon new), but noise worse (22 FPs vs 17)
- Correction table only partially followed: rhinox hide ✓, mephiston red ✗, trovarion ✗
- "When in doubt include" bias increased noise without proportional coverage gain
- 9B model ignores correction table at top of prompt — working context decay
- ASI → Restructure: extraction first, post-processing correction/validation at END

## Iteration 2
- 32 entities extracted. Mephiston red CORRECTED, reflection placement EXTRACTED, feather singular
- Lost glazing and outlining (type-gating regression). Trovarion dropped entirely.
- 19 FPs — type-gating partially helped but model invents types for fragments
- 9B model applies "novelty filter": keeps unusual compounds, drops common words with domain meaning
- ASI → Add contrast pairs (KEEP vs DROP by semantic role), strict closed-type-list gating

## Iteration 3
- 28 entities. NMM hyphen corrected, glazing+outlining recovered. Orange regressed (standalone color ban too aggressive)
- Contrast pairs FAILED for discourse-level entities (intermediate, display piece, high contrast, color temperature)
- Board confirms 9B capability ceiling: discourse-level semantic inference not achievable via prompting
- chris baron→trovarion has never worked in 4 iterations — architectural problem, not prompt problem
- DO NOT list items (darkest areas, etc.) still extracted — model treats as soft guidance
- ASI → Accept ceiling. Fix orange regression. Restructure DO NOT as post-extraction review. Add dedup review step.

## Iteration 4
- 28 entities. HIGH CONTRAST extracted (new discourse-level win!). But REVIEW STEP completely ignored.
- gold, warm, white, yellow, upper edges, guide all survived despite being explicit DELETE targets
- REVIEW STEP is dead — 9B model cannot do post-extraction review
- Regression from iter 3 (5.4→5.2). Starting iter 5 from iter 3 candidate.
- ASI → Remove REVIEW STEP (wastes tokens), recover orange, tighten inline instructions

## Iteration 5 (FINAL)
- 32 entities. display piece EXTRACTED (new!), high contrast persists.
- 15 clean GT matches + 2 partials. Recall ~0.59 (up from 0.43 seed)
- Noise: ~16 FPs. Precision ~0.50 (up from 0.41 at worst, roughly same as seed 0.45)
- 3 discourse-level entities now extracted (display piece + high contrast + reflection placement) vs 0 in seed
- Best composite: 6.0/10 (up from 4.3 seed)

## Summary
- **Start:** 4.3/10 composite (seed: simple prompt, no corrections, no type taxonomy)
- **End:** 6.0/10 composite (iteration 5: structured prompt with correction table, closed type set, contrast pairs, discourse examples)
- **Coverage:** 4.7 → 6.3 (+34%) — 15 clean GT matches (up from 10)
- **Noise:** 5.0 → 5.7 (+14%) — precision ~0.50 (up from 0.45)
- **Specificity:** 4.3 → 6.7 (+56%) — mephiston red corrected, NMM hyphenated, canonical forms enforced
- **Conceptual depth:** 3.3 → 5.3 (+61%) — 3 discourse-level entities extracted (from 0)
- **Key architectural learnings:** 9B models ignore DO NOT lists, can't do post-extraction review, have a ceiling on semantic inference. Correction tables work at end of prompt for known-string fixes. Worked examples are the strongest signal.
