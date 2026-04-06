# ABOUTME: Tests for primitives.py — verifies get_primitives_for_judge returns the right primitives.
# ABOUTME: Checks core, evaluator, exploration, and custom primitive inclusion/exclusion logic.

from simmer_sdk.primitives import (
    CORE_PRIMITIVES,
    EVALUATOR_PRIMITIVES,
    EXPLORATION_PRIMITIVES,
    get_primitives_for_judge,
)


class TestGetPrimitivesForJudge:
    """Tests for get_primitives_for_judge."""

    def test_returns_list(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=False)
        assert isinstance(result, list)

    def test_always_includes_core_primitives(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=False)
        for primitive in CORE_PRIMITIVES.values():
            assert primitive in result

    def test_core_only_when_no_evaluator_no_search_space(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=False)
        assert len(result) == len(CORE_PRIMITIVES)

    def test_includes_evaluator_primitives_when_has_evaluator(self):
        result = get_primitives_for_judge(has_evaluator=True, has_search_space=False)
        for primitive in EVALUATOR_PRIMITIVES.values():
            assert primitive in result

    def test_excludes_evaluator_primitives_when_no_evaluator(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=False)
        for primitive in EVALUATOR_PRIMITIVES.values():
            assert primitive not in result

    def test_includes_exploration_primitives_when_has_search_space(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=True)
        for primitive in EXPLORATION_PRIMITIVES.values():
            assert primitive in result

    def test_excludes_exploration_primitives_when_no_search_space(self):
        result = get_primitives_for_judge(has_evaluator=False, has_search_space=False)
        for primitive in EXPLORATION_PRIMITIVES.values():
            assert primitive not in result

    def test_includes_all_sets_when_both_flags_true(self):
        result = get_primitives_for_judge(has_evaluator=True, has_search_space=True)
        expected_count = (
            len(CORE_PRIMITIVES) + len(EVALUATOR_PRIMITIVES) + len(EXPLORATION_PRIMITIVES)
        )
        assert len(result) == expected_count

    def test_custom_primitives_appended(self):
        custom = ["my custom primitive one", "my custom primitive two"]
        result = get_primitives_for_judge(
            has_evaluator=False,
            has_search_space=False,
            custom_primitives=custom,
        )
        assert "my custom primitive one" in result
        assert "my custom primitive two" in result

    def test_custom_primitives_come_after_standard(self):
        custom = ["last one"]
        result = get_primitives_for_judge(
            has_evaluator=False,
            has_search_space=False,
            custom_primitives=custom,
        )
        # Core primitives should appear before custom
        core_last_idx = max(result.index(p) for p in CORE_PRIMITIVES.values())
        custom_idx = result.index("last one")
        assert custom_idx > core_last_idx

    def test_none_custom_primitives_not_included(self):
        result_no_custom = get_primitives_for_judge(
            has_evaluator=False,
            has_search_space=False,
            custom_primitives=None,
        )
        result_default = get_primitives_for_judge(
            has_evaluator=False,
            has_search_space=False,
        )
        assert result_no_custom == result_default

    def test_empty_custom_primitives_not_added(self):
        result = get_primitives_for_judge(
            has_evaluator=False,
            has_search_space=False,
            custom_primitives=[],
        )
        assert len(result) == len(CORE_PRIMITIVES)

    def test_primitives_are_strings(self):
        result = get_primitives_for_judge(has_evaluator=True, has_search_space=True)
        assert all(isinstance(p, str) for p in result)

    def test_core_count_is_four(self):
        # Core primitives dict has exactly 4 entries — document the contract
        assert len(CORE_PRIMITIVES) == 4

    def test_evaluator_count_is_three(self):
        assert len(EVALUATOR_PRIMITIVES) == 3

    def test_exploration_count_is_three(self):
        assert len(EXPLORATION_PRIMITIVES) == 3
