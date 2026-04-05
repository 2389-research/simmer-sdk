# simmer-sdk Specification

**Date:** 2026-03-25
**Status:** Draft
**Purpose:** Programmatic implementation of the simmer iterative refinement loop using the Claude Agent SDK

## Reference: The Simmer Skill

This SDK is a programmatic translation of the simmer Claude Code skill. The skill is the reference implementation — all design decisions, context discipline rules, judge board behavior, and prompt patterns originate there.

**Skill source:** https://github.com/2389-research/claude-plugins/tree/main/simmer

Key files to read:
- [`simmer/skills/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/SKILL.md) — Orchestrator (the main loop, context discipline, iteration counting, plateau detection)
- [`simmer/skills/simmer-judge-board/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-judge-board/SKILL.md) — Judge board (composition, investigation-first, deliberation, synthesis, primitive library)
- [`simmer/skills/simmer-judge/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-judge/SKILL.md) — Single judge (scoring rules, ASI format, calibration, evaluation modes)
- [`simmer/skills/simmer-generator/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-generator/SKILL.md) — Generator (what context it receives, how it executes ASI)
- [`simmer/skills/simmer-reflect/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-reflect/SKILL.md) — Reflect (trajectory, best-so-far, regression, stable wins, exploration status)
- [`simmer/skills/simmer-setup/SKILL.md`](https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-setup/SKILL.md) — Setup (problem classification, criteria inference, judge mode auto-selection)

When in doubt about how the SDK should behave, read the corresponding skill file. The SDK should produce the same outputs given the same inputs.

## What This Is

A Python library that implements simmer's iterative refinement loop as code. Same architecture as the Claude Code skill — generate → evaluate → judge → reflect — but callable from scripts, pipelines, CI/CD, cloud functions, or any Python environment.

```python
from simmer_sdk import refine

result = await refine(
    artifact="path/to/extraction_spec.yaml",
    evaluator="python evaluate.py --held-out-docs ./eval-set/",
    criteria={
        "coverage": "captures important entities from source material",
        "precision": "no noise or hallucinated entities",
        "domain_appropriateness": "entity types meaningful for this domain",
    },
    primary="coverage",
    iterations=5,
)
```

## Why

The simmer skill runs inside Claude Code — great for interactive use, but can't be called from:
- Cloud pipelines (no CLI access)
- CI/CD workflows
- Other Python applications
- Automated systems that need to simmer artifacts programmatically

The SDK preserves everything that makes the skill effective (context isolation, investigation-first judges, judge board with deliberation, stable wins tracking) in a form that any Python code can call.

## Architecture

### Runtime: Claude Agent SDK

The Claude Agent SDK provides:
- **Subagent dispatch** with fresh context windows (generator and judge never share context)
- **Tool access** per subagent (judge gets read-only, generator gets read-write)
- **Model selection** per subagent (opus for judge quality, sonnet for generator speed)
- **Async streaming** for progress updates

### Core Loop

```
refine() called
    │
    ├── Setup
    │   Classify problem (text/creative, code/testable, pipeline/engineering)
    │   Auto-select judge mode (single vs board)
    │   Compose judges from primitive library (if board)
    │
    ├── Iteration 0: Seed
    │   If seedless: dispatch generator to create initial candidate
    │   Run evaluator (if present)
    │   Dispatch judge (or judge board) to score seed
    │   Record trajectory
    │
    ├── Iterations 1-N
    │   ├── Generator subagent
    │   │   Receives: current best candidate + ASI + criteria + background
    │   │   Does NOT receive: scores, previous candidates, evaluator output
    │   │   Tools: Read, Edit, Write, Bash, Glob, Grep
    │   │   Model: sonnet (configurable)
    │   │   Writes improved candidate to output dir
    │   │
    │   ├── Evaluator (if present)
    │   │   Runs user-provided command via subprocess
    │   │   Captures stdout + stderr
    │   │
    │   ├── Judge subagent (or judge board)
    │   │   Receives: candidate + criteria + seed calibration + evaluator output
    │   │   Does NOT receive: intermediate scores (text/creative), previous candidates
    │   │   Tools: Read, Grep, Glob (read-only)
    │   │   Model: opus (configurable)
    │   │   Returns: scores + ASI
    │   │
    │   ├── Reflect
    │   │   Records trajectory, tracks best-so-far
    │   │   Detects regression → next generator gets best candidate
    │   │   Tracks stable wins (WORKING/NOT WORKING)
    │   │   Detects plateau → upgrades to board if currently single
    │   │
    │   └── Progress callback
    │       Calls user-provided callback with trajectory update
    │
    └── Output
        Returns SimmerResult with best candidate, trajectory, stable wins
```

### Subagent Mapping

| Simmer Role | Agent SDK Implementation |
|-------------|------------------------|
| Generator | `ClaudeSDKClient(tools=["Read","Edit","Write","Bash","Glob","Grep"], model=generator_model)` |
| Judge (single) | `ClaudeSDKClient(tools=["Read","Grep","Glob"], model=judge_model)` |
| Judge (board, N×) | N `ClaudeSDKClient` instances in parallel (default 3, configurable via `judge_count`) |
| Reflect | `ClaudeSDKClient(tools=["Read","Write","Glob"], model=clerk_model)` — Agent SDK subagent |
| Evaluator | `anyio.run_process()` (user-provided command, not an LLM call) |
| Clerk (synthesis) | Single `messages.create()` call to synthesize board output (no subagent needed) |

### Context Discipline

Enforced by what gets included in each subagent's prompt — not by framework magic. The orchestrator constructs prompts with the right context per role:

| Role | Receives | Excluded |
|------|----------|----------|
| Generator | Current candidate, criteria, ASI, background, panel summary | Scores, previous candidates, evaluator output |
| Judge (text/creative) | Current candidate, criteria, iteration number, seed + seed scores | Intermediate scores, previous candidates, previous ASI |
| Judge (code/pipeline) | Current candidate, criteria, seed + scores, evaluator output, previous ASI, iteration history, exploration status | Full candidate history |
| Judge (investigation) | File paths to candidate, evaluator script, ground truth, prior candidates | (Reads files itself via tools) |

## Public API

### `refine()`

The main entry point. Runs the full simmer loop and returns the result.

```python
async def refine(
    # Required
    artifact: str | Path,           # File path, directory path, or text content
    criteria: dict[str, str],       # {criterion_name: "what 10/10 looks like"}

    # Optional — evaluation
    evaluator: str | None = None,   # Shell command to run as evaluator
    primary: str | None = None,     # Primary criterion name (for best-so-far)

    # Optional — loop control
    iterations: int = 3,            # Number of generate-judge-reflect cycles
    mode: str = "auto",             # "auto", "seedless", "from-file", "from-paste", "from-workspace"

    # Optional — judge configuration
    judge_mode: str = "auto",       # "auto", "single", "board"
    judge_panel: list[dict] | None = None,  # Custom judge definitions
    judge_count: int = 3,           # Number of judges on the board (min 2)

    # Optional — workspace
    output_dir: str | Path = "docs/simmer",
    background: str | None = None,  # Constraints, available resources
    output_contract: str | None = None,
    validation_command: str | None = None,
    search_space: str | None = None,

    # Optional — models
    generator_model: str = "claude-sonnet-4-6",  # default
    judge_model: str = "claude-sonnet-4-6",      # default
    clerk_model: str = "claude-haiku-4-5",       # board composition, deliberation, reflect

    # Optional — API provider (Bedrock support)
    api_provider: str = "anthropic",   # "anthropic" | "bedrock"
    aws_access_key: str | None = None,
    aws_secret_key: str | None = None,
    aws_region: str | None = None,

    # Optional — callbacks
    on_iteration: OnIterationCallback | None = None,  # Called after each iteration
    on_plateau: OnPlateauCallback | None = None,      # Called when plateau detected (single judge mode only)

) -> SimmerResult:
    ...
```

### `SimmerResult`

```python
@dataclass
class SimmerResult:
    best_candidate: str              # The best artifact text
    best_iteration: int              # Which iteration produced the best
    best_scores: dict[str, int]      # Per-criterion scores for best
    composite: float                 # Best composite score
    trajectory: list[IterationRecord]  # Full history
    stable_wins: list[str]           # What's been working
    not_working: list[str]           # What's been tried and failed
    output_dir: Path                 # Where iteration files were written
```

### `IterationRecord`

```python
@dataclass
class IterationRecord:
    iteration: int
    scores: dict[str, int]          # Per-criterion scores
    composite: float
    key_change: str                  # What changed this iteration
    asi: str                        # The ASI that drove the next iteration
    regressed: bool                 # Whether this iteration regressed
    judge_mode: str                 # "single" or "board"
```

### Callbacks

```python
# Progress callback — called after each iteration with 3 args
async def on_iteration(
    record: IterationRecord,
    trajectory: list[IterationRecord],
    trajectory_table: str,          # formatted markdown table
) -> None:
    print(f"Iteration {record.iteration}: {record.composite}/10 — {record.key_change}")
    print(trajectory_table)

# Plateau callback — called when 3 iterations without improvement.
# Only triggered when judge_mode == "single".
# Return True to upgrade to board and extend run by 2 iterations.
async def on_plateau(trajectory: list[IterationRecord]) -> bool:
    return True  # auto-upgrade to board

result = await refine(
    artifact="prompt.md",
    criteria={...},
    on_iteration=on_iteration,
    on_plateau=on_plateau,
)
```

## Judge Board Implementation

The judge board follows the same architecture as the skill:

### Composition

At the start of the run, the board reads the problem context and constructs 3 judges with diverse lenses. Uses the built-in primitive library (same as the skill) — no Agency MCP dependency.

```python
def compose_judges(brief: dict) -> list[JudgeDefinition]:
    """Construct problem-specific judges from the primitive library."""
    # Read artifact, criteria, evaluator, constraints
    # Design 3 diverse lenses for this specific problem
    # Apply relevant primitives from the library
    # Return 3 JudgeDefinitions with unique prompts
    ...
```

### Three Phases

1. **Independent scoring** — dispatch 3 judge subagents in parallel via Agent SDK
2. **Deliberation** — one round, each judge sees others' scores + reasoning (dispatched as follow-up queries)
3. **Synthesis** — Python function computes consensus scores, distills single ASI

### Investigation-First

Each judge's prompt includes file paths and the INVESTIGATE step:

```python
judge_prompt = f"""
FILES YOU SHOULD READ:
- Candidate: {candidate_path}
- Evaluator script: {evaluator_path}
- Ground truth: {ground_truth_path}
- Prior candidates: {prior_paths}

── STEP 1: INVESTIGATE (required, before scoring) ──
Read the files listed above. Understand the problem before judging it.
...
"""
```

Judges get `Read`, `Grep`, `Glob` tools so they can investigate.

## Stable Wins Tracking

The reflect step (an Agent SDK subagent using clerk_model) maintains:

```python
@dataclass
class StableWins:
    working: list[str]       # Elements that held across 2+ iterations
    not_working: list[str]   # Elements that caused regression
    direction: str           # Current panel conclusion
```

Updated after each iteration by comparing trajectory entries. Passed to judges via deliberation summary and to generator via panel summary.

## Auto-Selection Logic

```python
def auto_select_judge_mode(brief: dict) -> str:
    """Pick single or board based on problem complexity."""
    if brief["mode"] == "from-workspace":
        return "board"
    if brief.get("evaluator"):
        return "board"
    if len(brief["criteria"]) >= 3:
        return "board"
    # Short text artifact with ≤2 criteria
    return "single"
```

## Plateau Detection

```python
def check_plateau(trajectory: list[IterationRecord], primary: str | None) -> bool:
    """3 consecutive iterations without PRIMARY improvement."""
    if len(trajectory) < 4:  # need at least seed + 3 iterations
        return False
    recent = trajectory[-3:]
    best_before = max(t.scores.get(primary, t.composite) for t in trajectory[:-3])
    best_recent = max(t.scores.get(primary, t.composite) for t in recent)
    return best_recent <= best_before
```

When plateau detected and currently single judge → call `on_plateau` callback. If it returns True, upgrade to board + add 2 iterations.

## File Structure

```
simmer-sdk/
├── src/
│   └── simmer_sdk/
│       ├── __init__.py          # exports refine(), SimmerResult
│       ├── refine.py            # main loop orchestrator
│       ├── setup.py             # problem classification, judge mode selection
│       ├── generator.py         # generator subagent dispatch
│       ├── judge.py             # single judge subagent dispatch
│       ├── judge_board.py       # board composition, dispatch, deliberation, synthesis
│       ├── reflect.py           # trajectory tracking, regression, plateau, stable wins (subagent)
│       ├── client.py            # API client factory (Anthropic + Bedrock), model ID mapping
│       ├── primitives.py        # built-in judge primitive library
│       ├── prompts.py           # prompt templates for all roles
│       └── types.py             # SimmerResult, IterationRecord, StableWins, etc.
├── tests/
│   ├── test_refine.py           # integration tests with real API calls
│   ├── test_reflect.py          # unit tests for trajectory logic
│   ├── test_judge_board.py      # unit tests for board composition
│   └── test_plateau.py          # unit tests for plateau detection
├── examples/
│   ├── text_refinement.py       # simmer a document
│   ├── prompt_optimization.py   # simmer a prompt with evaluator
│   ├── extraction_spec.py       # simmer an extraction spec (infodesk use case)
│   └── workspace_pipeline.py    # simmer a workspace
├── docs/
│   └── spec.md                  # this file
├── pyproject.toml
├── README.md
└── LICENSE
```

## Dependencies

```toml
[project]
dependencies = [
    "claude-agent-sdk>=0.1.50",
    "anthropic>=0.40.0",
    "boto3>=1.42.78",
]
```

The Agent SDK (which depends on the Anthropic SDK) plus `boto3` for AWS Bedrock support. Everything else is stdlib.

## Relationship to the Skill

The SDK and the skill are parallel implementations of the same architecture:

| Aspect | Skill (Claude Code) | SDK (Python) |
|--------|-------------------|-------------|
| Orchestrator | Markdown instructions in SKILL.md | Python `refine()` function |
| Generator | Subagent dispatched by Claude Code | `AgentDefinition` dispatched via Agent SDK |
| Judge | Subagent dispatched by Claude Code | `AgentDefinition` dispatched via Agent SDK |
| Reflect | Inline in Claude Code session | Agent SDK subagent (reads/writes trajectory.md via tools) |
| Evaluator | `Bash` tool call | `subprocess.run()` |
| Context discipline | Controlled by what's in the subagent prompt | Same — controlled by prompt construction |
| Judge board | Skill instructions for dispatch + deliberation | Python orchestration of 3 parallel subagents |
| Investigation | Judges read files via Claude Code tools | Judges read files via Agent SDK tools |
| Stable wins | Tracked in markdown files | Tracked in Python dataclass |
| Progress | Trajectory table displayed inline | Callback function called per iteration |

The skill is for humans using Claude Code interactively. The SDK is for code calling simmer programmatically.

## Usage Examples

### Simple text refinement

```python
from simmer_sdk import refine

result = await refine(
    artifact="Dear VP Engineering, I'm reaching out about...",
    criteria={
        "value_clarity": "reader immediately understands the specific problem",
        "response_likelihood": "CTA is so low-friction the recipient replies without thinking",
    },
    iterations=3,
    mode="seedless",
)

print(result.best_candidate)
print(f"Score: {result.composite}/10 after {result.best_iteration} iterations")
```

### Prompt optimization with evaluator

```python
result = await refine(
    artifact="path/to/extraction_prompt.md",
    evaluator="python evaluate.py --model qwen3.5:9b --video ozXhzdjT8tU",
    criteria={
        "coverage": "extracts every entity from ground truth",
        "precision": "zero false positives",
        "conceptual_depth": "captures theory concepts, not just concrete items",
    },
    primary="coverage",
    iterations=5,
    judge_mode="board",
    background="Local Ollama, qwen3.5:9b. Evaluator runs 1 video, ~5 min per run.",
    on_iteration=lambda r, t, table: print(f"Iter {r.iteration}: {r.composite}/10"),
)
```

### Extraction spec simmering (infodesk use case)

```python
async def simmer_domain_spec(domain: str, sample_docs: list[str], eval_docs: list[str]):
    """Called when a domain crosses threshold in the infodesk pipeline."""

    # Write initial spec from sample docs
    initial_spec = generate_initial_spec(domain, sample_docs)
    spec_path = f"/tmp/specs/{domain}/spec.yaml"
    Path(spec_path).write_text(initial_spec)

    result = await refine(
        artifact=spec_path,
        evaluator=f"python evaluate_extraction.py --spec {spec_path} --docs {eval_doc_dir}",
        criteria={
            "coverage": "captures important entities from source material",
            "precision": "no noise or hallucinated entities",
            "domain_appropriateness": "entity types meaningful for this domain",
        },
        primary="coverage",
        iterations=5,
        judge_mode="board",
        background=f"Domain: {domain}. Execution model: qwen3.5:27b local.",
        on_iteration=lambda r, t, table: log_progress(domain, r),
        on_plateau=lambda trajectory: True,  # auto-upgrade to board
    )

    # Deploy the simmered spec
    deploy_spec(domain, result.best_candidate, result.trajectory)
    return result
```

### With custom judge panel

```python
result = await refine(
    artifact="adventure_hook.md",
    criteria={
        "narrative_tension": "escalating stakes and time pressure",
        "player_agency": "genuine choices that change the outcome",
        "specificity": "concrete names, locations, stat blocks",
    },
    primary="player_agency",
    judge_panel=[
        {"name": "Craft", "lens": "Structure, pacing, narrative technique"},
        {"name": "Player", "lens": "Decision quality, railroading avoidance"},
        {"name": "DM", "lens": "Runnability, stat completeness, read-aloud text"},
    ],
    iterations=3,
)
```

## Open Questions

1. ~~**Should reflect be a subagent or Python?**~~ **Resolved.** Reflect is implemented as an Agent SDK subagent (`dispatch_reflect` in `reflect.py`) using clerk_model (haiku). It reads the current `trajectory.md`, updates it with the new iteration's scores, and writes it back via the Write tool. The orchestrator then parses the file for control-flow signals (regression, ASI, stable wins).

2. **How to handle the judge board's deliberation round?** The skill has judges "see each other's scores." In the SDK, this means dispatching N subagents, collecting their output, then dispatching N more subagents with the cross-visibility context. That's 2×N subagent calls per board iteration. Is there a more efficient pattern?

3. **Streaming progress during long evaluator runs.** The evaluator is a subprocess that might run for 5-15 minutes. The SDK's `on_iteration` callback fires after the iteration completes. Should we also emit progress during the evaluator run?

4. **Testing strategy.** Integration tests need real API calls (expensive). Unit tests can cover reflect, plateau detection, and board composition logic. What's the right balance?

5. ~~**Package distribution.**~~ **Resolved.** Package name on PyPI is `simmer-sdk` (see `pyproject.toml`). Note the package name may differ from the import name (`simmer_sdk`).
