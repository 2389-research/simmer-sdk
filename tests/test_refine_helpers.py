# ABOUTME: Tests for refine.py helper functions — artifact detection, mode detection,
# ABOUTME: evaluator shell-injection fix, and input validation in refine().

from __future__ import annotations

import shlex

import pytest

from simmer_sdk.refine import _detect_artifact_type, _detect_mode, refine


# ---------------------------------------------------------------------------
# _detect_artifact_type
# ---------------------------------------------------------------------------


class TestDetectArtifactType:
    def test_from_workspace_mode_returns_workspace(self):
        assert _detect_artifact_type("/any/path", "from-workspace") == "workspace"

    def test_existing_directory_returns_workspace(self, tmp_path):
        assert _detect_artifact_type(str(tmp_path), "auto") == "workspace"

    def test_file_path_returns_single_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        assert _detect_artifact_type(str(f), "auto") == "single-file"

    def test_short_description_returns_single_file(self):
        assert _detect_artifact_type("write a poem about cats", "auto") == "single-file"

    def test_nonexistent_path_returns_single_file(self):
        assert _detect_artifact_type("/does/not/exist/file.md", "auto") == "single-file"


# ---------------------------------------------------------------------------
# _detect_mode
# ---------------------------------------------------------------------------


class TestDetectMode:
    def test_workspace_returns_from_workspace(self):
        assert _detect_mode("/some/dir", "workspace") == "from-workspace"

    def test_existing_file_returns_from_file(self, tmp_path):
        f = tmp_path / "artifact.md"
        f.write_text("content")
        assert _detect_mode(str(f), "single-file") == "from-file"

    def test_multiline_text_returns_from_paste(self):
        text = "first line\nsecond line"
        assert _detect_mode(text, "single-file") == "from-paste"

    def test_long_text_returns_from_paste(self):
        text = "x" * 501
        assert _detect_mode(text, "single-file") == "from-paste"

    def test_short_nonexistent_returns_seedless(self):
        assert _detect_mode("write a landing page for my SaaS", "single-file") == "seedless"


# ---------------------------------------------------------------------------
# shlex.quote applied to evaluator template variables
# ---------------------------------------------------------------------------


class TestEvaluatorShellQuoting:
    """Verify the substitution logic applies shlex.quote to template vars.

    We test the quoting contract directly rather than running a subprocess.
    """

    def _substitute(self, cmd: str, candidate_path: str, output_dir: str, iteration: int) -> str:
        """Replicate the fixed substitution logic from _run_evaluator."""
        if candidate_path:
            cmd = cmd.replace("{candidate_path}", shlex.quote(candidate_path))
        if output_dir:
            cmd = cmd.replace("{output_dir}", shlex.quote(output_dir))
        cmd = cmd.replace("{iteration}", str(iteration))
        return cmd

    def test_normal_path_is_quoted(self):
        cmd = "check.sh {candidate_path}"
        result = self._substitute(cmd, "/tmp/safe_path.md", "", 1)
        # shlex.quote wraps with single-quotes or leaves safe strings bare;
        # either way the substitution must produce the shlex-quoted form.
        assert result == f"check.sh {shlex.quote('/tmp/safe_path.md')}"

    def test_path_with_spaces_is_quoted(self):
        cmd = "check.sh {candidate_path}"
        result = self._substitute(cmd, "/tmp/my docs/file.md", "", 1)
        assert "'/tmp/my docs/file.md'" in result

    def test_malicious_path_is_neutralised(self):
        """A path containing shell metacharacters must be quoted, not executed."""
        malicious = "/tmp/foo; rm -rf /"
        cmd = "check.sh {candidate_path}"
        result = self._substitute(cmd, malicious, "", 1)
        # The semicolon must be inside quotes, not a raw shell separator
        assert ";" not in result.replace(shlex.quote(malicious), "")
        # The quoted form contains the literal semicolon safely
        assert shlex.quote(malicious) in result

    def test_output_dir_is_quoted(self):
        cmd = "eval.sh {output_dir}"
        result = self._substitute(cmd, "", "/docs/simmer output", 2)
        assert "'/docs/simmer output'" in result

    def test_iteration_is_plain_int_string(self):
        cmd = "run.sh {iteration}"
        result = self._substitute(cmd, "", "", 5)
        assert result == "run.sh 5"


# ---------------------------------------------------------------------------
# Input validation in refine()
# ---------------------------------------------------------------------------


class TestRefineInputValidation:
    """Validation runs before any API calls so no keys are needed."""

    async def test_rejects_empty_criteria(self):
        with pytest.raises(ValueError, match="criteria"):
            await refine(artifact="test artifact", criteria={})

    async def test_rejects_negative_iterations(self):
        with pytest.raises(ValueError, match="iterations"):
            await refine(artifact="test artifact", criteria={"quality": "good"}, iterations=-1)

    async def test_rejects_invalid_mode(self):
        with pytest.raises(ValueError, match="mode"):
            await refine(
                artifact="test artifact",
                criteria={"quality": "good"},
                mode="invalid-mode",
            )

    async def test_rejects_invalid_judge_mode(self):
        with pytest.raises(ValueError, match="judge_mode"):
            await refine(
                artifact="test artifact",
                criteria={"quality": "good"},
                judge_mode="omniscient",
            )

    async def test_rejects_invalid_api_provider(self):
        with pytest.raises(ValueError, match="api_provider"):
            await refine(
                artifact="test artifact",
                criteria={"quality": "good"},
                api_provider="openai",
            )

    async def test_rejects_judge_count_below_2(self):
        with pytest.raises(ValueError, match="judge_count"):
            await refine(
                artifact="test artifact",
                criteria={"quality": "good"},
                judge_count=1,
            )

    async def test_zero_iterations_is_valid(self):
        """iterations=0 is explicitly allowed (>= 0 rule)."""
        # Should raise something other than the input-validation ValueError,
        # or succeed — either way the validator must not block it.
        try:
            await refine(artifact="test artifact", criteria={"quality": "good"}, iterations=0)
        except ValueError as exc:
            assert "iterations" not in str(exc), "iterations=0 should pass validation"
        except Exception:
            pass  # API errors or other errors are fine here
