# Simmer Trajectory — Local Extraction Prompt

| Iter | Coverage (P) | Noise | Specificity | Depth | Composite | Key Change |
|------|-------------|-------|-------------|-------|-----------|------------|
| 0    | 6           | 5     | 4           | 2     | 4.25      | seed — simple prompt, no corrections, narrow taxonomy |
| 1    | 4           | 4     | 2           | 4     | 3.50      | REGRESSION — added correction table + expanded taxonomy, model confused by complexity (23 vs 34 entities) |
| 2    | 6           | 3     | 5           | 6     | 5.00      | flat structure + inline examples + body_area/aesthetic/concept types. Depth +4, but noise -2 (fragment overgen) |
| 3    | 5           | 3     | 4           | 3     | 3.75      | REGRESSION — NEVER list + compound rule ignored by model, lost color temperature + feather |
| 4    | 6           | 4     | 5           | 3     | 4.50      | 4 few-shot examples, no negatives. Model can't do corrections via few-shot. Ceiling discussion. |
| 5    | 5           | 3     | 5           | 4     | 4.25      | Minimal surgical additions to iter 2. Regressed — adding names to examples didn't transfer. |
