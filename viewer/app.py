# ABOUTME: Streamlit inspector for simmer trajectory JSONL logs.
# ABOUTME: Thin UI over simmer_sdk.trajectory_view (all logic is in that module).

"""Simmer trajectory inspector.

Run:
    uv run --extra viewer streamlit run viewer/app.py
    # then pick a trajectory_*.jsonl (upload, or pass a dir/file as the 1st CLI arg)

Renders a run as: config header → score table → iteration → session(role) → turn
panels (with tool calls) → cost summary, plus a per-session "training transcript"
view. All parsing lives in simmer_sdk.trajectory_view; this file only renders.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import streamlit as st

from simmer_sdk.trajectory_view import RunView, load_run, parse_events, session_as_messages

st.set_page_config(page_title="Simmer Trajectory Inspector", layout="wide")


def _discover(arg: str | None) -> list[str]:
    if not arg:
        return []
    if os.path.isdir(arg):
        return sorted(glob.glob(os.path.join(arg, "*.jsonl")), reverse=True)
    if os.path.isfile(arg):
        return [arg]
    return []


def _role_badge(role: str | None) -> str:
    return {
        "generator": "🛠️ generator",
        "judge": "⚖️ judge",
        "clerk": "📝 clerk",
    }.get(role or "", f"• {role}")


PREVIEW = 1500  # chars shown before truncation in readable mode


def _stringify(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or json.dumps(b))
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return str(content)


def _long_text(text: str, *, code: bool = False) -> None:
    """Render text, truncating very long blocks with a char-count caption."""
    text = text or ""
    shown = text[:PREVIEW]
    if code:
        st.code(shown)
    else:
        st.markdown(shown.replace("\n", "  \n"))
    if len(text) > PREVIEW:
        st.caption(f"… +{len(text) - PREVIEW:,} more chars (enable Raw JSON for full)")


def _input_summary(inp) -> str:
    """One-line summary of a tool input: long string fields elided to <N chars>."""
    if not isinstance(inp, dict):
        return str(inp)[:120]
    parts = []
    for k, v in inp.items():
        if isinstance(v, str) and len(v) > 60:
            parts.append(f"{k}=<{len(v):,} chars>")
        else:
            parts.append(f"{k}={v!r}")
    return ", ".join(parts)


def _render_tool_input(inp) -> None:
    """Render a tool input field-by-field so long string fields keep real newlines."""
    if not isinstance(inp, dict):
        _long_text(str(inp), code=True)
        return
    for k, v in inp.items():
        if isinstance(v, str) and ("\n" in v or len(v) > 120):
            st.markdown(f"**{k}:**")
            _long_text(v, code=True)  # st.code preserves real newlines (no \\n escaping)
        else:
            st.markdown(f"**{k}:** `{v}`")


def _render_block(block: dict) -> None:
    btype = block.get("type")
    if btype == "text":
        _long_text(block.get("text", ""))
    elif btype == "tool_use":
        st.markdown(f"🔧 **{block.get('name')}**({_input_summary(block.get('input', {}))})")
    elif btype == "tool_result":
        st.markdown("↩️ *tool_result*")
        _long_text(_stringify(block.get("content", "")), code=True)
    else:
        _long_text(json.dumps(block, indent=2), code=True)


def _render_messages(messages: list) -> None:
    icons = {"user": "👤 user", "assistant": "🤖 assistant", "system": "⚙️ system"}
    for m in messages:
        if not isinstance(m, dict):
            st.text(str(m))
            continue
        role = m.get("role", "?")
        st.markdown(f"**{icons.get(role, role)}**")
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                _render_block(b if isinstance(b, dict) else {"type": "text", "text": str(b)})
        else:
            _long_text(_stringify(content))
        st.markdown("---")


def _render_turn(turn: dict, raw: bool) -> None:
    if turn["type"] == "llm_call":
        req, resp = turn.get("request", {}), turn.get("response", {})
        usage = (resp.get("usage") or {})
        msgs = req.get("messages", [])
        st.markdown(
            f"**llm_call** · seq {turn.get('seq')} · "
            f"{usage.get('input_tokens', '?')}→{usage.get('output_tokens', '?')} tok · "
            f"stop=`{resp.get('stop_reason')}` · {turn.get('duration_s', 0):.2f}s"
        )
        if turn.get("error"):
            st.error(turn["error"])
        with st.expander(f"prompt — {len(msgs)} message(s)", expanded=False):
            if raw:
                st.json(msgs)
            else:
                if req.get("system"):
                    st.markdown("**⚙️ system**")
                    _long_text(req["system"])
                    st.markdown("---")
                _render_messages(msgs)
        with st.expander("response", expanded=False):
            if raw:
                st.json(resp.get("content", []))
            else:
                content = resp.get("content", [])
                if isinstance(content, list):
                    for b in content:
                        _render_block(b if isinstance(b, dict) else {"type": "text", "text": str(b)})
                else:
                    _long_text(_stringify(content))
    elif turn["type"] == "tool_call":
        trunc = " (truncated)" if turn.get("truncated") else ""
        st.markdown(
            f"**tool_call** · seq {turn.get('seq')} · `{turn.get('name')}` · "
            f"{turn.get('result_orig_len', 0)} chars{trunc} · {turn.get('duration_s', 0):.3f}s"
        )
        with st.expander(f"{turn.get('name')} input / result", expanded=False):
            if raw:
                st.json({"input": turn.get("input", {}), "result": turn.get("result", "")})
            else:
                st.caption("input")
                _render_tool_input(turn.get("input", {}))
                st.caption("result")
                _long_text(str(turn.get("result", "")), code=True)


def render(view: RunView, raw: bool = False) -> None:
    st.title("Simmer Trajectory Inspector")

    # --- header ---
    cfg = view.config
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("run_id", view.run_id or "—")
    c1.metric("events", view.total_events)
    c2.metric("iterations", len([i for i in view.iterations if i.iteration not in (None,)]))
    c2.metric("judge_mode", cfg.get("judge_mode", "—"))
    if view.outcome:
        c3.metric("best iteration", view.outcome.get("best_iteration", "—"))
        c3.metric("best composite", view.outcome.get("composite", "—"))
    c4.metric("in tokens", f"{view.total_input_tokens:,}")
    c4.metric("out tokens", f"{view.total_output_tokens:,}")

    with st.expander("run config", expanded=False):
        st.json(cfg)
    st.caption("event counts: " + ", ".join(f"{k}={v}" for k, v in sorted(view.event_counts.items())))

    # --- score table ---
    rows = []
    for it in view.iterations:
        if it.record is None:
            continue
        row = {"iter": it.iteration, "composite": it.composite,
               "regressed": it.record.get("regressed")}
        row.update(it.scores)
        row["key_change"] = (it.record.get("key_change") or "")[:60]
        rows.append(row)
    if rows:
        st.subheader("Trajectory")
        st.dataframe(rows, use_container_width=True)

    # --- cost by role ---
    cbr = view.cost_by_role()
    if cbr:
        st.subheader("By role")
        st.dataframe(
            [{"role": r, **d} for r, d in sorted(cbr.items())],
            use_container_width=True,
        )

    # --- iteration → session → turn drilldown ---
    st.subheader("Iterations")
    for it in view.iterations:
        label = f"Iteration {it.iteration}"
        if it.composite is not None:
            label += f" — composite {it.composite}"
        label += f" · {len(it.sessions)} sessions"
        with st.expander(label, expanded=(it.iteration in (0, 1))):
            if it.record and it.record.get("asi"):
                st.markdown(f"**ASI:** {it.record['asi']}")
            for ev in it.evaluator:
                with st.expander(f"evaluator (exit {ev.get('exit_code')})", expanded=False):
                    st.code((ev.get("stdout") or "")[:4000] or "(no stdout)")
                    if ev.get("stderr"):
                        st.code(ev["stderr"][:2000])
            for sess in it.sessions:
                with st.expander(
                    f"{_role_badge(sess.role)} · session {sess.session_id} · "
                    f"{len(sess.llm_calls)} llm · {len(sess.tool_calls)} tools",
                    expanded=False,
                ):
                    # training-transcript view
                    if st.checkbox(
                        "show as training transcript",
                        key=f"tx-{it.iteration}-{sess.session_id}-{sess.role or 'unknown'}",
                    ):
                        st.json(session_as_messages(sess))
                    for turn in sess.turns:
                        _render_turn(turn, raw)
                        st.divider()


def main() -> None:
    # SIMMER_TRAJ_DIR wins over argv so headless test harnesses (and explicit
    # env config) aren't shadowed by an unrelated sys.argv[1].
    arg = os.environ.get("SIMMER_TRAJ_DIR") or (sys.argv[1] if len(sys.argv) > 1 else None)
    candidates = _discover(arg)

    st.sidebar.header("Load a trajectory")
    uploaded = st.sidebar.file_uploader("Upload a .jsonl", type=["jsonl"])
    chosen = None
    if candidates:
        chosen = st.sidebar.selectbox("…or pick a discovered file", candidates)
    raw = st.sidebar.checkbox("Raw JSON view", value=False,
                              help="Show full untruncated request/response/tool JSON")

    view = None
    if uploaded is not None:
        events = []
        for line in uploaded.getvalue().decode("utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        view = parse_events(events)
    elif chosen:
        view = load_run(chosen)

    if view is None:
        st.info("Upload a trajectory_*.jsonl in the sidebar, or launch with a dir/file "
                "argument: `streamlit run viewer/app.py <dir-or-file>`")
        return
    render(view, raw)


main()
