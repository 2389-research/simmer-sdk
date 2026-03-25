from __future__ import annotations

import pytest

from simmer_sdk.types import IterationRecord, StableWins
from simmer_sdk.reflect import (
    find_best,
    check_regression,
    record_iteration,
    track_stable_wins,
    track_exploration,
)


def _make_record(
    iteration: int,
    scores: dict[str, int],
    key_change: str = "",
    asi: str = "",
    regressed: bool = False,
    judge_mode: str = "single",
) -> IterationRecord:
    return IterationRecord(
        iteration=iteration,
        scores=scores,
        key_change=key_change,
        asi=asi,
        regressed=regressed,
        judge_mode=judge_mode,
    )


class TestRecordIteration:
    def test_creates_record(self):
        trajectory: list[IterationRecord] = []
        record = record_iteration(
            iteration=1,
            scores={"clarity": 7, "tone": 6},
            key_change="Changed intro",
            asi="better",
            judge_mode="single",
            trajectory=trajectory,
            primary=None,
        )
        assert record.iteration == 1
        assert record.scores == {"clarity": 7, "tone": 6}
        assert record.key_change == "Changed intro"
        assert record.asi == "better"
        assert record.judge_mode == "single"
        assert record.regressed is False

    def test_detects_regression(self):
        seed = _make_record(0, {"clarity": 8, "tone": 8}, key_change="seed")
        good = _make_record(1, {"clarity": 9, "tone": 9}, key_change="improve")
        trajectory = [seed, good]

        record = record_iteration(
            iteration=2,
            scores={"clarity": 5, "tone": 5},
            key_change="Bad change",
            asi="worse",
            judge_mode="single",
            trajectory=trajectory,
            primary=None,
        )
        assert record.regressed is True

    def test_no_regression_on_improvement(self):
        seed = _make_record(0, {"clarity": 5, "tone": 5}, key_change="seed")
        trajectory = [seed]

        record = record_iteration(
            iteration=1,
            scores={"clarity": 7, "tone": 7},
            key_change="Improvement",
            asi="better",
            judge_mode="single",
            trajectory=trajectory,
            primary=None,
        )
        assert record.regressed is False


class TestFindBest:
    def test_highest_composite(self):
        t = [
            _make_record(0, {"a": 5}),
            _make_record(1, {"a": 7}),
            _make_record(2, {"a": 6}),
        ]
        assert find_best(t, primary=None) == 1

    def test_primary_criterion_wins_over_composite(self):
        # iteration 1: primary=9, composite=7 (secondary=5)
        # iteration 2: primary=6, composite=8 (secondary=10)
        t = [
            _make_record(0, {"primary": 5, "secondary": 5}),
            _make_record(1, {"primary": 9, "secondary": 5}),
            _make_record(2, {"primary": 6, "secondary": 10}),
        ]
        # Without primary: composite of iter2 = 8 > iter1 composite = 7
        assert find_best(t, primary=None) == 2
        # With primary: iter1 has primary=9 > iter2 primary=6
        assert find_best(t, primary="primary") == 1

    def test_earlier_iteration_wins_ties(self):
        t = [
            _make_record(0, {"a": 7}),
            _make_record(1, {"a": 7}),
            _make_record(2, {"a": 7}),
        ]
        assert find_best(t, primary=None) == 0

    def test_primary_tiebreaker_composite(self):
        # Both iter1 and iter2 have same primary score; composite breaks tie
        t = [
            _make_record(0, {"primary": 5, "other": 5}),
            _make_record(1, {"primary": 8, "other": 6}),  # composite=7
            _make_record(2, {"primary": 8, "other": 8}),  # composite=8
        ]
        # iter2 has higher composite, so wins
        assert find_best(t, primary="primary") == 2


class TestCheckRegression:
    def test_no_regression_on_improvement(self):
        seed = _make_record(0, {"clarity": 5})
        trajectory = [seed]
        assert check_regression({"clarity": 7}, trajectory, primary=None) is False

    def test_regression_detected(self):
        seed = _make_record(0, {"clarity": 8})
        good = _make_record(1, {"clarity": 9})
        trajectory = [seed, good]
        assert check_regression({"clarity": 3}, trajectory, primary=None) is True

    def test_no_regression_equal_scores(self):
        seed = _make_record(0, {"clarity": 7})
        trajectory = [seed]
        assert check_regression({"clarity": 7}, trajectory, primary=None) is False

    def test_regression_with_primary(self):
        # Best has primary=9, new has primary=6 => regression
        seed = _make_record(0, {"primary": 9, "other": 5})
        trajectory = [seed]
        assert check_regression({"primary": 6, "other": 9}, trajectory, primary="primary") is True

    def test_no_regression_empty_trajectory(self):
        assert check_regression({"clarity": 5}, [], primary=None) is False


class TestTrackStableWins:
    def test_empty_trajectory(self):
        result = track_stable_wins([])
        assert isinstance(result, StableWins)
        assert result.working == []
        assert result.not_working == []

    def test_identifies_stable_element(self):
        # key_change from iter 1 held through iter 2 (no regression after)
        seed = _make_record(0, {"a": 5}, key_change="seed")
        iter1 = _make_record(1, {"a": 7}, key_change="improve_tone", regressed=False)
        iter2 = _make_record(2, {"a": 8}, key_change="improve_cta", regressed=False)
        trajectory = [seed, iter1, iter2]
        result = track_stable_wins(trajectory)
        # improve_tone held through (iter2 didn't regress), so it's working
        assert "improve_tone" in result.working

    def test_identifies_not_working(self):
        # iter1 change caused a regression at iter2
        seed = _make_record(0, {"a": 5}, key_change="seed")
        iter1 = _make_record(1, {"a": 7}, key_change="risky_change", regressed=False)
        iter2 = _make_record(2, {"a": 3}, key_change="another", regressed=True)
        trajectory = [seed, iter1, iter2]
        result = track_stable_wins(trajectory)
        # The change that led to a regression iteration is in not_working
        assert "risky_change" in result.not_working or "another" in result.not_working

    def test_seed_not_in_working(self):
        seed = _make_record(0, {"a": 5}, key_change="seed")
        trajectory = [seed]
        result = track_stable_wins(trajectory)
        assert "seed" not in result.working


class TestTrackExploration:
    def test_no_search_space_returns_empty(self):
        seed = _make_record(0, {"a": 5}, key_change="seed")
        result = track_exploration([seed], search_space=None)
        assert result == ""

    def test_tracks_configs(self):
        seed = _make_record(0, {"a": 5}, key_change="seed")
        iter1 = _make_record(1, {"a": 7}, key_change="config_A")
        iter2 = _make_record(2, {"a": 6}, key_change="config_B")
        trajectory = [seed, iter1, iter2]
        result = track_exploration(trajectory, search_space="tone: [formal, casual]")
        assert isinstance(result, str)
        assert len(result) > 0
