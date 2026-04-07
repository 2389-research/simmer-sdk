# ABOUTME: Core data types for the simmer SDK.
# ABOUTME: Defines IterationRecord, SimmerResult, SetupBrief, JudgeOutput, and callback types.

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Union


@dataclass
class IterationRecord:
    """Record of a single iteration's results."""

    iteration: int
    scores: dict[str, int]
    key_change: str
    asi: str
    regressed: bool
    judge_mode: str
    composite: float = field(init=False)

    def __post_init__(self):
        if self.scores:
            self.composite = round(sum(self.scores.values()) / len(self.scores), 1)
        else:
            self.composite = 0.0


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
    """Tracks what's working/not working across iterations."""

    working: list[str] = field(default_factory=list)
    not_working: list[str] = field(default_factory=list)
    direction: str = ""


@dataclass
class JudgeDefinition:
    """Definition for a judge on a board."""

    name: str
    lens: str
    primitives: list[str] = field(default_factory=list)


@dataclass
class SetupBrief:
    """Configuration for a simmer run."""

    artifact: str
    artifact_type: str
    criteria: dict[str, str]
    iterations: int
    mode: str
    primary: str | None = None
    evaluator: str | None = None
    background: str | None = None
    output_contract: str | None = None
    validation_command: str | None = None
    search_space: str | None = None
    judge_mode: str = "auto"
    judge_panel: list[JudgeDefinition] | None = None
    judge_count: int = 3
    output_dir: str = "docs/simmer"
    generator_model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-sonnet-4-6"
    clerk_model: str = "claude-haiku-4-5"

    # API provider configuration
    api_provider: str = "anthropic"  # "anthropic" | "bedrock" | "ollama"
    aws_access_key: str | None = None
    aws_secret_key: str | None = None
    aws_region: str | None = None
    ollama_url: str = "http://localhost:11434"
    judge_preamble: str | None = None  # Optional preamble injected into judge prompts
    custom_tools: dict | None = None  # Custom tools for local agent {"name": {"function": fn, "schema": {...}}}


@dataclass
class JudgeOutput:
    """Output from a judge."""

    scores: dict[str, int]
    asi: str
    reasoning: dict[str, str] = field(default_factory=dict)
    deliberation_summary: str | None = None
    panel_working: list[str] | None = None
    panel_not_working: list[str] | None = None
    raw_text: str = ""

    @property
    def composite(self) -> float:
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 1)


# ---------------------------------------------------------------------------
# Callback type aliases
# ---------------------------------------------------------------------------

# Called after each iteration with (record, trajectory, trajectory_table).
OnIterationCallback = Callable[
    ["IterationRecord", list["IterationRecord"], str],
    Union[None, Awaitable[None]],
]

# Called when a plateau is detected with (trajectory,). Return True to upgrade
# judge_mode to "board" and extend the run by 2 iterations.
OnPlateauCallback = Callable[
    [list["IterationRecord"]],
    Union[bool, Awaitable[bool]],
]
