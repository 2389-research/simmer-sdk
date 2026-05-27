# ABOUTME: Unit tests for trajectory logging — no API calls, uses fakes.

"""Tests for the trajectory event logger (TrajectoryLogger + boundary capture)."""

from __future__ import annotations

import asyncio
import json

import pytest

from simmer_sdk.trajectory import (
    TrajectoryLogger,
    begin_session,
    emit,
    get_active_logger,
    set_active_logger,
    set_iteration,
    wrap_client,
)


def _read_jsonl(path):
    return [json.loads(line) for line in open(path).read().splitlines()]


async def test_logger_writes_valid_jsonl(tmp_path):
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    logger.emit("run", config={"a": 1})
    logger.emit("iteration", iteration=1, composite=7.5)
    await logger.aclose()

    rows = _read_jsonl(logger.file_path)
    assert len(rows) == 2
    assert rows[0]["type"] == "run"
    assert rows[1]["type"] == "iteration"
    # every event has the correlation fields + schema version + monotonic seq
    for i, r in enumerate(rows):
        assert r["v"] == 1
        assert r["run_id"] == logger.run_id
        assert r["seq"] == i
        assert "ts" in r


async def test_seq_is_monotonic_and_context_tagged(tmp_path):
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    set_iteration(3)
    begin_session("judge")
    emit("llm_call", request={"model": "x"})
    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    assert rows[0]["iteration"] == 3
    assert rows[0]["role"] == "judge"
    assert rows[0]["session_id"] is not None


async def test_concurrent_emits_are_not_interleaved(tmp_path):
    """Many concurrent tasks emitting must produce N intact, valid lines."""
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()

    async def worker(n):
        for k in range(20):
            logger.emit("tool_call", name=f"w{n}", k=k, payload="x" * 500)

    await asyncio.gather(*[worker(n) for n in range(10)])
    await logger.aclose()

    rows = _read_jsonl(logger.file_path)
    assert len(rows) == 200  # 10 workers x 20 — none lost or torn
    seqs = sorted(r["seq"] for r in rows)
    assert seqs == list(range(200))  # unique, contiguous


async def test_no_op_when_no_active_logger():
    # emit() with no active logger must be a harmless no-op
    set_active_logger(None)
    assert get_active_logger() is None
    emit("llm_call", request={"model": "x"})  # should not raise


class _FakeUsage:
    input_tokens = 11
    output_tokens = 7


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self):
        self.content = [_FakeBlock("hello")]
        self.stop_reason = "end_turn"
        self.model = "fake-model"
        self.usage = _FakeUsage()


class _FakeMessages:
    async def create(self, **kwargs):
        return _FakeResponse()


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


async def test_wrap_client_emits_llm_call(tmp_path):
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    set_iteration(1)
    begin_session("generator")

    client = wrap_client(_FakeClient())
    resp = await client.messages.create(
        model="fake-model",
        max_tokens=100,
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert resp.stop_reason == "end_turn"  # transparent passthrough

    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    calls = [r for r in rows if r["type"] == "llm_call"]
    assert len(calls) == 1
    c = calls[0]
    assert c["request"]["model"] == "fake-model"
    assert c["request"]["system"] == "sys"
    assert c["request"]["messages"][0]["content"] == "hi"
    assert c["response"]["stop_reason"] == "end_turn"
    assert c["response"]["usage"]["input_tokens"] == 11
    assert c["role"] == "generator"
    assert "duration_s" in c


async def test_execute_tool_emits_tool_call(tmp_path):
    from simmer_sdk.tools import execute_tool

    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    set_iteration(2)
    begin_session("judge")

    # Write a file then Read it via the tool — exercises real tool execution
    target = tmp_path / "f.txt"
    target.write_text("line1\nline2\n")
    result = execute_tool("Read", {"path": str(target)}, str(tmp_path))
    assert "line1" in result

    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    tcs = [r for r in rows if r["type"] == "tool_call"]
    assert len(tcs) == 1
    assert tcs[0]["name"] == "Read"
    assert tcs[0]["iteration"] == 2
    assert tcs[0]["result_orig_len"] > 0
    assert "duration_s" in tcs[0]


async def test_secrets_stripped_from_run_config():
    from simmer_sdk.trajectory import run_config
    from simmer_sdk.types import SetupBrief

    brief = SetupBrief(
        artifact="x", artifact_type="single-file", criteria={"a": "b"},
        iterations=1, mode="from-paste",
        aws_access_key="AKIA-SECRET", google_api_key="g-secret",
    )
    cfg = run_config(brief)
    assert cfg["aws_access_key"] == "***redacted***"
    assert cfg["google_api_key"] == "***redacted***"
    assert cfg["artifact"] == "x"


async def test_in_memory_events_without_log_dir():
    # No log_dir → no file, but events still captured in memory
    logger = TrajectoryLogger(log_dir=None)
    await logger.start()
    logger.emit("run", config={})
    await logger.aclose()
    assert logger.file_path is None
    assert len(logger.events) == 1
    assert logger.events[0]["type"] == "run"


# --- gap-closing tests ---

class _FailMessages:
    async def create(self, **kwargs):
        raise RuntimeError("boom")


class _FailClient:
    def __init__(self):
        self.messages = _FailMessages()


async def test_wrap_client_logs_error_and_reraises(tmp_path):
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    begin_session("judge")
    client = wrap_client(_FailClient())
    with pytest.raises(RuntimeError):
        await client.messages.create(model="m", messages=[{"role": "user", "content": "x"}])
    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    calls = [r for r in rows if r["type"] == "llm_call"]
    assert len(calls) == 1
    assert "boom" in calls[0]["error"]
    assert "response" not in calls[0]  # error path has no response


def test_create_async_client_wraps_only_when_logger_active(monkeypatch):
    import simmer_sdk.client as client_mod
    from simmer_sdk.types import SetupBrief

    fake = _FakeClient()
    monkeypatch.setattr(client_mod, "_build_raw_client", lambda brief, role: fake)
    brief = SetupBrief(artifact="x", artifact_type="single-file",
                       criteria={"a": "b"}, iterations=1, mode="from-paste")

    set_active_logger(None)
    assert client_mod.create_async_client(brief, role="judge") is fake  # raw passthrough

    logger = TrajectoryLogger()
    set_active_logger(logger)
    try:
        wrapped = client_mod.create_async_client(brief, role="judge")
        assert wrapped is not fake          # wrapped
        assert hasattr(wrapped, "messages")  # still a usable client
    finally:
        set_active_logger(None)


async def test_run_evaluator_emits_evaluator_event(tmp_path):
    from simmer_sdk.refine import _run_evaluator
    from simmer_sdk.types import SetupBrief

    brief = SetupBrief(artifact=str(tmp_path), artifact_type="single-file",
                       criteria={"q": "good"}, iterations=1, mode="seedless",
                       evaluator="echo hi_eval", output_dir=str(tmp_path))
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    out = await _run_evaluator(brief, output_dir=str(tmp_path))
    await logger.aclose()
    set_active_logger(None)

    assert "hi_eval" in out
    rows = _read_jsonl(logger.file_path)
    evs = [r for r in rows if r["type"] == "evaluator"]
    assert len(evs) == 1
    assert "hi_eval" in evs[0]["stdout"]
    assert evs[0]["exit_code"] == 0


async def test_aclose_is_idempotent(tmp_path):
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    logger.emit("run", config={})
    await logger.aclose()
    await logger.aclose()  # second close must be a harmless no-op


async def test_iteration_context_resets_after_block(tmp_path):
    from simmer_sdk.trajectory import iteration_context

    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    set_active_logger(logger)
    set_iteration(5)
    emit("run", config={})              # tagged iteration 5
    with iteration_context(9):
        emit("iteration", iteration=9)  # tagged iteration 9
    emit("outcome")                     # back to iteration 5
    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    by_type = {r["type"]: r["iteration"] for r in rows}
    assert by_type["run"] == 5
    assert by_type["iteration"] == 9
    assert by_type["outcome"] == 5  # context restored


def test_to_jsonable_branches():
    from simmer_sdk.trajectory import _to_jsonable

    class Obj:
        def __init__(self):
            self.a = 1
            self._private = "hidden"

    out = _to_jsonable(Obj())
    assert out == {"a": 1}  # private attrs skipped

    # nested + primitives preserved
    assert _to_jsonable({"x": [1, "s", {"y": 2.0}]}) == {"x": [1, "s", {"y": 2.0}]}

    # unconvertible → str, never raises
    class Weird:
        __slots__ = ()
    assert isinstance(_to_jsonable(Weird()), (str, dict))


def test_default_redactor_scrubs_common_secrets():
    from simmer_sdk.trajectory import default_redactor

    assert "***redacted***" in default_redactor("key=sk-ant-api03-AAAA1111BBBB2222")
    assert "***redacted***" in default_redactor("aws AKIAIOSFODNN7EXAMPLE here")
    # leaves ordinary text alone
    assert default_redactor("just normal text") == "just normal text"


async def test_redact_applied_to_emitted_events(tmp_path):
    from simmer_sdk.trajectory import default_redactor

    logger = TrajectoryLogger(log_dir=str(tmp_path), redact=default_redactor)
    await logger.start()
    set_active_logger(logger)
    begin_session("judge")
    # secret hidden inside a nested tool_result-style payload
    emit("tool_call", name="Bash", input={"command": "cat .env"},
         result="ANTHROPIC_API_KEY=sk-ant-api03-SECRET12345678 done",
         result_orig_len=10, truncated=False, duration_s=0.0)
    await logger.aclose()
    set_active_logger(None)

    rows = _read_jsonl(logger.file_path)
    tc = next(r for r in rows if r["type"] == "tool_call")
    assert "sk-ant-api03-SECRET12345678" not in tc["result"]
    assert "***redacted***" in tc["result"]


async def test_no_writer_task_or_handle_leak_on_emit(tmp_path):
    # Synchronous design: there is no persistent file handle or writer task,
    # so emitting then never calling aclose() leaks nothing and data is durable.
    logger = TrajectoryLogger(log_dir=str(tmp_path))
    await logger.start()
    logger.emit("run", config={})
    logger.emit("iteration", iteration=1)
    # no aclose() — data must already be on disk
    rows = _read_jsonl(logger.file_path)
    assert [r["type"] for r in rows] == ["run", "iteration"]
    assert not hasattr(logger, "_writer_task")  # design no longer uses a task
