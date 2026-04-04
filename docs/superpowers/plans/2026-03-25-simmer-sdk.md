# simmer-sdk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python SDK that implements the full simmer iterative refinement loop using the Claude Agent SDK, matching the Claude Code skill's behavior exactly.

**Architecture:** 9 modules in `src/simmer_sdk/` mapping 1:1 to the 6 skill files plus types, prompts, and primitives. Agent SDK dispatches generator/judge subagents with tool access and isolated contexts. Reflect is pure Python. Unit tests cover all non-LLM logic; integration test validates the full loop with real API calls.

**Tech Stack:** Python 3.11+, `anthropic` SDK, `claude-agent-sdk`, `pytest`, `pytest-asyncio`, `uv` for dependency management.

**Reference files:**
- Spec: `docs/spec.md`
- Design: `docs/superpowers/specs/2026-03-25-simmer-sdk-design.md`
- Skill source (orchestrator): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/SKILL.md
- Skill source (judge board): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-judge-board/SKILL.md
- Skill source (judge): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-judge/SKILL.md
- Skill source (generator): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-generator/SKILL.md
- Skill source (reflect): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-reflect/SKILL.md
- Skill source (setup): https://github.com/2389-research/claude-plugins/blob/main/simmer/skills/simmer-setup/SKILL.md

**Important:** All prompt templates must closely match the skill's prompt blocks. The skill is the reference implementation — when in doubt, match it verbatim. Prompts should be verbose and complete, not summarized.

**Environment:** `ANTHROPIC_API_KEY` must be set for integration tests. Use `uv run pytest` to run tests.

---

## File Structure

```
src/simmer_sdk/
├── __init__.py          # exports refine(), SimmerResult, IterationRecord
├── types.py             # SimmerResult, IterationRecord, StableWins, SetupBrief, JudgeOutput, JudgeDefinition
├── setup.py             # classify_problem(), auto_select_judge_mode(), build_brief()
├── prompts.py           # prompt templates for generator, judge, judge board, deliberation, synthesis
├── primitives.py        # judge primitive library (core, evaluator, exploration primitives)
├── generator.py         # dispatch_generator() via Agent SDK
├── judge.py             # dispatch_judge() via Agent SDK
├── judge_board.py       # compose_judges(), dispatch_board() — parallel scoring, deliberation, synthesis
├── reflect.py           # record_iteration(), track_best(), check_regression(), check_plateau(), track_stable_wins(), track_exploration()
└── refine.py            # refine() main loop orchestrator

tests/
├── conftest.py          # shared fixtures
├── test_types.py        # dataclass construction, composite calculation
├── test_setup.py        # problem classification, judge mode selection
├── test_reflect.py      # trajectory tracking, best-so-far, regression, stable wins
├── test_plateau.py      # plateau detection edge cases
├── test_judge_board.py  # consensus scoring, synthesis logic
└── test_integration.py  # full loop with real API (DND adventure hook)
```

---

### Task 1: Types — Data Classes

**Files:**
- Create: `src/simmer_sdk/types.py`
- Create: `tests/test_types.py`
- Modify: `src/simmer_sdk/__init__.py`

All data structures used across the SDK. These are pure data — no logic beyond composite calculation.

- [ ] **Step 1: Write tests for types**

```python
# tests/test_types.py
from simmer_sdk.types import (
    IterationRecord,
    SimmerResult,
    StableWins,
    SetupBrief,
    JudgeOutput,
    JudgeDefinition,
)


def test_iteration_record_composite():
    """Composite is average of scores, one decimal place."""
    record = IterationRecord(
        iteration=1,
        scores={"clarity": 7, "tone": 5, "cta": 4},
        key_change="specific problem statement",
        asi="Fix the CTA",
        regressed=False,
        judge_mode="single",
    )
    assert record.composite == 5.3


def test_iteration_record_empty_scores():
    """Empty scores produce 0.0 composite."""
    record = IterationRecord(
        iteration=0,
        scores={},
        key_change="seed",
        asi="",
        regressed=False,
        judge_mode="single",
    )
    assert record.composite == 0.0


def test_simmer_result_construction():
    """SimmerResult can be constructed with all fields."""
    from pathlib import Path

    record = IterationRecord(
        iteration=0,
        scores={"clarity": 5},
        key_change="seed",
        asi="",
        regressed=False,
        judge_mode="single",
    )
    result = SimmerResult(
        best_candidate="some text",
        best_iteration=0,
        best_scores={"clarity": 5},
        composite=5.0,
        trajectory=[record],
        stable_wins=["lookup table"],
        not_working=["verbose rules"],
        output_dir=Path("docs/simmer"),
    )
    assert result.best_iteration == 0
    assert result.composite == 5.0


def test_setup_brief_defaults():
    """SetupBrief has sensible defaults."""
    brief = SetupBrief(
        artifact="some text",
        artifact_type="single-file",
        criteria={"clarity": "reader understands immediately"},
        iterations=3,
        mode="from-paste",
    )
    assert brief.judge_mode == "auto"
    assert brief.output_dir == "docs/simmer"
    assert brief.evaluator is None
    assert brief.primary is None


def test_judge_output_construction():
    """JudgeOutput holds scores and ASI."""
    output = JudgeOutput(
        scores={"clarity": 7, "tone": 6},
        asi="Fix the opening paragraph",
        reasoning={"clarity": "Clear but verbose", "tone": "Too formal"},
    )
    assert output.composite == 6.5


def test_judge_definition():
    """JudgeDefinition holds name, lens, and optional primitives."""
    judge = JudgeDefinition(
        name="Craft",
        lens="Structure, pacing, narrative technique",
    )
    assert judge.name == "Craft"
    assert judge.primitives == []


def test_stable_wins_defaults():
    """StableWins starts empty."""
    wins = StableWins()
    assert wins.working == []
    assert wins.not_working == []
    assert wins.direction == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL — cannot import from `simmer_sdk.types`

- [ ] **Step 3: Implement types.py**

```python
# src/simmer_sdk/types.py
"""Data types for simmer-sdk."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IterationRecord:
    """Record of a single iteration's results."""

    iteration: int
    scores: dict[str, int]
    key_change: str
    asi: str
    regressed: bool
    judge_mode: str

    @property
    def composite(self) -> float:
        """Average of all criterion scores, one decimal place."""
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 1)


@dataclass
class SimmerResult:
    """Final result from a simmer refinement run."""

    best_candidate: str
    best_iteration: int
    best_scores: dict[str, int]
    composite: float
    trajectory: list[IterationRecord]
    stable_wins: list[str]
    not_working: list[str]
    output_dir: Path


@dataclass
class StableWins:
    """Tracks what's working and what's not across iterations."""

    working: list[str] = field(default_factory=list)
    not_working: list[str] = field(default_factory=list)
    direction: str = ""


@dataclass
class SetupBrief:
    """Configuration for a simmer run, produced by setup or caller."""

    artifact: str  # file path, directory path, or text content
    artifact_type: str  # "single-file" or "workspace"
    criteria: dict[str, str]  # {name: "what 10/10 looks like"}
    iterations: int
    mode: str  # "seedless", "from-file", "from-paste", "from-workspace"

    # Optional fields
    primary: str | None = None
    evaluator: str | None = None
    background: str | None = None
    output_contract: str | None = None
    validation_command: str | None = None
    search_space: str | None = None
    judge_mode: str = "auto"  # "auto", "single", "board"
    judge_panel: list[JudgeDefinition] | None = None
    output_dir: str = "docs/simmer"

    # Model configuration — every LLM call is independently configurable
    generator_model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-sonnet-4-6"
    clerk_model: str = "claude-haiku-4-5"


@dataclass
class JudgeOutput:
    """Output from a single judge or judge board."""

    scores: dict[str, int]
    asi: str
    reasoning: dict[str, str] = field(default_factory=dict)

    # Board-only fields
    deliberation_summary: str | None = None
    panel_working: list[str] | None = None
    panel_not_working: list[str] | None = None

    @property
    def composite(self) -> float:
        """Average of all criterion scores, one decimal place."""
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 1)


@dataclass
class JudgeDefinition:
    """Definition for a judge on a board panel."""

    name: str
    lens: str
    primitives: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Update __init__.py exports**

```python
# src/simmer_sdk/__init__.py
"""simmer-sdk: Programmatic simmer iterative refinement loop."""

from simmer_sdk.types import (
    IterationRecord,
    JudgeDefinition,
    JudgeOutput,
    SetupBrief,
    SimmerResult,
    StableWins,
)

__all__ = [
    "IterationRecord",
    "JudgeDefinition",
    "JudgeOutput",
    "SetupBrief",
    "SimmerResult",
    "StableWins",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_types.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/simmer_sdk/types.py src/simmer_sdk/__init__.py tests/test_types.py
git commit -m "feat: add core data types (IterationRecord, SimmerResult, SetupBrief, etc.)"
```

---

### Task 2: Setup — Problem Classification & Judge Mode Selection

**Files:**
- Create: `src/simmer_sdk/setup.py`
- Create: `tests/test_setup.py`

Pure Python logic matching `simmer-setup/SKILL.md` — problem class detection and judge mode auto-selection. No LLM calls.

- [ ] **Step 1: Write tests for setup**

```python
# tests/test_setup.py
from simmer_sdk.setup import classify_problem, auto_select_judge_mode, resolve_brief
from simmer_sdk.types import SetupBrief


class TestClassifyProblem:
    def test_workspace_with_evaluator_is_pipeline(self):
        brief = SetupBrief(
            artifact="/tmp/pipeline",
            artifact_type="workspace",
            criteria={"coverage": "high"},
            iterations=3,
            mode="from-workspace",
            evaluator="python evaluate.py",
        )
        assert classify_problem(brief) == "pipeline/engineering"

    def test_code_with_evaluator_is_code_testable(self):
        brief = SetupBrief(
            artifact="script.py",
            artifact_type="single-file",
            criteria={"correctness": "passes all tests"},
            iterations=3,
            mode="from-file",
            evaluator="pytest",
        )
        assert classify_problem(brief) == "code/testable"

    def test_seedless_prose_is_text_creative(self):
        brief = SetupBrief(
            artifact="Write a DND adventure hook",
            artifact_type="single-file",
            criteria={"tension": "high stakes"},
            iterations=3,
            mode="seedless",
        )
        assert classify_problem(brief) == "text/creative"

    def test_file_without_evaluator_is_text_creative(self):
        brief = SetupBrief(
            artifact="email.md",
            artifact_type="single-file",
            criteria={"clarity": "clear", "tone": "professional"},
            iterations=3,
            mode="from-file",
        )
        assert classify_problem(brief) == "text/creative"


class TestAutoSelectJudgeMode:
    def test_workspace_always_board(self):
        assert auto_select_judge_mode("pipeline/engineering", 2, None) == "board"

    def test_code_testable_always_board(self):
        assert auto_select_judge_mode("code/testable", 2, None) == "board"

    def test_text_creative_two_criteria_single(self):
        assert auto_select_judge_mode("text/creative", 2, None) == "single"

    def test_text_creative_three_criteria_board(self):
        assert auto_select_judge_mode("text/creative", 3, None) == "board"

    def test_user_override_single(self):
        assert auto_select_judge_mode("pipeline/engineering", 3, "single") == "single"

    def test_user_override_board(self):
        assert auto_select_judge_mode("text/creative", 1, "board") == "board"


class TestResolveBrief:
    def test_auto_judge_mode_resolved(self):
        brief = SetupBrief(
            artifact="email text",
            artifact_type="single-file",
            criteria={"clarity": "clear", "tone": "good"},
            iterations=3,
            mode="from-paste",
            judge_mode="auto",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "single"

    def test_explicit_judge_mode_preserved(self):
        brief = SetupBrief(
            artifact="email text",
            artifact_type="single-file",
            criteria={"clarity": "clear"},
            iterations=3,
            mode="from-paste",
            judge_mode="board",
        )
        resolved = resolve_brief(brief)
        assert resolved.judge_mode == "board"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL — cannot import from `simmer_sdk.setup`

- [ ] **Step 3: Implement setup.py**

```python
# src/simmer_sdk/setup.py
"""Problem classification and judge mode auto-selection.

Matches simmer-setup/SKILL.md logic. No LLM calls — pure Python.
"""

from __future__ import annotations

import copy

from simmer_sdk.types import SetupBrief


def classify_problem(brief: SetupBrief) -> str:
    """Classify the problem type from the brief.

    Matching simmer-setup/SKILL.md Phase 2 logic:
    - workspace + evaluator -> pipeline/engineering
    - evaluator present (non-workspace) -> code/testable
    - everything else -> text/creative
    """
    if brief.artifact_type == "workspace" and brief.evaluator:
        return "pipeline/engineering"
    if brief.evaluator:
        return "code/testable"
    return "text/creative"


def auto_select_judge_mode(
    problem_class: str,
    num_criteria: int,
    user_override: str | None,
) -> str:
    """Auto-select judge mode based on problem complexity.

    Matching simmer-setup/SKILL.md Judge Mode Auto-Selection table:
    - text/creative, <=2 criteria -> single
    - text/creative, 3+ criteria -> board
    - code/testable -> board
    - pipeline/engineering -> board
    - User override always wins
    """
    if user_override and user_override in ("single", "board"):
        return user_override

    if problem_class in ("code/testable", "pipeline/engineering"):
        return "board"

    # text/creative
    if num_criteria >= 3:
        return "board"
    return "single"


def resolve_brief(brief: SetupBrief) -> SetupBrief:
    """Resolve 'auto' fields in a SetupBrief to concrete values.

    Returns a new SetupBrief with all auto fields resolved.
    """
    resolved = copy.deepcopy(brief)

    problem_class = classify_problem(resolved)

    if resolved.judge_mode == "auto":
        user_override = None
    else:
        user_override = resolved.judge_mode

    resolved.judge_mode = auto_select_judge_mode(
        problem_class, len(resolved.criteria), user_override
    )

    return resolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_setup.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/simmer_sdk/setup.py tests/test_setup.py
git commit -m "feat: add setup module (problem classification, judge mode selection)"
```

---

### Task 3: Reflect — Trajectory Tracking & Analysis

**Files:**
- Create: `src/simmer_sdk/reflect.py`
- Create: `tests/test_reflect.py`
- Create: `tests/test_plateau.py`

Pure Python. Matches `simmer-reflect/SKILL.md` exactly. This is the bookkeeping engine — trajectory, best-so-far, regression detection, plateau detection, stable wins, exploration status.

- [ ] **Step 1: Write tests for reflect**

```python
# tests/test_reflect.py
from simmer_sdk.reflect import (
    record_iteration,
    find_best,
    check_regression,
    track_stable_wins,
    track_exploration,
    ReflectOutput,
)
from simmer_sdk.types import IterationRecord, StableWins


class TestRecordIteration:
    def test_creates_iteration_record(self):
        record = record_iteration(
            iteration=1,
            scores={"clarity": 7, "tone": 5},
            key_change="specific problem statement",
            asi="Fix the CTA",
            judge_mode="single",
            trajectory=[],
            primary=None,
        )
        assert record.iteration == 1
        assert record.composite == 6.0
        assert record.regressed is False

    def test_detects_regression(self):
        seed = IterationRecord(
            iteration=0, scores={"clarity": 5}, key_change="seed",
            asi="", regressed=False, judge_mode="single",
        )
        record = record_iteration(
            iteration=1,
            scores={"clarity": 3},
            key_change="rewrite attempt",
            asi="Try again",
            judge_mode="single",
            trajectory=[seed],
            primary=None,
        )
        assert record.regressed is True


class TestFindBest:
    def test_finds_highest_composite(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"a": 7}, key_change="fix",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=2, scores={"a": 5}, key_change="regressed",
                          asi="", regressed=True, judge_mode="single"),
        ]
        best_idx = find_best(trajectory, primary=None)
        assert best_idx == 1

    def test_primary_criterion_wins_over_composite(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"coverage": 3, "noise": 8},
                          key_change="seed", asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"coverage": 6, "noise": 4},
                          key_change="fix", asi="", regressed=False, judge_mode="single"),
        ]
        # iteration 1 has lower composite (5.0 vs 5.5) but higher coverage
        best_idx = find_best(trajectory, primary="coverage")
        assert best_idx == 1


class TestCheckRegression:
    def test_no_regression_on_improvement(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
        ]
        assert check_regression({"a": 5}, trajectory, primary=None) is False

    def test_regression_detected(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"a": 7}, key_change="fix",
                          asi="", regressed=False, judge_mode="single"),
        ]
        assert check_regression({"a": 5}, trajectory, primary=None) is True


class TestTrackStableWins:
    def test_empty_trajectory(self):
        wins = track_stable_wins([])
        assert wins.working == []
        assert wins.not_working == []

    def test_identifies_stable_element(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"a": 6}, key_change="added lookup table",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=2, scores={"a": 7}, key_change="refined examples",
                          asi="", regressed=False, judge_mode="single"),
        ]
        wins = track_stable_wins(trajectory)
        # "added lookup table" held through iter 2 without regression
        assert len(wins.working) >= 1

    def test_identifies_not_working(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"a": 6}, key_change="added verbose rules",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=2, scores={"a": 3}, key_change="expanded rules further",
                          asi="", regressed=True, judge_mode="single"),
        ]
        wins = track_stable_wins(trajectory)
        assert len(wins.not_working) >= 1


class TestTrackExploration:
    def test_no_search_space_returns_empty(self):
        result = track_exploration([], search_space=None)
        assert result == ""

    def test_tracks_configs(self):
        trajectory = [
            IterationRecord(iteration=0, scores={"a": 4}, key_change="seed",
                          asi="", regressed=False, judge_mode="single"),
            IterationRecord(iteration=1, scores={"a": 6}, key_change="switched to qwen 27b",
                          asi="", regressed=False, judge_mode="single"),
        ]
        result = track_exploration(trajectory, search_space="Models: qwen 4b/9b/27b")
        assert isinstance(result, str)
        assert len(result) > 0
```

- [ ] **Step 2: Write tests for plateau detection**

```python
# tests/test_plateau.py
from simmer_sdk.reflect import check_plateau
from simmer_sdk.types import IterationRecord


def _record(iteration: int, score: int, **kwargs) -> IterationRecord:
    """Helper to make test records."""
    return IterationRecord(
        iteration=iteration,
        scores={"main": score},
        key_change=kwargs.get("key_change", f"iter {iteration}"),
        asi="",
        regressed=kwargs.get("regressed", False),
        judge_mode="single",
    )


def test_not_enough_iterations():
    """Need at least seed + 3 iterations to detect plateau."""
    trajectory = [_record(0, 4), _record(1, 5), _record(2, 5)]
    assert check_plateau(trajectory, primary=None) is False


def test_improving_scores_no_plateau():
    trajectory = [_record(0, 4), _record(1, 5), _record(2, 6), _record(3, 7)]
    assert check_plateau(trajectory, primary=None) is False


def test_flat_scores_is_plateau():
    trajectory = [_record(0, 4), _record(1, 6), _record(2, 6), _record(3, 6)]
    assert check_plateau(trajectory, primary=None) is True


def test_oscillating_scores_is_plateau():
    trajectory = [
        _record(0, 4), _record(1, 6),
        _record(2, 5), _record(3, 6), _record(4, 5),
    ]
    assert check_plateau(trajectory, primary=None) is True


def test_late_improvement_no_plateau():
    trajectory = [_record(0, 4), _record(1, 6), _record(2, 6), _record(3, 7)]
    assert check_plateau(trajectory, primary=None) is False


def test_primary_criterion_used_for_plateau():
    trajectory = [
        IterationRecord(iteration=0, scores={"coverage": 4, "noise": 8},
                       key_change="seed", asi="", regressed=False, judge_mode="single"),
        IterationRecord(iteration=1, scores={"coverage": 6, "noise": 6},
                       key_change="fix", asi="", regressed=False, judge_mode="single"),
        IterationRecord(iteration=2, scores={"coverage": 6, "noise": 5},
                       key_change="try", asi="", regressed=False, judge_mode="single"),
        IterationRecord(iteration=3, scores={"coverage": 6, "noise": 7},
                       key_change="try2", asi="", regressed=False, judge_mode="single"),
    ]
    # Coverage has plateaued at 6, even though composite moved
    assert check_plateau(trajectory, primary="coverage") is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_reflect.py tests/test_plateau.py -v`
Expected: FAIL — cannot import from `simmer_sdk.reflect`

- [ ] **Step 4: Implement reflect.py**

```python
# src/simmer_sdk/reflect.py
"""Reflect module — trajectory tracking and analysis.

Matches simmer-reflect/SKILL.md. Pure Python, no LLM calls.
This is the only component that sees the full score history.
"""

from __future__ import annotations

from dataclasses import dataclass

from simmer_sdk.types import IterationRecord, StableWins


@dataclass
class ReflectOutput:
    """Output from the reflect step, returned to the orchestrator."""

    record: IterationRecord
    best_iteration: int
    best_composite: float
    regression: bool
    regression_rollback_to: int | None
    iterations_remaining: int
    asi: str
    exploration_status: str
    stable_wins: StableWins


def _get_score_for_comparison(
    record: IterationRecord, primary: str | None
) -> float:
    """Get the score to use for best-so-far comparison.

    If primary criterion is set, use that score. Otherwise use composite.
    """
    if primary and primary in record.scores:
        return float(record.scores[primary])
    return record.composite


def find_best(trajectory: list[IterationRecord], primary: str | None) -> int:
    """Find the index of the best iteration in the trajectory.

    Best is determined by primary criterion if set, composite otherwise.
    Ties broken by composite, then by earlier iteration.
    """
    if not trajectory:
        return 0

    best_idx = 0
    best_score = _get_score_for_comparison(trajectory[0], primary)
    best_composite = trajectory[0].composite

    for i, record in enumerate(trajectory[1:], 1):
        score = _get_score_for_comparison(record, primary)
        if score > best_score or (score == best_score and record.composite > best_composite):
            best_idx = i
            best_score = score
            best_composite = record.composite

    return best_idx


def check_regression(
    new_scores: dict[str, int],
    trajectory: list[IterationRecord],
    primary: str | None,
) -> bool:
    """Check if new scores represent a regression from best-so-far."""
    if not trajectory:
        return False

    best_idx = find_best(trajectory, primary)
    best_score = _get_score_for_comparison(trajectory[best_idx], primary)

    # Create a temporary record to compute the new score
    new_composite = round(sum(new_scores.values()) / len(new_scores), 1) if new_scores else 0.0
    if primary and primary in new_scores:
        new_score = float(new_scores[primary])
    else:
        new_score = new_composite

    return new_score < best_score


def record_iteration(
    iteration: int,
    scores: dict[str, int],
    key_change: str,
    asi: str,
    judge_mode: str,
    trajectory: list[IterationRecord],
    primary: str | None,
) -> IterationRecord:
    """Create an IterationRecord and determine if it regressed."""
    regressed = check_regression(scores, trajectory, primary)
    return IterationRecord(
        iteration=iteration,
        scores=scores,
        key_change=key_change,
        asi=asi,
        regressed=regressed,
        judge_mode=judge_mode,
    )


def check_plateau(
    trajectory: list[IterationRecord],
    primary: str | None,
) -> bool:
    """Detect plateau: 3 consecutive iterations without improvement.

    Matching simmer SKILL.md plateau detection:
    Need at least seed + 3 iterations (4 total records).
    Compare best of recent 3 against best before them.
    """
    if len(trajectory) < 4:
        return False

    recent = trajectory[-3:]
    earlier = trajectory[:-3]

    best_before = max(_get_score_for_comparison(t, primary) for t in earlier)
    best_recent = max(_get_score_for_comparison(t, primary) for t in recent)

    return best_recent <= best_before


def track_stable_wins(trajectory: list[IterationRecord]) -> StableWins:
    """Track what's been working and what hasn't across iterations.

    Matching simmer-reflect/SKILL.md Section 4.
    - Working: elements introduced in an iteration that held across subsequent iterations
    - Not working: elements associated with regressions
    """
    wins = StableWins()

    if len(trajectory) < 2:
        return wins

    # Track elements from non-seed, non-regressed iterations
    for i, record in enumerate(trajectory[1:], 1):
        if record.regressed:
            wins.not_working.append(
                f"{record.key_change} (tried iter {record.iteration}, regressed)"
            )
        elif i < len(trajectory) - 1:
            # Check if subsequent iterations regressed
            subsequent_regressed = any(
                t.regressed for t in trajectory[i + 1 :]
            )
            if not subsequent_regressed:
                wins.working.append(
                    f"{record.key_change} (added iter {record.iteration}, held)"
                )

    return wins


def track_exploration(
    trajectory: list[IterationRecord],
    search_space: str | None,
) -> str:
    """Track what's been explored vs untried in the search space.

    Matching simmer-reflect/SKILL.md Section 3.
    Only relevant for workspace mode with a defined search space.
    """
    if not search_space:
        return ""

    changes = [f"Iter {r.iteration}: {r.key_change}" for r in trajectory]
    return f"Search space: {search_space}\nTried so far:\n" + "\n".join(
        f"  - {c}" for c in changes
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_reflect.py tests/test_plateau.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/simmer_sdk/reflect.py tests/test_reflect.py tests/test_plateau.py
git commit -m "feat: add reflect module (trajectory, regression, plateau, stable wins)"
```

---

### Task 4: Primitives — Judge Primitive Library

**Files:**
- Create: `src/simmer_sdk/primitives.py`

The building blocks for constructing judges, extracted from the judge board skill. No tests needed — these are string constants used by the prompt builder.

- [ ] **Step 1: Implement primitives.py**

```python
# src/simmer_sdk/primitives.py
"""Judge primitive library.

Building blocks for constructing judges on a board panel.
Extracted from simmer-judge-board/SKILL.md "Judge Primitive Library" section.
These are proven capabilities that make judges more effective.
"""

# Core primitives — apply to all judges
CORE_PRIMITIVES = {
    "seed_calibration": (
        "Score via seed calibration — score the original first, anchor all "
        "subsequent iterations to it."
    ),
    "diagnose_before_scoring": (
        "Diagnose before scoring — read the candidate, evaluator output, and "
        "relevant code/config. Understand *why* things are the way they are "
        "before writing scores."
    ),
    "protect_high_scoring": (
        "Protect high-scoring elements — identify what's working and constrain "
        "your ASI to preserve it."
    ),
    "score_all_criteria": (
        "Score ALL criteria from your lens — every judge scores every criterion "
        "from their perspective, not one criterion per judge."
    ),
}

# Evaluator-present primitives
EVALUATOR_PRIMITIVES = {
    "cluster_failures": (
        "Cluster evaluator failures by type — near-misses (spelling), systematic "
        "gaps (whole category), noise (hallucinations). The pattern determines the fix."
    ),
    "verify_proper_nouns": (
        "Verify proper nouns from lossy sources — transcripts, OCR, and "
        "auto-captions garble names."
    ),
    "flag_stochasticity": (
        "Flag evaluator stochasticity — if the same config produces different "
        "results, small score changes may be noise."
    ),
}

# Exploration primitives — when problem involves search
EXPLORATION_PRIMITIVES = {
    "review_tried": (
        "Review what's been tried — check iteration history before suggesting "
        "more of the same."
    ),
    "flag_ceilings": (
        "Flag ceilings — if 2+ iterations tried the same type of change with "
        "no improvement, the bottleneck is structural."
    ),
    "research_if_stuck": (
        "Research if stuck — look up how similar problems are solved rather "
        "than guessing."
    ),
}


def get_primitives_for_judge(
    has_evaluator: bool,
    has_search_space: bool,
    custom_primitives: list[str] | None = None,
) -> list[str]:
    """Get the applicable primitive descriptions for a judge.

    Always includes core primitives. Adds evaluator and exploration
    primitives based on the problem context.
    """
    primitives = list(CORE_PRIMITIVES.values())

    if has_evaluator:
        primitives.extend(EVALUATOR_PRIMITIVES.values())

    if has_search_space:
        primitives.extend(EXPLORATION_PRIMITIVES.values())

    if custom_primitives:
        primitives.extend(custom_primitives)

    return primitives
```

- [ ] **Step 2: Commit**

```bash
git add src/simmer_sdk/primitives.py
git commit -m "feat: add judge primitive library"
```

---

### Task 5: Prompts — All Prompt Templates

**Files:**
- Create: `src/simmer_sdk/prompts.py`

Direct translations of the skill's prompt blocks. These are long and verbose — that's intentional. The skill's prompts are battle-tested and the SDK should match them closely.

- [ ] **Step 1: Implement prompts.py**

This is a large file. It contains prompt-building functions for every role. Each function takes structured data and returns the prompt string that gets passed to the Agent SDK.

The prompts must match the skill's prompt blocks closely. Read the skill files for reference:
- Generator prompt: `simmer-generator/SKILL.md` "Context You Receive" and "What To Do" sections
- Judge prompt: `simmer-judge/SKILL.md` full file — scoring rules, ASI format, calibration, evaluation modes
- Judge board panelist prompt: `simmer-judge-board/SKILL.md` "Panelist prompt template" section
- Deliberation prompt: `simmer-judge-board/SKILL.md` "Phase 2: Deliberation" section
- Synthesis: `simmer-judge-board/SKILL.md` "Phase 3: Synthesis" section

The file should contain these functions:

```python
def build_generator_prompt(
    iteration: int,
    artifact_type: str,  # "single-file" or "workspace"
    criteria: dict[str, str],
    current_candidate: str,
    asi: str,
    output_dir: str,
    background: str | None = None,
    panel_summary: str | None = None,
    output_contract: str | None = None,
    validation_command: str | None = None,
    search_space: str | None = None,
    exploration_status: str | None = None,
    workspace_path: str | None = None,
) -> str: ...

def build_judge_prompt(
    iteration: int,
    artifact_type: str,
    problem_class: str,  # "text/creative", "code/testable", "pipeline/engineering"
    criteria: dict[str, str],
    candidate: str,
    seed_candidate: str | None = None,
    seed_scores: dict[str, int] | None = None,
    evaluator_output: str | None = None,
    previous_asi: str | None = None,
    iteration_history: str | None = None,
    search_space: str | None = None,
    exploration_status: str | None = None,
    output_contract: str | None = None,
    candidate_path: str | None = None,
    evaluator_path: str | None = None,
    prior_candidate_paths: list[str] | None = None,
) -> str: ...

def build_board_panelist_prompt(
    judge_def: "JudgeDefinition",
    iteration: int,
    artifact_type: str,
    problem_class: str,
    criteria: dict[str, str],
    candidate: str,
    primitives: list[str],
    seed_candidate: str | None = None,
    seed_scores: dict[str, int] | None = None,
    evaluator_output: str | None = None,
    previous_asi: str | None = None,
    iteration_history: str | None = None,
    search_space: str | None = None,
    exploration_status: str | None = None,
    background: str | None = None,
    previous_deliberation: str | None = None,
    candidate_path: str | None = None,
    evaluator_path: str | None = None,
    prior_candidate_paths: list[str] | None = None,
) -> str: ...

def build_deliberation_prompt(
    judge_name: str,
    own_output: str,
    other_outputs: list[tuple[str, str]],  # [(name, scores_and_reasoning)]
) -> str: ...

def build_synthesis_prompt(
    criteria: dict[str, str],
    all_judge_outputs: list[tuple[str, str]],  # [(name, full_output_with_asi)]
    deliberation_results: list[tuple[str, str]],  # [(name, deliberation)]
    artifact_type: str,
    search_space: str | None = None,
    stable_wins: "StableWins | None" = None,
) -> str: ...

def build_board_composition_prompt(
    artifact_summary: str,
    criteria: dict[str, str],
    problem_class: str,
    has_evaluator: bool,
    background: str | None = None,
    search_space: str | None = None,
) -> str: ...
```

Each function builds a prompt that matches the corresponding skill's prompt template. The prompts include:
- Full context discipline rules (what the role receives and does NOT receive)
- Scoring rules (1-10 integer, seed calibration, composite calculation)
- ASI format requirements (single, specific, concrete, actionable)
- Investigation steps for judges (read files before scoring)
- Output format requirements (parseable by the orchestrator)

**IMPORTANT:** Read the actual skill files (linked in the plan header) and translate their prompt blocks faithfully. Do not summarize or abbreviate. The prompts should be verbose — that's how the skill works.

- [ ] **Step 2: Commit**

```bash
git add src/simmer_sdk/prompts.py
git commit -m "feat: add prompt templates (generator, judge, board, deliberation, synthesis)"
```

---

### Task 6: Generator — Subagent Dispatch

**Files:**
- Create: `src/simmer_sdk/generator.py`

Dispatches the generator subagent via Claude Agent SDK. The generator gets tool access (`Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep`) and an isolated context (no scores, no previous candidates, no evaluator output).

- [ ] **Step 1: Implement generator.py**

```python
# src/simmer_sdk/generator.py
"""Generator subagent dispatch via Claude Agent SDK.

Matches simmer-generator/SKILL.md. The generator receives:
- Current candidate, criteria, ASI, background, panel summary
- Does NOT receive: scores, previous candidates, evaluator output

Tools: Read, Edit, Write, Bash, Glob, Grep
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

from simmer_sdk.prompts import build_generator_prompt
from simmer_sdk.types import SetupBrief


@dataclass
class GeneratorOutput:
    """What the generator returns to the orchestrator."""

    candidate: str  # the improved artifact text
    report: str  # what changed and why (2-3 sentences)
    files_modified: list[str]  # workspace mode only


async def dispatch_generator(
    brief: SetupBrief,
    iteration: int,
    current_candidate: str,
    asi: str,
    panel_summary: str | None = None,
    exploration_status: str | None = None,
) -> GeneratorOutput:
    """Dispatch a generator subagent and collect its output.

    The generator produces an improved version of the artifact based
    on the judge's ASI feedback.
    """
    prompt = build_generator_prompt(
        iteration=iteration,
        artifact_type=brief.artifact_type,
        criteria=brief.criteria,
        current_candidate=current_candidate,
        asi=asi,
        output_dir=brief.output_dir,
        background=brief.background,
        panel_summary=panel_summary,
        output_contract=brief.output_contract,
        validation_command=brief.validation_command,
        search_space=brief.search_space,
        exploration_status=exploration_status,
        workspace_path=brief.artifact if brief.artifact_type == "workspace" else None,
    )

    # Determine tools based on artifact type
    if brief.artifact_type == "workspace":
        tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
    else:
        tools = ["Read", "Write", "Glob"]

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model=brief.generator_model,
            allowed_tools=tools,
            permission_mode="bypassPermissions",
            cwd=brief.artifact if brief.artifact_type == "workspace" else None,
            max_turns=20,
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result

    return _parse_generator_output(result_text, brief)


def _parse_generator_output(
    result_text: str, brief: SetupBrief
) -> GeneratorOutput:
    """Parse the generator's text output into structured data."""
    # The generator should report what changed — extract that
    # For single-file mode, the candidate is written to a file
    # For workspace mode, changes are made in place

    # Extract report (last paragraph or section after the candidate)
    lines = result_text.strip().split("\n")
    report = result_text[:500] if result_text else "No report provided"

    # Extract file list if mentioned
    files_modified = []
    for line in lines:
        if line.strip().startswith("Files modified:"):
            files_str = line.split(":", 1)[1].strip()
            files_modified = [f.strip() for f in files_str.split(",")]

    return GeneratorOutput(
        candidate=result_text,
        report=report,
        files_modified=files_modified,
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/simmer_sdk/generator.py
git commit -m "feat: add generator subagent dispatch"
```

---

### Task 7: Judge — Single Judge Subagent Dispatch

**Files:**
- Create: `src/simmer_sdk/judge.py`

Dispatches a single judge subagent via Agent SDK. Judges get read-only tool access (`Read`, `Grep`, `Glob`) for investigation. Context discipline varies by problem class.

- [ ] **Step 1: Implement judge.py**

```python
# src/simmer_sdk/judge.py
"""Single judge subagent dispatch via Claude Agent SDK.

Matches simmer-judge/SKILL.md. Context discipline:
- Text/creative: candidate + criteria + seed reference only (no intermediate scores)
- Code/pipeline: above + evaluator output + previous ASI + iteration history

Tools: Read, Grep, Glob (read-only investigation)
"""

from __future__ import annotations

import re

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

from simmer_sdk.prompts import build_judge_prompt
from simmer_sdk.types import JudgeOutput, SetupBrief, IterationRecord


async def dispatch_judge(
    brief: SetupBrief,
    problem_class: str,
    iteration: int,
    candidate: str,
    seed_candidate: str | None = None,
    seed_scores: dict[str, int] | None = None,
    evaluator_output: str | None = None,
    previous_asi: str | None = None,
    iteration_history: str | None = None,
    exploration_status: str | None = None,
    candidate_path: str | None = None,
    evaluator_path: str | None = None,
    prior_candidate_paths: list[str] | None = None,
) -> JudgeOutput:
    """Dispatch a single judge subagent and parse its output."""

    prompt = build_judge_prompt(
        iteration=iteration,
        artifact_type=brief.artifact_type,
        problem_class=problem_class,
        criteria=brief.criteria,
        candidate=candidate,
        seed_candidate=seed_candidate,
        seed_scores=seed_scores,
        evaluator_output=evaluator_output,
        previous_asi=previous_asi,
        iteration_history=iteration_history,
        search_space=brief.search_space,
        exploration_status=exploration_status,
        output_contract=brief.output_contract,
        candidate_path=candidate_path,
        evaluator_path=evaluator_path,
        prior_candidate_paths=prior_candidate_paths,
    )

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model=brief.judge_model,
            allowed_tools=["Read", "Grep", "Glob"],
            permission_mode="bypassPermissions",
            cwd=brief.artifact if brief.artifact_type == "workspace" else None,
            max_turns=10,
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result

    return parse_judge_output(result_text, brief.criteria)


def parse_judge_output(
    result_text: str, criteria: dict[str, str]
) -> JudgeOutput:
    """Parse judge output into structured JudgeOutput.

    Expected format (from simmer-judge/SKILL.md):
    ITERATION [N] SCORES:
      [criterion]: [N]/10 — [reasoning] — [specific improvement]
    COMPOSITE: [N.N]/10

    ASI (highest-leverage direction):
    [text]
    """
    scores: dict[str, int] = {}
    reasoning: dict[str, str] = {}
    asi = ""

    # Parse scores: look for patterns like "criterion_name: N/10"
    score_pattern = re.compile(
        r"^\s*(\w[\w\s]*?):\s*(\d{1,2})/10\s*[—–-]\s*(.+?)(?:\s*[—–-]\s*.+)?$",
        re.MULTILINE,
    )
    for match in score_pattern.finditer(result_text):
        name = match.group(1).strip().lower().replace(" ", "_")
        score = int(match.group(2))
        reason = match.group(3).strip()
        # Match against known criteria names
        for criterion_key in criteria:
            if criterion_key.lower().replace(" ", "_") == name or name in criterion_key.lower():
                scores[criterion_key] = min(max(score, 1), 10)
                reasoning[criterion_key] = reason
                break

    # Parse ASI: everything after "ASI" header
    asi_match = re.search(
        r"ASI\s*\(.*?\):\s*\n(.*)",
        result_text,
        re.DOTALL | re.IGNORECASE,
    )
    if asi_match:
        asi = asi_match.group(1).strip()

    return JudgeOutput(scores=scores, asi=asi, reasoning=reasoning)
```

- [ ] **Step 2: Commit**

```bash
git add src/simmer_sdk/judge.py
git commit -m "feat: add single judge subagent dispatch"
```

---

### Task 8: Judge Board — Board Composition, Parallel Dispatch, Deliberation, Synthesis

**Files:**
- Create: `src/simmer_sdk/judge_board.py`
- Create: `tests/test_judge_board.py`

The most complex module. Matches `simmer-judge-board/SKILL.md`:
1. Compose 3 judges with diverse lenses (LLM call or custom panel)
2. Dispatch all 3 in parallel for independent scoring
3. Run one deliberation round (each sees others' scores, not ASI)
4. Synthesize consensus scores + single ASI

- [ ] **Step 1: Write tests for board consensus logic**

```python
# tests/test_judge_board.py
from simmer_sdk.judge_board import compute_consensus_scores


class TestConsensusScores:
    def test_all_agree_uses_median(self):
        """When all judges within 1 point, use median."""
        judge_scores = [
            {"clarity": 7, "tone": 6},
            {"clarity": 7, "tone": 7},
            {"clarity": 8, "tone": 6},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7  # median of 7,7,8
        assert consensus["tone"] == 6  # median of 6,7,6

    def test_spread_uses_median(self):
        """When 2+ point spread, still use median."""
        judge_scores = [
            {"clarity": 4},
            {"clarity": 7},
            {"clarity": 8},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_two_judges(self):
        """Two judges: average rounded to nearest int."""
        judge_scores = [
            {"clarity": 6},
            {"clarity": 8},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7  # median of 6,8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_judge_board.py -v`
Expected: FAIL — cannot import from `simmer_sdk.judge_board`

- [ ] **Step 3: Implement judge_board.py**

This module handles:
- `compose_judges()` — uses an LLM call to design 3 judges for the specific problem, OR uses a custom panel from the brief
- `dispatch_board()` — orchestrates the three phases (independent scoring, deliberation, synthesis)
- `compute_consensus_scores()` — pure Python median calculation
- `_dispatch_panelist()` — sends one judge via Agent SDK
- `_dispatch_deliberation()` — sends one deliberation prompt via Agent SDK
- `_synthesize()` — clerk LLM call to distill single ASI from all judges

Key implementation notes:
- Independent scoring dispatches 3 Agent SDK queries (can be run concurrently with `anyio.create_task_group`)
- Deliberation dispatches 3 more queries — each judge sees others' scores but NOT ASI
- Synthesis is a single LLM call (clerk model, no tools needed) that produces consensus scores + one focused ASI
- Output format is identical to single judge (`JudgeOutput`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_judge_board.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/simmer_sdk/judge_board.py tests/test_judge_board.py
git commit -m "feat: add judge board (composition, deliberation, synthesis)"
```

---

### Task 9: Orchestrator — Main Refinement Loop

**Files:**
- Create: `src/simmer_sdk/refine.py`
- Modify: `src/simmer_sdk/__init__.py`

The main `refine()` function. Matches `SKILL.md` (orchestrator) — the full loop: setup → seed judgment → iterate (generate → evaluate → judge → reflect) → return result.

- [ ] **Step 1: Implement refine.py**

```python
# src/simmer_sdk/refine.py
"""Main simmer refinement loop.

Matches SKILL.md orchestrator. This is the public entry point.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from simmer_sdk.types import (
    IterationRecord,
    SetupBrief,
    SimmerResult,
    StableWins,
)
from simmer_sdk.setup import classify_problem, resolve_brief
from simmer_sdk.generator import dispatch_generator
from simmer_sdk.judge import dispatch_judge
from simmer_sdk.judge_board import dispatch_board
from simmer_sdk.reflect import (
    record_iteration,
    find_best,
    check_plateau,
    track_stable_wins,
    track_exploration,
)


async def refine(
    # Required
    artifact: str | Path,
    criteria: dict[str, str],

    # Optional — evaluation
    evaluator: str | None = None,
    primary: str | None = None,

    # Optional — loop control
    iterations: int = 3,
    mode: str = "auto",

    # Optional — judge configuration
    judge_mode: str = "auto",
    judge_panel: list[dict] | None = None,

    # Optional — workspace
    output_dir: str | Path = "docs/simmer",
    background: str | None = None,
    output_contract: str | None = None,
    validation_command: str | None = None,
    search_space: str | None = None,

    # Optional — models
    generator_model: str = "claude-sonnet-4-6",
    judge_model: str = "claude-sonnet-4-6",
    clerk_model: str = "claude-haiku-4-5",

    # Optional — callbacks
    on_iteration: Callable | None = None,
    on_plateau: Callable | None = None,
) -> SimmerResult:
    """Run the simmer iterative refinement loop.

    This is the main entry point for the SDK.
    See docs/spec.md for full API documentation.
    """
    # Build the setup brief from parameters
    artifact_str = str(artifact)
    artifact_type = _detect_artifact_type(artifact_str, mode)

    if mode == "auto":
        mode = _detect_mode(artifact_str, artifact_type)

    from simmer_sdk.types import JudgeDefinition
    parsed_panel = None
    if judge_panel:
        parsed_panel = [
            JudgeDefinition(name=j["name"], lens=j["lens"])
            for j in judge_panel
        ]

    brief = SetupBrief(
        artifact=artifact_str,
        artifact_type=artifact_type,
        criteria=criteria,
        iterations=iterations,
        mode=mode,
        primary=primary,
        evaluator=evaluator,
        background=background,
        output_contract=output_contract,
        validation_command=validation_command,
        search_space=search_space,
        judge_mode=judge_mode,
        judge_panel=parsed_panel,
        output_dir=str(output_dir),
        generator_model=generator_model,
        judge_model=judge_model,
        clerk_model=clerk_model,
    )

    # Resolve auto fields
    brief = resolve_brief(brief)
    problem_class = classify_problem(brief)

    # Create output directory
    out_path = Path(brief.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Load or initialize the candidate
    current_candidate = _load_initial_candidate(brief)

    trajectory: list[IterationRecord] = []
    seed_candidate = current_candidate
    seed_scores: dict[str, int] | None = None
    stable_wins = StableWins()
    previous_asi = ""
    panel_summary: str | None = None

    # --- Iteration 0: Judge the seed ---
    evaluator_output = None
    if brief.evaluator:
        evaluator_output = _run_evaluator(brief)

    if brief.judge_mode == "board":
        judge_output = await dispatch_board(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output,
            candidate_path=str(out_path / "iteration-0-candidate.md"),
        )
    else:
        judge_output = await dispatch_judge(
            brief=brief,
            problem_class=problem_class,
            iteration=0,
            candidate=current_candidate,
            evaluator_output=evaluator_output,
            candidate_path=str(out_path / "iteration-0-candidate.md"),
        )

    seed_scores = judge_output.scores
    record = record_iteration(
        iteration=0,
        scores=judge_output.scores,
        key_change="seed",
        asi=judge_output.asi,
        judge_mode=brief.judge_mode,
        trajectory=trajectory,
        primary=brief.primary,
    )
    trajectory.append(record)
    previous_asi = judge_output.asi

    if judge_output.deliberation_summary:
        panel_summary = judge_output.deliberation_summary

    if on_iteration:
        await _call_callback(on_iteration, record, trajectory)

    # Write seed candidate
    if brief.artifact_type == "single-file":
        (out_path / "iteration-0-candidate.md").write_text(current_candidate)

    # --- Iterations 1-N ---
    for i in range(1, brief.iterations + 1):
        # Determine which candidate the generator works from
        best_idx = find_best(trajectory, brief.primary)
        if trajectory[-1].regressed:
            # Rollback: use best candidate, not latest
            current_candidate = _load_candidate_at(brief, out_path, best_idx)

        # Step 1: Generator
        gen_output = await dispatch_generator(
            brief=brief,
            iteration=i,
            current_candidate=current_candidate,
            asi=previous_asi,
            panel_summary=panel_summary,
            exploration_status=track_exploration(trajectory, brief.search_space),
        )

        current_candidate = gen_output.candidate

        # Write candidate file (single-file mode)
        if brief.artifact_type == "single-file":
            (out_path / f"iteration-{i}-candidate.md").write_text(
                current_candidate
            )

        # Step 2: Run evaluator
        evaluator_output = None
        if brief.evaluator:
            evaluator_output = _run_evaluator(brief)

        # Build iteration history for code/pipeline judges
        iteration_history = None
        if problem_class != "text/creative":
            iteration_history = _build_iteration_history(trajectory)

        # Step 3: Judge
        if brief.judge_mode == "board":
            judge_output = await dispatch_board(
                brief=brief,
                problem_class=problem_class,
                iteration=i,
                candidate=current_candidate,
                seed_candidate=seed_candidate,
                seed_scores=seed_scores,
                evaluator_output=evaluator_output,
                previous_asi=previous_asi,
                iteration_history=iteration_history,
                exploration_status=track_exploration(trajectory, brief.search_space),
                stable_wins=stable_wins,
                candidate_path=str(out_path / f"iteration-{i}-candidate.md"),
                prior_candidate_paths=[
                    str(out_path / f"iteration-{j}-candidate.md")
                    for j in range(i)
                ],
            )
        else:
            judge_output = await dispatch_judge(
                brief=brief,
                problem_class=problem_class,
                iteration=i,
                candidate=current_candidate,
                seed_candidate=seed_candidate,
                seed_scores=seed_scores,
                evaluator_output=evaluator_output,
                previous_asi=previous_asi if problem_class != "text/creative" else None,
                iteration_history=iteration_history,
                exploration_status=track_exploration(trajectory, brief.search_space) if problem_class != "text/creative" else None,
                candidate_path=str(out_path / f"iteration-{i}-candidate.md"),
                prior_candidate_paths=[
                    str(out_path / f"iteration-{j}-candidate.md")
                    for j in range(i)
                ] if problem_class != "text/creative" else None,
            )

        # Step 4: Reflect
        record = record_iteration(
            iteration=i,
            scores=judge_output.scores,
            key_change=gen_output.report[:60],
            asi=judge_output.asi,
            judge_mode=brief.judge_mode,
            trajectory=trajectory,
            primary=brief.primary,
        )
        trajectory.append(record)
        previous_asi = judge_output.asi
        stable_wins = track_stable_wins(trajectory)

        if judge_output.deliberation_summary:
            panel_summary = judge_output.deliberation_summary

        if on_iteration:
            await _call_callback(on_iteration, record, trajectory)

        # Plateau detection
        if check_plateau(trajectory, brief.primary):
            if brief.judge_mode == "single" and on_plateau:
                upgrade = await _call_callback(
                    on_plateau,
                    trajectory[find_best(trajectory, brief.primary)].composite,
                    len(trajectory) - find_best(trajectory, brief.primary),
                )
                if upgrade:
                    brief.judge_mode = "board"
                    brief.iterations = max(brief.iterations, i + 2)

    # --- Output ---
    best_idx = find_best(trajectory, brief.primary)
    best_record = trajectory[best_idx]
    best_candidate = _load_candidate_at(brief, out_path, best_idx)

    # Write result
    if brief.artifact_type == "single-file":
        (out_path / "result.md").write_text(best_candidate)

    return SimmerResult(
        best_candidate=best_candidate,
        best_iteration=best_record.iteration,
        best_scores=best_record.scores,
        composite=best_record.composite,
        trajectory=trajectory,
        stable_wins=stable_wins.working,
        not_working=stable_wins.not_working,
        output_dir=out_path,
    )


# --- Helper functions ---

def _detect_artifact_type(artifact: str, mode: str) -> str:
    """Detect whether artifact is single-file or workspace."""
    if mode == "from-workspace":
        return "workspace"
    p = Path(artifact)
    if p.is_dir():
        return "workspace"
    return "single-file"


def _detect_mode(artifact: str, artifact_type: str) -> str:
    """Detect the mode from the artifact."""
    if artifact_type == "workspace":
        return "from-workspace"
    p = Path(artifact)
    if p.is_file():
        return "from-file"
    # If it's not a file path, treat as seedless or pasted content
    if len(artifact) > 200 or "\n" in artifact:
        return "from-paste"
    return "seedless"


def _load_initial_candidate(brief: SetupBrief) -> str:
    """Load the initial candidate text."""
    if brief.mode == "from-file":
        return Path(brief.artifact).read_text()
    if brief.mode == "from-paste":
        return brief.artifact
    if brief.mode == "seedless":
        return brief.artifact  # description, generator will create first candidate
    if brief.mode == "from-workspace":
        return f"[Workspace at {brief.artifact}]"
    return brief.artifact


def _load_candidate_at(
    brief: SetupBrief, out_path: Path, iteration: int
) -> str:
    """Load the candidate from a specific iteration."""
    if brief.artifact_type == "single-file":
        candidate_file = out_path / f"iteration-{iteration}-candidate.md"
        if candidate_file.exists():
            return candidate_file.read_text()
    return ""


def _run_evaluator(brief: SetupBrief) -> str:
    """Run the evaluator command and capture output."""
    try:
        result = subprocess.run(
            brief.evaluator,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout for long evaluators
            cwd=brief.artifact if brief.artifact_type == "workspace" else None,
        )
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        if result.returncode != 0:
            output += f"EXIT CODE: {result.returncode}\n"
        return output
    except subprocess.TimeoutExpired:
        return "EVALUATOR TIMEOUT: Command exceeded 1 hour limit."
    except Exception as e:
        return f"EVALUATOR ERROR: {e}"


def _build_iteration_history(trajectory: list[IterationRecord]) -> str:
    """Build condensed iteration history for code/pipeline judges."""
    lines = []
    for record in trajectory:
        scores_str = ", ".join(f"{k}: {v}" for k, v in record.scores.items())
        lines.append(
            f"Iteration {record.iteration}: [{scores_str}] "
            f"Composite: {record.composite} — {record.key_change}"
            f"{' (REGRESSED)' if record.regressed else ''}"
        )
    return "\n".join(lines)


async def _call_callback(callback: Callable, *args):
    """Call a callback, handling both sync and async."""
    import asyncio
    result = callback(*args)
    if asyncio.iscoroutine(result):
        return await result
    return result
```

- [ ] **Step 2: Update __init__.py to export refine**

Add to `src/simmer_sdk/__init__.py`:

```python
from simmer_sdk.refine import refine

# Add to __all__
__all__ = [
    "refine",
    # ... existing exports ...
]
```

- [ ] **Step 3: Commit**

```bash
git add src/simmer_sdk/refine.py src/simmer_sdk/__init__.py
git commit -m "feat: add refine() orchestrator (main loop)"
```

---

### Task 10: Integration Test — Full Loop

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_integration.py`

End-to-end test using real API calls. DND adventure hook, seedless, 2 iterations. Uses haiku to keep costs low.

**Requires:** `ANTHROPIC_API_KEY` environment variable set.

- [ ] **Step 1: Create conftest.py**

```python
# tests/conftest.py
"""Shared test fixtures."""

import os
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests that make real API calls (deselect with '-m \"not integration\"')"
    )


@pytest.fixture
def has_api_key():
    """Skip test if no API key available."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
```

- [ ] **Step 2: Create integration test**

```python
# tests/test_integration.py
"""Integration tests — real API calls, real simmer loop.

Run with: ANTHROPIC_API_KEY=... uv run pytest tests/test_integration.py -v -m integration
"""

import pytest
import tempfile
from pathlib import Path

from simmer_sdk import refine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dnd_adventure_hook_seedless(has_api_key):
    """Full simmer loop: seedless DND adventure hook, 2 iterations, haiku."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await refine(
            artifact="A level 5 party explores a haunted lighthouse on a rocky coast. The keeper vanished a week ago and ships have been crashing on the rocks since.",
            criteria={
                "narrative_tension": "escalating stakes with time pressure and consequences",
                "player_agency": "genuine decision points that change the outcome, not a railroad",
                "specificity": "concrete names, locations, sensory details, not generic fantasy",
            },
            iterations=2,
            mode="seedless",
            judge_mode="single",
            output_dir=Path(tmpdir) / "simmer",
            generator_model="claude-haiku-4-5",
            judge_model="claude-haiku-4-5",
        )

        # Basic structural assertions
        assert result.best_candidate, "Should produce a candidate"
        assert len(result.best_candidate) > 100, "Candidate should be substantial"
        assert result.composite > 0, "Should have non-zero composite score"
        assert len(result.trajectory) == 3, "Should have seed + 2 iterations"
        assert result.trajectory[0].key_change == "seed"
        assert result.best_iteration >= 0

        # All iterations should have scores for all criteria
        for record in result.trajectory:
            assert len(record.scores) > 0, f"Iteration {record.iteration} has no scores"

        # Output files should exist
        simmer_dir = Path(tmpdir) / "simmer"
        assert (simmer_dir / "iteration-0-candidate.md").exists()
        assert (simmer_dir / "result.md").exists()

        # Print trajectory for manual inspection
        print("\n--- Trajectory ---")
        for record in result.trajectory:
            print(
                f"Iter {record.iteration}: {record.scores} "
                f"(composite: {record.composite}) — {record.key_change}"
            )
        print(f"Best: iteration {result.best_iteration} ({result.composite}/10)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_refinement_from_paste(has_api_key):
    """Simmer a pasted email, 2 iterations, haiku."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await refine(
            artifact=(
                "Hi, I wanted to reach out about our new product. "
                "It does a lot of things and I think you'd like it. "
                "Let me know if you want to chat."
            ),
            criteria={
                "value_clarity": "reader immediately understands the specific problem solved",
                "response_likelihood": "CTA is so low-friction the recipient replies without thinking",
            },
            iterations=2,
            mode="from-paste",
            output_dir=Path(tmpdir) / "simmer",
            generator_model="claude-haiku-4-5",
            judge_model="claude-haiku-4-5",
        )

        assert result.best_candidate
        assert result.composite > 0
        assert len(result.trajectory) == 3

        print("\n--- Trajectory ---")
        for record in result.trajectory:
            print(
                f"Iter {record.iteration}: {record.scores} "
                f"(composite: {record.composite}) — {record.key_change}"
            )
```

- [ ] **Step 3: Run unit tests to confirm they still pass**

Run: `uv run pytest tests/ -v -m "not integration"`
Expected: All unit tests PASS

- [ ] **Step 4: Run integration test**

Run: `ANTHROPIC_API_KEY=... uv run pytest tests/test_integration.py -v -m integration -s`
Expected: Both tests PASS, trajectory printed to console

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_integration.py
git commit -m "feat: add integration tests (DND hook, email refinement)"
```

---

## Summary

| Task | Module | Tests | LLM Calls |
|------|--------|-------|-----------|
| 1 | types.py | test_types.py | None |
| 2 | setup.py | test_setup.py | None |
| 3 | reflect.py | test_reflect.py, test_plateau.py | None |
| 4 | primitives.py | — | None |
| 5 | prompts.py | — | None |
| 6 | generator.py | — | Agent SDK |
| 7 | judge.py | — | Agent SDK |
| 8 | judge_board.py | test_judge_board.py | Agent SDK |
| 9 | refine.py | — | Orchestrator |
| 10 | — | test_integration.py | Full loop |

Tasks 1-5 are pure Python with no API calls — fast to build and test. Tasks 6-9 require the Agent SDK. Task 10 validates everything end-to-end.

Build order matters: each task depends on the previous ones. Types → Setup → Reflect → Primitives → Prompts → Generator → Judge → Board → Orchestrator → Integration test.
