# ABOUTME: Tests for the trajectory_view projection — no API, no streamlit UI.

"""Tests that the flat JSONL event log projects into the correct run tree.

Generates a synthetic event log via TrajectoryLogger (the real writer), then
parses it back with load_run and asserts the iteration/session/turn grouping,
tool nesting, ordering, token sums, and the training-transcript projection.
"""

from __future__ import annotations

from simmer_sdk.trajectory import (
    TrajectoryLogger,
    begin_session,
    emit,
    set_active_logger,
    set_iteration,
)
from simmer_sdk.trajectory_view import load_run, session_as_messages


def _llm_event(model, in_tok, out_tok, content, stop="end_turn", system=None, messages=None):
    return dict(
        request={"model": model, "system": system, "messages": messages or [{"role": "user", "content": "hi"}]},
        response={"content": content, "stop_reason": stop,
                  "usage": {"input_tokens": in_tok, "output_tokens": out_tok}},
        duration_s=0.1,
    )


async def _write_synthetic_log(tmp_path):
    """A 2-iteration board-ish run: generator + 2 judges + clerk per round."""
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)

    logger.emit("run", config={"judge_mode": "board", "generator_model": "m"})

    # seed iteration 0: just a judge looking
    set_iteration(0)
    begin_session("judge")
    emit("tool_call", name="Read", input={"path": "spec"}, result="x", result_orig_len=1, truncated=False, duration_s=0.01)
    emit("llm_call", **_llm_event("m", 100, 20, [{"type": "text", "text": "seed judged"}]))
    logger.emit("iteration", iteration=0, scores={"a": 5, "b": 6}, composite=5.5,
                key_change="seed", asi="do X", regressed=False)

    for i in (1, 2):
        set_iteration(i)
        # generator session: writes a candidate
        begin_session("generator")
        emit("llm_call", **_llm_event("m", 200, 50, [{"type": "tool_use", "name": "Write", "input": {}}], stop="tool_use"))
        emit("tool_call", name="Write", input={"path": "cand"}, result="ok", result_orig_len=2, truncated=False, duration_s=0.02)
        emit("llm_call", **_llm_event("m", 210, 30, [{"type": "text", "text": "done"}]))
        # two judge sessions (concurrent in real runs)
        for _ in range(2):
            begin_session("judge")
            emit("tool_call", name="Read", input={"path": "cand"}, result="...", result_orig_len=3, truncated=False, duration_s=0.01)
            emit("llm_call", **_llm_event("m", 150, 25, [{"type": "text", "text": "scored"}]))
        # clerk synthesis
        begin_session("clerk")
        emit("llm_call", **_llm_event("m", 120, 40, [{"type": "text", "text": "consensus"}]))
        logger.emit("iteration", iteration=i, scores={"a": 7, "b": 8}, composite=7.5,
                    key_change=f"change {i}", asi=f"next {i}", regressed=False)

    logger.emit("outcome", best_iteration=2, best_scores={"a": 7, "b": 8}, composite=7.5,
                total_usage={"estimated_cost_usd": 0.01})
    await logger.aclose()
    set_active_logger(None)
    return logger.file_path


async def test_run_view_structure(tmp_path):
    path = await _write_synthetic_log(tmp_path)
    view = load_run(path)

    assert view.config["judge_mode"] == "board"
    assert view.outcome["best_iteration"] == 2

    # iterations 0, 1, 2 in order
    idxs = [it.iteration for it in view.iterations]
    assert idxs == [0, 1, 2]

    seed, it1, it2 = view.iterations
    assert seed.composite == 5.5
    assert it1.scores == {"a": 7, "b": 8}

    # iteration 1: generator + 2 judges + clerk = 4 distinct sessions
    roles = sorted(s.role for s in it1.sessions)
    assert roles == ["clerk", "generator", "judge", "judge"]
    assert len(it1.sessions) == 4
    # judges are distinct sessions (not merged)
    judge_sids = {s.session_id for s in it1.sessions if s.role == "judge"}
    assert len(judge_sids) == 2


async def test_turn_ordering_and_tool_nesting(tmp_path):
    path = await _write_synthetic_log(tmp_path)
    view = load_run(path)
    it1 = next(it for it in view.iterations if it.iteration == 1)
    gen = next(s for s in it1.sessions if s.role == "generator")

    # generator: llm_call(tool_use) -> tool_call(Write) -> llm_call(text), ordered by seq
    types = [t["type"] for t in gen.turns]
    assert types == ["llm_call", "tool_call", "llm_call"]
    seqs = [t["seq"] for t in gen.turns]
    assert seqs == sorted(seqs)
    assert len(gen.tool_calls) == 1 and gen.tool_calls[0]["name"] == "Write"


async def test_token_sums(tmp_path):
    path = await _write_synthetic_log(tmp_path)
    view = load_run(path)
    it1 = next(it for it in view.iterations if it.iteration == 1)
    gen = next(s for s in it1.sessions if s.role == "generator")
    assert gen.input_tokens == 200 + 210
    assert gen.output_tokens == 50 + 30

    by_role = view.cost_by_role()
    # 2 generator sessions across iters 1 and 2
    assert by_role["generator"]["sessions"] == 2
    # 1 (seed) + 2 + 2 = 5 judge sessions
    assert by_role["judge"]["sessions"] == 5


async def test_training_transcript_projection(tmp_path):
    path = await _write_synthetic_log(tmp_path)
    view = load_run(path)
    it1 = next(it for it in view.iterations if it.iteration == 1)
    gen = next(s for s in it1.sessions if s.role == "generator")
    msgs = session_as_messages(gen)
    # user message(s) + an assistant turn per llm_call
    assert any(m["role"] == "user" for m in msgs)
    assert sum(1 for m in msgs if m["role"] == "assistant") == 2


def test_torn_tail_is_skipped(tmp_path):
    # A truncated final line (simulated crash) must not break parsing.
    p = tmp_path / "torn.jsonl"
    p.write_text(
        '{"v":1,"type":"run","run_id":"r","seq":0,"config":{}}\n'
        '{"v":1,"type":"iteration","iteration":0,"seq":1,"composite":5.0}\n'
        '{"v":1,"type":"llm_call","iteration":0,"se'  # torn
    )
    view = load_run(p)
    assert view.run_id == "r"
    assert len(view.iterations) == 1  # the complete iteration parsed; torn line skipped
