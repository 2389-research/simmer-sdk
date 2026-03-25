# Simmer Trajectory: Local Extraction Prompt (Agency Board)

| Iter | Coverage | Noise | Specificity | Conceptual Depth | Composite | Key Change |
|------|----------|-------|-------------|------------------|-----------|------------|
| 0    | 5        | 4     | 5           | 3.5              | 4.4       | seed — 15/27 hits, 14 extras |
| 1    | 3.5      | 2.5   | 3           | 3                | 3.0       | REGRESSION — stripped correction table |
| 2    | 3.5      | 2.5   | 3           | 2.5              | 2.9       | REGRESSION — nuanced stop-list failed |
| 3    | 4.5      | 5     | 4.5         | 3                | 4.25      | noise improved (12 extras), coverage below seed |
| 4    | 6        | 4     | 5.5         | 5.5              | 5.3       | correction table + examples merged |
| 5    | 7.5      | 5.5   | 6.5         | 6                | 6.4       | **BEST** — 19/26 hits, 6 extras, 95% reachable recall |

**Best candidate: iteration 5 (composite: 6.4/10, coverage: 7.5/10)**

## Summary: Seed → Best

| Metric | Seed (iter 0) | Best (iter 5) | Delta |
|--------|--------------|---------------|-------|
| Hits | 15/27 | 19/26 | +4 |
| Extras | 14 | 6 | -8 |
| Recall | 56% | 73.1% | +17.1pp |
| Precision | 52% | 76.0% | +24pp |
| Reachable recall | ~75% | 95.0% | +20pp |
| Composite | 4.4 | 6.4 | +2.0 |

## What Changed (Seed → Best)

1. **Correction table expanded**: Added "nonmetallic"→"non-metallic metal", "outline"→"outlining", "feathers"→"feather", "reflections"→"reflection", "edges"→"edge"
2. **Compound color splitting rule**: "warm and cold gold" → extract both as separate entities
3. **Stop-list removed**: Replaced with positive examples + review checklist
4. **4 worked examples** (up from 1): covering paints, colors, body_areas, concepts, brand inference
5. **Brand inference checklist**: Explicit "BEFORE RETURNING" check for citadel/vallejo
6. **Rules reduced from 9 to 6**: Focused on what the 9b model can reliably follow

## Transcript Audit
6 ground truth entities NOT in transcript: dark brown, high contrast, color temperature, reflection placement, display piece, intermediate. These are unreachable.

## Key Lessons
- Correction table is the most reliable mechanism for a 9b model — it follows lookup tables better than abstract rules
- Stop-lists with nuanced conditional logic fail on small models
- Worked examples are more effective than rule lists for type coverage
- The "BEFORE RETURNING" checklist activates post-extraction verification
- Transcript audit revealed phantom targets, enabling focused optimization on reachable entities
