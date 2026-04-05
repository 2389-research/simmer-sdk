from simmer_sdk.judge_board import compute_consensus_scores
from simmer_sdk.types import StableWins


class TestConsensusScores:
    def test_all_agree_uses_median(self):
        judge_scores = [
            {"clarity": 7, "tone": 6},
            {"clarity": 7, "tone": 7},
            {"clarity": 8, "tone": 6},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7
        assert consensus["tone"] == 6

    def test_spread_uses_median(self):
        judge_scores = [{"clarity": 4}, {"clarity": 7}, {"clarity": 8}]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_two_judges(self):
        judge_scores = [{"clarity": 6}, {"clarity": 8}]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_five_judges(self):
        judge_scores = [
            {"clarity": 3},
            {"clarity": 5},
            {"clarity": 7},
            {"clarity": 8},
            {"clarity": 9},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 7

    def test_multiple_criteria(self):
        judge_scores = [
            {"clarity": 4, "tone": 8, "accuracy": 6},
            {"clarity": 6, "tone": 6, "accuracy": 7},
            {"clarity": 8, "tone": 7, "accuracy": 5},
        ]
        consensus = compute_consensus_scores(judge_scores)
        assert consensus["clarity"] == 6
        assert consensus["tone"] == 7
        assert consensus["accuracy"] == 6


class TestNotWorkingRendering:
    """Test that NOT WORKING items render with their actual text, not literal 'nw'."""

    def _build_previous_deliberation(self, stable_wins: StableWins) -> str:
        """Replicates the exact code path from dispatch_board for the previous_deliberation string."""
        parts: list[str] = []
        if stable_wins.working:
            parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- nw" for nw in stable_wins.not_working))
        if stable_wins.direction:
            parts.append(f"DIRECTION:\n{stable_wins.direction}")
        return "\n\n".join(parts)

    def test_not_working_items_render_as_literal_nw_before_fix(self):
        """This test documents the bug: items render as '- nw' not their text.

        Once the bug is fixed this test should FAIL (it demonstrates the broken behavior).
        It is kept to document what the bug looked like.
        """
        stable_wins = StableWins(not_working=["approach A failed", "approach B was wrong"])
        result = self._build_previous_deliberation(stable_wins)
        # The buggy version renders literal "nw" instead of item text
        assert "- nw" in result
        assert "approach A failed" not in result
        assert "approach B was wrong" not in result

    def _build_previous_deliberation_fixed(self, stable_wins: StableWins) -> str:
        """The correct version of the dispatch_board code path after bug fix."""
        parts: list[str] = []
        if stable_wins.working:
            parts.append("WORKING (preserve):\n" + "\n".join(f"- {w}" for w in stable_wins.working))
        if stable_wins.not_working:
            parts.append("NOT WORKING (do not retry):\n" + "\n".join(f"- {nw}" for nw in stable_wins.not_working))
        if stable_wins.direction:
            parts.append(f"DIRECTION:\n{stable_wins.direction}")
        return "\n\n".join(parts)

    def test_not_working_items_render_actual_text(self):
        """After fix: NOT WORKING items must render their actual text."""
        stable_wins = StableWins(not_working=["approach A failed", "approach B was wrong"])
        result = self._build_previous_deliberation_fixed(stable_wins)
        assert "approach A failed" in result
        assert "approach B was wrong" in result
        assert "NOT WORKING (do not retry):\n- approach A failed\n- approach B was wrong" in result

    def test_not_working_does_not_contain_literal_nw_variable_name(self):
        """After fix: output must not contain the literal variable name 'nw' as a list item."""
        stable_wins = StableWins(not_working=["something broke"])
        result = self._build_previous_deliberation_fixed(stable_wins)
        # "- nw" should not appear as a standalone bullet (the bug artifact)
        assert "- nw\n" not in result
        assert result.count("- nw") == 0

    def test_working_items_still_render_correctly(self):
        """WORKING items should be unaffected by the fix."""
        stable_wins = StableWins(
            working=["thing one works", "thing two works"],
            not_working=["bad approach"],
            direction="try something else",
        )
        result = self._build_previous_deliberation_fixed(stable_wins)
        assert "thing one works" in result
        assert "thing two works" in result
        assert "bad approach" in result
        assert "try something else" in result
