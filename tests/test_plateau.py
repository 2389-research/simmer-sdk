from __future__ import annotations

import pytest

from simmer_sdk.types import IterationRecord
from simmer_sdk.reflect import check_plateau


def _record(iteration: int, score: int, **kwargs) -> IterationRecord:
    return IterationRecord(
        iteration=iteration,
        scores={"main": score},
        key_change=kwargs.get("key_change", f"iter {iteration}"),
        asi="",
        regressed=kwargs.get("regressed", False),
        judge_mode="single",
    )


class TestCheckPlateau:
    def test_not_enough_iterations(self):
        # Fewer than 4 records should return False
        assert check_plateau([], primary=None) is False
        assert check_plateau([_record(0, 5)], primary=None) is False
        assert check_plateau([_record(0, 5), _record(1, 6)], primary=None) is False
        assert check_plateau([_record(0, 5), _record(1, 6), _record(2, 7)], primary=None) is False

    def test_exactly_four_records_not_plateau(self):
        trajectory = [
            _record(0, 5),
            _record(1, 6),
            _record(2, 7),
            _record(3, 8),
        ]
        assert check_plateau(trajectory, primary=None) is False

    def test_improving_scores_no_plateau(self):
        trajectory = [
            _record(0, 5),
            _record(1, 6),
            _record(2, 7),
            _record(3, 9),  # recent best is higher
        ]
        assert check_plateau(trajectory, primary=None) is False

    def test_flat_scores_is_plateau(self):
        trajectory = [
            _record(0, 7),
            _record(1, 7),
            _record(2, 7),
            _record(3, 7),
        ]
        assert check_plateau(trajectory, primary=None) is True

    def test_oscillating_scores_is_plateau(self):
        # Best before last 3 = 8; best of last 3 = 7 (oscillating, never beats early peak)
        trajectory = [
            _record(0, 5),
            _record(1, 8),  # best_before = 8
            _record(2, 6),
            _record(3, 7),
            _record(4, 6),  # last 3: 6,7,6 => best_recent=7 <= best_before=8
        ]
        assert check_plateau(trajectory, primary=None) is True

    def test_late_improvement_no_plateau(self):
        # Best before last 3 = 8; best of last 3 = 10
        trajectory = [
            _record(0, 5),
            _record(1, 8),
            _record(2, 6),
            _record(3, 7),
            _record(4, 10),  # late breakthrough
        ]
        assert check_plateau(trajectory, primary=None) is False

    def test_primary_criterion_used_for_plateau(self):
        # Using primary="main": best_before (from first record) = main=9
        # last 3 records have main=5,6,7 => plateau since 7 < 9
        trajectory = [
            _record(0, 9),  # best_before main=9
            _record(1, 5),
            _record(2, 6),
            _record(3, 7),
        ]
        assert check_plateau(trajectory, primary="main") is True

    def test_primary_criterion_improvement_no_plateau(self):
        # best_before main=6; last 3 have main values 7,8,9 => no plateau
        trajectory = [
            _record(0, 6),
            _record(1, 7),
            _record(2, 8),
            _record(3, 9),
        ]
        assert check_plateau(trajectory, primary="main") is False
