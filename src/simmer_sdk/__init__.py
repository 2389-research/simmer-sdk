# ABOUTME: Public API surface for simmer-sdk.
# ABOUTME: Exports refine(), types, and callback protocols.

from simmer_sdk.types import (
    IterationRecord,
    JudgeDefinition,
    JudgeOutput,
    OnIterationCallback,
    OnPlateauCallback,
    SetupBrief,
    SimmerResult,
    StableWins,
)
from simmer_sdk.refine import refine

__all__ = [
    "IterationRecord",
    "JudgeDefinition",
    "JudgeOutput",
    "OnIterationCallback",
    "OnPlateauCallback",
    "SetupBrief",
    "SimmerResult",
    "refine",
]
