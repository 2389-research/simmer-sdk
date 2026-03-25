# Simmer Trajectory — Local Extraction Prompt

| Iter | Coverage | Noise | Specificity | Conceptual Depth | Composite | Key Change |
|------|----------|-------|-------------|-----------------|-----------|------------|
| 0    | 5        | 4     | 5           | 4               | 4.5       | seed (v4_full hardcoded — correction tables + rules) |
| 1    | 5        | 3     | 4           | 3               | 3.8       | REGRESSED — taxonomy table + cleanup rules, model ignored |
| 2    | 4        | 3     | 3           | 3               | 3.3       | REGRESSED — compact types + hard negatives + correction lookup |
| 3    | 4        | 3     | 3           | 3               | 3.3       | REGRESSED — pure few-shot (4 examples), more noise without DO NOT |
| 4    | 4        | 3     | 3           | 3               | 3.3       | REGRESSED — v4_full merge + new types + example 2, prompt too long |
| 5    | 6        | 5     | 6           | 5               | 5.8       | **BEST** — exact v4_full + STEP 3 verify corrections |

Best: iteration 5 (5.8/10)

## Key Learnings

1. **Don't simplify what works.** v4_full's STEP structure, correction table, numbered rules, and entity types table were all load-bearing. Every attempt to simplify (iters 1-3) degraded performance.
2. **Don't add to what works either.** Adding types, examples, or rules to v4_full (iter 4) pushed past the model's effective attention window.
3. **Self-correction works.** STEP 3 "verify corrections" forced a second pass that successfully applied corrections (trovarion, rhinox hide, mephiston red) that had failed across all prior iterations.
4. **Small models learn from structure, not volume.** The qwen3.5:9b model responds to numbered STEP sequences and explicit rules but cannot handle long rule lists, tables, or abstract instructions.
5. **Next direction:** Add STEP 4 verify completeness — category checklist (3-4 lines) prompting the model to check for aesthetic, body_area, skill_level, topic entities.
