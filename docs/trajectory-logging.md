# Trajectory Logging

A complete, raw, append-only **JSONL event log** of everything that happens
inside a `refine()` run — every LLM call, every tool call, the orchestration
events, and the outcome. Designed so the flows can be replayed, audited,
inspected in a UI, or shaped into agent **training data** offline.

## Enabling

```python
from simmer_sdk import refine

result = await refine(
    artifact=...,
    criteria=...,
    trajectory_log_dir="trajectories",   # off by default
)
# writes: trajectories/trajectory_<YYYY-MM-DD_HH-MM-SS>_<run_id>.jsonl
```

Off by default — zero overhead when unset. When set, one JSONL file is written
per run.

### Redacting secrets

Tool results and prompts are captured verbatim, so a tool that reads a secrets
file (`Bash: cat .env`) or a prompt containing a key would otherwise land in the
log. Pass `trajectory_redact` to scrub them:

```python
await refine(..., trajectory_log_dir="trajectories", trajectory_redact=True)
# True → built-in default_redactor (Anthropic/OpenAI/AWS/GitHub/Slack token patterns)

from simmer_sdk.trajectory import default_redactor
await refine(..., trajectory_redact=lambda s: my_scrubber(default_redactor(s)))
# or pass any str -> str callable for custom rules
```

The redactor is applied to every string in each event before it is written.
(The `run` config snapshot is always secret-stripped regardless.)

## Design

- **Event-sourced.** The log is a flat, append-only stream of granular events,
  not buffered records. Sessions and iterations are *reconstructed* by grouping
  on IDs — never written as fat records.
- **Boundary capture.** Events are emitted at two transport boundaries —
  the model client (`create_async_client` → wrapped) and `execute_tool` — using
  context variables for ambient `run_id` / `iteration` / `session_id` / `role`.
  Role logic (generator / judge / clerk / reflect) is untouched, and new roles
  get logging for free.
- **Synchronous atomic writes.** Each `emit` opens the file in append mode
  (`O_APPEND`), writes one `json.dumps(...) + "\n"`, and closes it. There is no
  writer task and no persistent file handle, so a run that raises mid-way leaks
  nothing. Writes never interleave — `emit` runs to completion with no `await`
  (safe across concurrent coroutines/parallel judges) and `O_APPEND` writes are
  atomic (safe across threads).
- **Crash-safe.** Every event is durable the moment it's written. A torn tail
  loses only the last line; every earlier line is valid JSON. A partial/crashed
  run still parses (incomplete sessions just have fewer turns).
- **Raw, uninterpreted.** Full requests + responses + tool results captured
  verbatim (only secrets are stripped from the config snapshot). No reward
  labeling, session assembly, or training-shape is done at capture time — all of
  that is an offline projection over the log.

## Event schema

Every event carries: `v` (schema version), `type`, `ts` (UTC ISO), `seq`
(monotonic), `run_id`, `iteration`, `session_id`, `role`.

| `type` | additional fields |
|--------|-------------------|
| `run` | `config` — the `SetupBrief` snapshot (api keys / aws / google creds redacted) |
| `iteration` | `scores`, `composite`, `key_change`, `asi`, `regressed` |
| `llm_call` | `request` {`model`, `system`, `messages`, `tools`, `max_tokens`, ...}, `response` {`content`, `stop_reason`, `model`, `usage`{`input_tokens`,`output_tokens`}}, `duration_s`; on failure: `error` instead of `response` |
| `tool_call` | `name`, `input`, `result`, `result_orig_len`, `truncated`, `duration_s` |
| `evaluator` | `cmd`, `stdout`, `stderr`, `exit_code` |
| `outcome` | `best_iteration`, `best_scores`, `composite`, `total_usage` |

A "session" = all `llm_call` + `tool_call` events sharing a `session_id`, ordered
by `seq`. One agent invocation (e.g. one judge in a board) is one session.

## Reading a log: the `RunView` projection

```python
from simmer_sdk.trajectory_view import load_run, session_as_messages

view = load_run("trajectories/trajectory_....jsonl")

view.config              # the run config
view.outcome             # the outcome event
view.event_counts        # {"llm_call": 68, "tool_call": 58, ...}
view.total_input_tokens  # summed across all sessions
view.cost_by_role()      # {"judge": {"sessions": 21, "input_tokens": ...}, ...}

for it in view.iterations:           # IterationView, ordered by index
    it.iteration, it.composite, it.scores
    for sess in it.sessions:         # SessionView, one per session_id
        sess.role                    # "generator" | "judge" | "clerk" | ...
        sess.llm_calls, sess.tool_calls, sess.input_tokens
        for turn in sess.turns:      # llm_call + tool_call, ordered by seq
            ...

# Project one session into a flat chat transcript (the training-example shape):
messages = session_as_messages(view.iterations[1].sessions[0])
```

All projection functions are pure (no UI/SDK deps) and unit-tested.

## Training-data use

Each `agent_session` is a self-contained, standard tool-use transcript
(`system` + `messages` with `tool_use` / `tool_result` blocks) — directly usable
for SFT/RL. Join it to the reward signal offline: the `iteration` and `outcome`
events carry the scores. A typical export is "group events by `session_id`,
attach the iteration's composite as the label, filter to best-iteration
sessions." Because the log is raw and complete, you can re-derive any training
format later without re-running.

## Inspecting (Streamlit viewer)

```bash
uv sync --extra viewer
uv run --extra viewer streamlit run viewer/app.py trajectories
```

Renders iteration → session(role) → turn panels, a score table, per-role cost,
and a per-session training-transcript view. Sidebar **Raw JSON** toggle shows
full untruncated events. The viewer is a thin layer over `RunView`.

## Limitations

- **`cli` dispatch** (Claude Agent SDK subprocess) captures less than the
  `api` / `ollama` paths — the full per-turn request/response inside the
  subprocess isn't exposed the same way. For training-grade fidelity prefer
  `agent_dispatch="api"` (the default for cloud providers).
- **Outcome event on exception.** On a mid-run exception, all events written so
  far are intact and durable (synchronous writes; nothing leaks), but you won't
  get the final `outcome` summary event. The run still reconstructs from the
  events that were written.
- **Storage on long agent loops.** Each `llm_call` stores the full *growing*
  message history, so a long multi-turn agent session re-stores the prompt each
  turn (≈O(n²)). Fine for typical runs; for very long workspace agents consider
  this when sizing storage.

## Relation to OpenTelemetry

The capture pattern (boundary instrumentation, granular LLM + tool records,
correlation IDs) matches the OpenTelemetry GenAI conventions; the schema and
file transport are intentionally bespoke for the training-data use case. The
event-sourced design makes an OTel/tracing-backend exporter a pure offline
projection (`session_id` → trace, `llm_call`/`tool_call` → spans) if ecosystem
interop is later wanted.
