# ABOUTME: Event-sourced trajectory logging for simmer runs — captures raw
# ABOUTME: LLM calls, tool calls, and orchestration events as append-only JSONL.

"""Trajectory logging.

Captures a complete, raw, append-only event stream for a ``refine()`` run so
the flows can be replayed, audited, or shaped into agent training data offline.

Design (deliberately past the limitations of simpler loggers):

- **Granular events, not fat records.** Each LLM turn and each tool call is its
  own event. A crash yields every complete event up to that point; partial
  sessions are still useful. Sessions/iterations are reconstructed offline by
  grouping on IDs — never written as buffered records.
- **Synchronous atomic writes.** Each ``emit`` opens the file in append mode
  (``O_APPEND``), writes one ``json.dumps(...) + "\\n"``, and closes it. No
  writer task and no persistent file handle, so a run that raises leaks nothing.
  Writes never interleave — ``emit`` runs to completion with no ``await`` (safe
  across coroutines) and ``O_APPEND`` writes are atomic (safe across threads).
- **Crash-safe.** Every event is durable the moment it's written. A torn tail
  loses only the last line; earlier lines are always valid JSON.
- **Optional redaction.** A ``redact`` callable scrubs secrets from every string
  in each event before writing (config is always secret-stripped regardless).
- **Correlation IDs + schema version on every event.** ``run_id``, ``iteration``,
  ``session_id``, ``role``, monotonic ``seq``, and ``v`` — so the log is
  shardable, mergeable, and reconstructable from IDs, not file position.
- **Raw, uninterpreted.** Full requests + responses + tool results captured
  verbatim (secrets stripped from config only). No reward labeling, no session
  assembly, no training-shape at capture time — all of that is an offline
  projection over this log.

Capture happens at two transport boundaries via context variables, so business
logic (generator/judge/clerk/reflect) is untouched and new roles get logging
for free:

- ``wrap_client()`` around the model client → one ``llm_call`` per turn.
- ``execute_tool`` (instrumented in ``tools.py``) → one ``tool_call`` per call.
"""

from __future__ import annotations

import contextvars
import itertools
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1

# --- Ambient context (per asyncio task; copied into child tasks at creation) ---
_current_logger: contextvars.ContextVar["TrajectoryLogger | None"] = contextvars.ContextVar(
    "simmer_trajectory_logger", default=None
)
_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("simmer_run_id", default=None)
_iteration: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "simmer_iteration", default=None
)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "simmer_session_id", default=None
)
_role: contextvars.ContextVar[str | None] = contextvars.ContextVar("simmer_role", default=None)

_SECRET_KEYS = ("api_key", "aws_access_key", "aws_secret_key", "google_api_key", "secret", "token")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_jsonable(obj: Any, _depth: int = 0) -> Any:
    """Best-effort lossless-ish conversion to JSON-serializable form.

    Never raises: anything unconvertible falls back to ``str(obj)``. Handles
    pydantic models (``model_dump``), dataclass-ish objects (``__dict__``),
    mappings, and sequences.
    """
    if _depth > 12:
        return str(obj)
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v, _depth + 1) for v in obj]
    # pydantic v2
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_jsonable(model_dump(), _depth + 1)
        except Exception:
            pass
    # anthropic SDK objects often expose .to_dict()
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return _to_jsonable(to_dict(), _depth + 1)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        try:
            return {
                str(k): _to_jsonable(v, _depth + 1)
                for k, v in vars(obj).items()
                if not k.startswith("_")
            }
        except Exception:
            pass
    return str(obj)


def _strip_secrets(d: Any) -> Any:
    """Recursively drop values for secret-looking keys."""
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if any(s in str(k).lower() for s in _SECRET_KEYS):
                out[k] = "***redacted***"
            else:
                out[k] = _strip_secrets(v)
        return out
    if isinstance(d, list):
        return [_strip_secrets(v) for v in d]
    return d


def _deep_redact(obj: Any, fn) -> Any:
    """Apply a string-scrubbing function to every string leaf of a structure."""
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, dict):
        return {k: _deep_redact(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_redact(v, fn) for v in obj]
    return obj


_DEFAULT_SECRET_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}"      # Anthropic
    r"|sk-[A-Za-z0-9_-]{20,}"          # OpenAI-style
    r"|AKIA[0-9A-Z]{16}"               # AWS access key id
    r"|ghp_[A-Za-z0-9]{20,}"           # GitHub PAT
    r"|xox[baprs]-[A-Za-z0-9-]{10,})"  # Slack
)


def default_redactor(text: str) -> str:
    """Scrub common secret token patterns (API keys, PATs) from a string."""
    return _DEFAULT_SECRET_RE.sub("***redacted***", text)


class TrajectoryLogger:
    """Append-only JSONL event logger.

    Writes are **synchronous and atomic per event**: each ``emit`` opens the
    file in append mode (``O_APPEND``), writes one ``json.dumps(...) + "\\n"``,
    and closes it. This is crash-proof (no persistent file handle and no writer
    task to leak if the run raises) and interleave-free across both coroutines
    (``emit`` runs to completion with no ``await``) and threads (``O_APPEND``
    writes are atomic). ``start()`` / ``aclose()`` are async no-ops kept for API
    symmetry. The in-memory ``events`` list is always populated.

    Pass ``redact`` (a ``str -> str`` callable, e.g. :func:`default_redactor`) to
    scrub secrets from every string in each event before it is written.
    """

    def __init__(
        self,
        log_dir: str | None = None,
        run_id: str | None = None,
        file_name: str = "trajectory",
        redact=None,
    ):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.log_dir = log_dir
        self.redact = redact
        self.events: list[dict] = []
        self._seq = itertools.count()
        self.file_path: str | None = None
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.file_path = os.path.join(log_dir, f"{file_name}_{ts}_{self.run_id}.jsonl")

    async def start(self) -> None:
        """No persistent resources to start (writes are sync append-per-event)."""
        return None

    def emit(self, type: str, **fields: Any) -> None:
        """Write one event synchronously. Atomic; safe from concurrent tasks."""
        event = {
            "v": SCHEMA_VERSION,
            "type": type,
            "ts": _now(),
            "seq": next(self._seq),
            "run_id": self.run_id,
            "iteration": _iteration.get(),
            "session_id": _session_id.get(),
            "role": _role.get(),
            **fields,
        }
        if self.redact is not None:
            event = _deep_redact(event, self.redact)
        self.events.append(event)
        if self.file_path is not None:
            line = json.dumps(event, ensure_ascii=False) + "\n"
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line)  # O_APPEND → atomic; close flushes to the OS

    async def aclose(self) -> None:
        """No-op: nothing to drain or close (writes are durable per event)."""
        return None


# --- Ambient helpers (used by refine + the wrapped boundaries) ---

def set_active_logger(logger: TrajectoryLogger | None) -> contextvars.Token:
    return _current_logger.set(logger)


def get_active_logger() -> TrajectoryLogger | None:
    return _current_logger.get()


def emit(type: str, **fields: Any) -> None:
    """Emit on the active logger if one is set; no-op otherwise (zero overhead off)."""
    logger = _current_logger.get()
    if logger is not None:
        logger.emit(type, **fields)


def set_iteration(n: int) -> None:
    """Set the current iteration on this task's context (persists until changed).

    Child tasks spawned afterward inherit a snapshot, so concurrent judges are
    tagged with the iteration that was active when they were spawned.
    """
    _iteration.set(n)


@contextmanager
def iteration_context(n: int):
    token = _iteration.set(n)
    try:
        yield
    finally:
        _iteration.reset(token)


@contextmanager
def session_context(role: str, session_id: str | None = None):
    """Mark an agent session: assigns a fresh session_id + role for downstream calls."""
    sid = session_id or uuid.uuid4().hex[:12]
    t1 = _session_id.set(sid)
    t2 = _role.set(role)
    try:
        yield sid
    finally:
        _session_id.reset(t1)
        _role.reset(t2)


def begin_session(role: str, session_id: str | None = None) -> str:
    """Set session_id + role on the current context without auto-reset.

    Used by ``create_async_client`` where one client == one logical agent
    session in this codebase, and the context should persist for that client's
    subsequent ``messages.create`` calls within the same task.
    """
    sid = session_id or uuid.uuid4().hex[:12]
    _session_id.set(sid)
    _role.set(role)
    return sid


def run_config(brief: Any) -> dict:
    """Serialize a SetupBrief into a secrets-stripped config dict for the run event."""
    raw = _to_jsonable(brief)
    return _strip_secrets(raw)


# --- Boundary: wrap the model client so every turn emits an llm_call ---

def _serialize_request(kwargs: dict) -> dict:
    keep = {}
    for k in ("model", "system", "messages", "tools", "max_tokens", "temperature", "tool_choice"):
        if k in kwargs:
            keep[k] = _to_jsonable(kwargs[k])
    return keep


def _serialize_response(resp: Any) -> dict:
    out: dict[str, Any] = {}
    out["content"] = _to_jsonable(getattr(resp, "content", None))
    out["stop_reason"] = getattr(resp, "stop_reason", None)
    out["model"] = getattr(resp, "model", None)
    usage = getattr(resp, "usage", None)
    if usage is not None:
        out["usage"] = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
    return out


class _LoggingMessages:
    def __init__(self, inner_messages, get_model_default):
        self._inner = inner_messages
        self._get_model_default = get_model_default

    async def create(self, *args, **kwargs):
        logger = _current_logger.get()
        if logger is None:
            return await self._inner.create(*args, **kwargs)
        start = time.perf_counter()
        try:
            resp = await self._inner.create(*args, **kwargs)
        except Exception as exc:
            logger.emit(
                "llm_call",
                request=_serialize_request(kwargs),
                error=f"{type(exc).__name__}: {exc}",
                duration_s=time.perf_counter() - start,
            )
            raise
        logger.emit(
            "llm_call",
            request=_serialize_request(kwargs),
            response=_serialize_response(resp),
            duration_s=time.perf_counter() - start,
        )
        return resp

    def __getattr__(self, name):  # delegate anything else (e.g. .stream)
        return getattr(self._inner, name)


class LoggingClient:
    """Transparent proxy that logs every ``.messages.create`` call.

    Delegates all other attribute access to the wrapped client, so it is a
    drop-in replacement for AsyncAnthropic / AsyncAnthropicBedrock / the Gemini
    adapter (all expose ``.messages.create``).
    """

    def __init__(self, inner):
        self._inner = inner
        self._messages_proxy = _LoggingMessages(inner.messages, lambda: None)

    @property
    def messages(self):
        return self._messages_proxy

    def __getattr__(self, name):
        return getattr(self._inner, name)


def wrap_client(client):
    """Wrap a model client for trajectory logging. No-op if it has no ``.messages``."""
    if client is None or not hasattr(client, "messages"):
        return client
    return LoggingClient(client)
