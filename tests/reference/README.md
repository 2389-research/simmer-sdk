# Reference Test Data

These are real outputs from simmer skill runs during development and testing. They serve as reference data for the SDK — the SDK should produce comparable quality outputs given the same inputs.

## Test Runs

### Creative / DND Adventure Hooks

| Directory | Config | Result | Notes |
|-----------|--------|--------|-------|
| `dnd-agency-board/` | Agency-composed judge board, seedless | 9.0/10 | Mid-thread forks, Tomas interruption, faction fallout, NPC betrayal table |
| `dnd-progress-test/` | Single judge, auto-selected, seedless | 9.0/10 | Siphon Clock, color NPCs, per-iteration trajectory display test |

### Extraction Prompt Optimization

| Directory | Config | Result | Notes |
|-----------|--------|--------|-------|
| `extraction-builtin-judges/` | Built-in judge composition, investigation-first | 17/26 GT hits, 65% recall, 89% precision | Investigation discovered scoring mechanics at iter 0 |
| `simmer-agency-board-test/` | Agency-composed judges, static | 19/26 GT hits, 73% recall, 76% precision | Best coverage, brand inference, transcript audit |
| `simmer-agency-exec-test/` | Agency judges + Agency generator (exec craft) | 5.8 composite | Generator overrode ASI — not recommended |
| `simmer-agency-full-test/` | Agency judges + Agency generator (strategic) | 5.0 composite | Generator conflicted with board — proved generators should not strategize |
| `simmer-adaptive-judges-test/` | Adaptive re-composition each iteration | Variable | Proved static composition beats adaptive |
| `simmer-adaptive-v2-test/` | Adaptive + stable wins | 4.8 composite | Pivoting problem persisted |

### UX Tests

| Directory | Config | Result | Notes |
|-----------|--------|--------|-------|
| `simmer-plateau-test/` | Single judge → plateau → board upgrade | 7.5 → 8.0 | Validated auto-selection, plateau detection, board upgrade flow |

## Findings Reports

| File | Summary |
|------|---------|
| `agency-creative-test-results.md` | DND adventure: Agency board produces richer artifacts (mid-thread forks, moral dilemmas) |
| `investigation-judges-final-results.md` | Investigation > composition. 17/26 at 89% precision without Agency. Every innovation discovered 4-5 iters faster. |
| `investigation-vs-agency-creative-comparison.md` | Agency produces memorable moments, investigation produces runnable adventures. Criteria control which you get. |

## How to Use

These are **reference outputs**, not automated test fixtures. The SDK should:

1. Be able to reproduce comparable quality on the same tasks
2. Follow the same trajectory patterns (monotonic improvement on simple tasks, plateau detection on complex ones)
3. Produce the same output format (trajectory tables, iteration candidates, result files)

The extraction prompt tests require local Ollama with qwen3.5:9b and the evaluator script from the DS-scratch repo. The DND tests are judge-only (no evaluator) and can run with just Claude API access.
