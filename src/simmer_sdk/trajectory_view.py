# ABOUTME: Pure projection of a trajectory JSONL event log into a structured
# ABOUTME: RunView (iterations -> sessions -> turns). No UI deps; unit-testable.

"""Read a trajectory JSONL event log and reconstruct the run as a tree.

The on-disk log is a flat, append-only event stream (``run``, ``iteration``,
``llm_call``, ``tool_call``, ``evaluator``, ``outcome``) tagged with
``run_id`` / ``iteration`` / ``session_id`` / ``role`` / ``seq``. This module
groups those events into the natural hierarchy for inspection:

    RunView
      └─ IterationView (one per iteration index)
           ├─ SessionView (one per session_id, labelled by role)
           │     └─ TurnEvent[]  (llm_call + tool_call, ordered by seq)
           └─ evaluator events

Everything here is a pure read-only projection: a partial / crashed log still
parses (incomplete sessions simply have fewer turns).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionView:
    session_id: str
    role: str | None
    turns: list[dict] = field(default_factory=list)  # llm_call + tool_call events, ordered by seq

    @property
    def llm_calls(self) -> list[dict]:
        return [t for t in self.turns if t["type"] == "llm_call"]

    @property
    def tool_calls(self) -> list[dict]:
        return [t for t in self.turns if t["type"] == "tool_call"]

    @property
    def input_tokens(self) -> int:
        return sum(
            (t.get("response", {}).get("usage", {}) or {}).get("input_tokens", 0) or 0
            for t in self.llm_calls
        )

    @property
    def output_tokens(self) -> int:
        return sum(
            (t.get("response", {}).get("usage", {}) or {}).get("output_tokens", 0) or 0
            for t in self.llm_calls
        )


@dataclass
class IterationView:
    iteration: int
    record: dict | None = None  # the "iteration" event (scores/composite/asi/...)
    sessions: list[SessionView] = field(default_factory=list)
    evaluator: list[dict] = field(default_factory=list)

    @property
    def composite(self) -> float | None:
        return self.record.get("composite") if self.record else None

    @property
    def scores(self) -> dict:
        return (self.record or {}).get("scores", {}) or {}


@dataclass
class RunView:
    run_id: str | None
    config: dict = field(default_factory=dict)
    iterations: list[IterationView] = field(default_factory=list)
    outcome: dict | None = None
    events: list[dict] = field(default_factory=list)

    # --- aggregate stats ---
    @property
    def total_events(self) -> int:
        return len(self.events)

    @property
    def event_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.events:
            if not isinstance(e, dict):
                continue
            etype = e.get("type")
            if etype:
                counts[etype] = counts.get(etype, 0) + 1
        return counts

    @property
    def total_input_tokens(self) -> int:
        return sum(s.input_tokens for it in self.iterations for s in it.sessions)

    @property
    def total_output_tokens(self) -> int:
        return sum(s.output_tokens for it in self.iterations for s in it.sessions)

    def cost_by_role(self) -> dict[str, dict]:
        """Token totals grouped by role (cost comes from outcome.total_usage if present)."""
        roles: dict[str, dict] = {}
        for it in self.iterations:
            for s in it.sessions:
                r = s.role or "unknown"
                d = roles.setdefault(r, {"sessions": 0, "input_tokens": 0, "output_tokens": 0})
                d["sessions"] += 1
                d["input_tokens"] += s.input_tokens
                d["output_tokens"] += s.output_tokens
        return roles


def parse_events(events: list[dict]) -> RunView:
    """Group a list of event dicts into a RunView."""
    run_event = next((e for e in events if isinstance(e, dict) and e.get("type") == "run"), None)
    outcome = next((e for e in events if isinstance(e, dict) and e.get("type") == "outcome"), None)

    view = RunView(
        run_id=(run_event or {}).get("run_id"),
        config=(run_event or {}).get("config", {}),
        outcome=outcome,
        events=events,
    )

    # iteration index -> IterationView (preserve first-seen order)
    iters: dict[Any, IterationView] = {}

    def get_iter(idx) -> IterationView:
        if idx not in iters:
            iters[idx] = IterationView(iteration=idx)
        return iters[idx]

    for e in events:
        if not isinstance(e, dict):
            continue
        etype = e.get("type")
        idx = e.get("iteration")
        if etype == "iteration":
            it = get_iter(e.get("iteration"))
            it.record = e
        elif etype == "evaluator":
            get_iter(idx).evaluator.append(e)
        elif etype in ("llm_call", "tool_call"):
            it = get_iter(idx)
            sid = e.get("session_id")
            sess = next((s for s in it.sessions if s.session_id == sid), None)
            if sess is None:
                sess = SessionView(session_id=sid, role=e.get("role"))
                it.sessions.append(sess)
            if sess.role is None:
                sess.role = e.get("role")
            sess.turns.append(e)

    # order iterations by index (None last), turns by seq, sessions by first seq
    def _iter_key(i: IterationView):
        return (i.iteration is None, i.iteration if i.iteration is not None else 0)

    view.iterations = sorted(iters.values(), key=_iter_key)
    for it in view.iterations:
        for s in it.sessions:
            s.turns.sort(key=lambda t: t.get("seq", 0))
        it.sessions.sort(key=lambda s: s.turns[0].get("seq", 0) if s.turns else 0)
    return view


def load_run(path: str | Path) -> RunView:
    """Load a trajectory JSONL file into a RunView. Skips torn/invalid lines."""
    events: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # A torn tail line (e.g. crash mid-write) — skip, keep the rest.
                continue
            if isinstance(event, dict):  # ignore valid-but-non-object lines
                events.append(event)
    return parse_events(events)


def session_as_messages(session: SessionView) -> list[dict]:
    """Project one agent session into a flat chat transcript (training-example view).

    Concatenates each llm_call's request messages + the assistant response, in
    order. This is the shape you'd export for SFT/RL.
    """
    transcript: list[dict] = []
    for call in session.llm_calls:
        req = call.get("request", {})
        # System prompt (once, from the first call that has one)
        sys = req.get("system")
        if sys and not any(m.get("role") == "system" for m in transcript):
            transcript.append({"role": "system", "content": sys})
        for m in req.get("messages", []):
            transcript.append(m)
        resp = call.get("response", {})
        if resp.get("content") is not None:
            transcript.append({"role": "assistant", "content": resp["content"]})
    return transcript
