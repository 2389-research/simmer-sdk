# simmer-sdk

Programmatic implementation of the [simmer](https://github.com/2389-research/claude-plugins/tree/main/simmer) iterative refinement loop using the Claude Agent SDK. Same architecture as the Claude Code skill — generate, evaluate, judge, reflect — but callable from scripts, pipelines, and any Python environment.

## Install

```bash
uv add simmer-sdk
# or
pip install simmer-sdk
```

Requires `ANTHROPIC_API_KEY` set in your environment, or AWS credentials for Bedrock mode.

## Usage

```python
import anyio
from pathlib import Path
from simmer_sdk import refine

async def main():
    result = await refine(
        artifact=(
            "A one-shot DND adventure hook for a party of 4 level-5 characters. "
            "The setting: a coastal town where fishermen have been pulling up bones "
            "instead of fish for the past week. The town's mayor has gone missing. "
            "Should be 300-500 words, playable in a 3-4 hour session."
        ),
        criteria={
            "narrative_tension": (
                "scenes have escalating stakes, time pressure, and meaningful "
                'consequences — 10/10 means every scene raises the question '
                '"what happens if we don\'t act?"'
            ),
            "player_agency": (
                "multiple decision points where the party's choices genuinely "
                "change the outcome — 10/10 means no railroading, at least 3 "
                "distinct paths through the adventure"
            ),
            "specificity": (
                "concrete names, locations, sensory details, NPC motivations — "
                "10/10 means a DM could run this cold without inventing anything"
            ),
        },
        primary="player_agency",
        iterations=3,
        mode="seedless",
        judge_mode="board",
        output_dir=Path("/tmp/simmer-dnd-test"),
    )

    print(f"Best: iteration {result.best_iteration} ({result.composite}/10)")
    print(result.best_candidate)

anyio.run(main)
```

## Configuration

The `refine()` function accepts a config that maps to the simmer skill's setup brief:

```
ARTIFACT          -> artifact         # text content, file path, directory path, or description
ARTIFACT_TYPE     -> (auto-detected)  # "single-file" or "workspace"
CRITERIA          -> criteria         # dict of {name: "what 10/10 looks like"}
PRIMARY           -> primary          # criterion name for best-so-far comparison
EVALUATOR         -> evaluator        # shell command (supports {candidate_path}, {iteration}, {output_dir})
BACKGROUND        -> background       # constraints, available resources
OUTPUT_CONTRACT   -> output_contract  # valid output format description
VALIDATION_COMMAND-> validation_command # quick check command
SEARCH_SPACE      -> search_space     # what's in scope to explore
JUDGE_MODE        -> judge_mode       # "auto", "single", "board"
JUDGE_PANEL       -> judge_panel      # custom judge definitions [{name, lens}]
JUDGE_COUNT       -> judge_count      # number of judges on the board (default 3, min 2)
ITERATIONS        -> iterations       # number of generate-judge-reflect cycles (default 3)
MODE              -> mode             # "auto", "seedless", "from-file", "from-paste", "from-workspace"
OUTPUT_DIR        -> output_dir       # where iteration files go (default "docs/simmer")
```

### Models

Every LLM call is independently configurable:

```python
result = await refine(
    ...,
    generator_model="claude-sonnet-4-6",  # default
    judge_model="claude-sonnet-4-6",      # default
    clerk_model="claude-haiku-4-5",       # default, board synthesis + reflect
)
```

### AWS Bedrock

To use AWS Bedrock instead of the direct Anthropic API:

```python
result = await refine(
    ...,
    api_provider="bedrock",
    aws_access_key="AKIA...",
    aws_secret_key="...",
    aws_region="us-east-1",
    generator_model="claude-sonnet-4-5",  # auto-mapped to Bedrock ID
    judge_model="claude-sonnet-4-5",
    clerk_model="claude-haiku-4-5",
)
```

Model IDs are auto-mapped (e.g., `claude-sonnet-4-5` becomes `us.anthropic.claude-sonnet-4-5-20250929-v1:0`). You can also pass Bedrock model IDs directly. Requires `boto3` (included as a dependency).

### Evaluators

The evaluator is a shell command run after each generator step. Its stdout/stderr is passed to the judge as evidence. Supports template variables:

```python
# Word count check
evaluator="wc -w {candidate_path}"

# Run a test suite
evaluator="python eval_scorer.py --spec {candidate_path} --output {output_dir}/eval_v{iteration}"

# Shell script
evaluator="./run_eval.sh {candidate_path} {output_dir}"
```

### Callbacks

```python
async def on_iteration(record, trajectory, trajectory_table):
    """Called after each iteration with the trajectory table."""
    print(trajectory_table)

async def on_plateau(trajectory):
    """Called when 3 iterations without improvement. Return True to upgrade to board."""
    return True

result = await refine(..., on_iteration=on_iteration, on_plateau=on_plateau)
```

## Output

`refine()` returns a `SimmerResult`:

```python
result.best_candidate   # str — the best artifact text
result.best_iteration   # int — which iteration produced the best
result.best_scores      # dict — per-criterion scores for best
result.composite        # float — best composite score
result.trajectory       # list[IterationRecord] — full history
result.stable_wins      # list[str] — what's been working
result.not_working      # list[str] — what's been tried and failed
result.output_dir       # Path — where iteration files were written
```

### Output Directory

```
{output_dir}/
  iteration-0-candidate.md     # seed (or seedless first generation)
  iteration-0-judgment.md      # raw judge output (scores, evidence, improvements per criterion)
  iteration-1-candidate.md     # each improved candidate
  iteration-1-judgment.md      # raw judge output
  iteration-2-candidate.md
  iteration-2-judgment.md
  iteration-3-candidate.md
  iteration-3-judgment.md
  trajectory.md                # running score table
  result.md                    # final best output
```

The `iteration-N-judgment.md` files contain per-criterion scores, evidence, and improvement suggestions from the judge. Useful for building UIs that show the judge's reasoning or for downstream agents that extract structured detail.

## Architecture

1:1 translation of the 6 simmer Claude Code skill files. The actual skill markdown files are bundled in `src/simmer_sdk/skill_reference/` and used as prompts.

| Role | Implementation | Tools |
|------|---------------|-------|
| Generator | Agent SDK subagent | Read, Edit, Write, Bash, Glob, Grep |
| Judge (single) | Agent SDK subagent | Read, Grep, Glob |
| Judge (board) | N Agent SDK subagents in parallel (default 3, configurable) | Read, Grep, Glob |
| Reflect | Agent SDK subagent | Read, Write, Glob |
| Evaluator | subprocess.run() | (user-provided command) |
| Clerk (synthesis) | anthropic messages.create() | (no tools) |

## Development

```bash
uv sync --all-extras
uv run pytest tests/ -m "not integration"        # unit tests (no API calls)
ANTHROPIC_API_KEY=... uv run pytest -m integration -v -s  # integration tests (real API)
```
