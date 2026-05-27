# ABOUTME: Headless render test for the Streamlit viewer via AppTest (no browser).

"""Run viewer/app.py headlessly with streamlit's AppTest against a real log and
assert the render path executes without raising and produces expected content.

Skipped if streamlit isn't installed (it's an optional 'viewer' extra).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from simmer_sdk.trajectory import (  # noqa: E402
    TrajectoryLogger,
    begin_session,
    emit,
    set_active_logger,
    set_iteration,
)

APP = str(Path(__file__).resolve().parents[1] / "viewer" / "app.py")


async def _make_log(dirpath: str) -> str:
    lg = TrajectoryLogger(log_dir=dirpath)
    await lg.start()
    set_active_logger(lg)
    lg.emit("run", config={"judge_mode": "board", "generator_model": "m"})
    set_iteration(0)
    begin_session("judge")
    emit("llm_call",
         request={"model": "m", "system": "s", "messages": [{"role": "user", "content": "hi"}]},
         response={"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn",
                   "usage": {"input_tokens": 10, "output_tokens": 3}},
         duration_s=0.1)
    lg.emit("iteration", iteration=0, scores={"a": 5}, composite=5.0,
            key_change="seed", asi="x", regressed=False)
    set_iteration(1)
    begin_session("generator")
    emit("tool_call", name="Write", input={"path": "c"}, result="ok",
         result_orig_len=2, truncated=False, duration_s=0.01)
    emit("llm_call",
         request={"model": "m", "messages": [{"role": "user", "content": "go"}]},
         response={"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn",
                   "usage": {"input_tokens": 20, "output_tokens": 5}},
         duration_s=0.1)
    lg.emit("iteration", iteration=1, scores={"a": 8}, composite=8.0,
            key_change="c1", asi="n", regressed=False)
    lg.emit("outcome", best_iteration=1, best_scores={"a": 8}, composite=8.0,
            total_usage={"estimated_cost_usd": 0.0})
    await lg.aclose()
    set_active_logger(None)
    return lg.file_path


def test_viewer_renders_without_error(tmp_path):
    asyncio.run(_make_log(str(tmp_path)))
    # The app reads SIMMER_TRAJ_DIR when no CLI arg is given (AppTest passes none).
    os.environ["SIMMER_TRAJ_DIR"] = str(tmp_path)
    try:
        at = AppTest.from_file(APP, default_timeout=30).run()
    finally:
        os.environ.pop("SIMMER_TRAJ_DIR", None)

    assert not at.exception, f"viewer raised: {at.exception}"
    # Title rendered
    titles = [t.value for t in at.title]
    assert any("Simmer Trajectory Inspector" in t for t in titles)
    # The score table (dataframe) rendered — proves the render path ran on a loaded run
    assert len(at.dataframe) >= 1
