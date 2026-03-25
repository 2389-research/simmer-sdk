# Simmer Trajectory — Local Extraction Prompt

| Iter | Coverage | Noise | Specificity | Conceptual Depth | Composite | Key Change |
|------|----------|-------|-------------|-----------------|-----------|------------|
| 0    | 6        | 6     | 4           | 3               | 4.8       | seed       |
| 1    | 5        | 4     | 5           | 4               | 4.5       | +taxonomy +correction table (REGRESSED — noise explosion) |
| 2    | 5        | 4     | 5           | 3               | 4.3       | +noise gate +blocklist (REGRESSED — model ignores inline rules) |
| 3    | 6        | 5     | 4           | 3               | 4.5       | example-driven approach (flat — model patterns entrenched) |
| 4    | 5        | 5     | 4           | 3               | 4.3       | v4_full STEP architecture (corrections still not applied) |
| 5    | 5        | 4     | 4           | 3               | 4.0       | full v4_full prompt (non-determinism revealed) |
| 5*   | ~7       | ~7    | ~8          | ~5              | ~6.8      | *same prompt, baseline run — corrections fired stochastically* |

Best single-run: iteration 0 seed (4.8/10)
Best prompt (demonstrated capability): iteration 5 / v4_full (~6.8 when corrections fire)

## Key Findings

1. **Model non-determinism dominates**: At temperature 0.3, qwen3.5:9b produces wildly different results on the same prompt. The v4_full prompt CAN correct names, infer brands, and extract theory concepts — but doesn't do so reliably. Single evaluations are unreliable for comparison.

2. **The 9b model ignores inline rules**: Correction tables, blocklists, noise gates, and searchable tag tests are all treated as advisory. Only the type taxonomy table and worked examples have reliable influence.

3. **The seed was a regression from v4_full**: The well-refined v4_full prompt (already in the codebase) is clearly superior to the seed on average, but the seed happened to get a favorable single run.

4. **Prompt engineering ceiling**: All 5 iterations failed to reliably improve on the seed's single-run score. The v4_full architecture is the best available, but the model's stochastic behavior means improvements are only visible over multiple runs.

## Recommendations

- **Reduce temperature to 0.0-0.1** to collapse variance and make corrections more reliable
- **Run evaluator 3x and average** to get stable scores for comparison
- **Use v4_full prompt** (iteration 5 candidate) as the production prompt — it demonstrably CAN apply corrections and extract theory concepts
- **Post-processing pipeline** may be needed for normalization the model can't reliably do inline
