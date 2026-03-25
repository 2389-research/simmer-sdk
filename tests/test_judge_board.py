from simmer_sdk.judge_board import compute_consensus_scores


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
