"""Interior View dashboard, Studio Flow mode wiring
(observatory.turn_api.Dashboard / observatory.server, `session_mode="flow"`).

Flow's own engine (state isolation, no accept/reject, observations,
integration) is already covered by tests/test_flow.py against flow.py
directly. This file covers the *dashboard* surfacing task: FlowTraces
served alongside pipeline TurnTraces, session listing marked mode: flow,
POST /api/turn routing to the flow path when the dashboard process is
configured for it, and the field_before/traveled/field_after SSE sequence
— all without a live Ollama.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path

from conditioned_kernel.cli import build_parser
from conditioned_kernel.edge import load_profile
from conditioned_kernel.observatory import server as server_mod
from conditioned_kernel.observatory import turn_api as turn_api_mod
from conditioned_kernel.flow import run_flow_turn as real_run_flow_turn

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "goal": GOAL,
                "active_profile": "orin_nano_8gb",
                "session_id": "sess_flow_dash_test",
                "receipt_count_24h": 0,
                "recent_turns": [],
                "flags": {
                    "sensors": False,
                    "tools": False,
                    "cloud": False,
                    "max_repair_passes": 1,
                    "edge_target": "jetson_orin_nano_8gb",
                    "one_model_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "threads.json").write_text(
        json.dumps(
            [
                {
                    "id": "thread_min_model",
                    "status": "open",
                    "title": "What is the minimum viable model size on Jetson Orin Nano 8GB?",
                }
            ]
        ),
        encoding="utf-8",
    )
    (state_dir / "methods.json").write_text("[]", encoding="utf-8")
    return state_dir, logs_dir


def _dry_run_flow_turn(user_input, **kwargs):
    """Offline stand-in for flow.run_flow_turn, mirroring
    test_observatory_server.py's `_dry_run_traced_turn` convention: force a
    deterministic reply so POST /api/turn can be exercised at the wire
    level with zero network calls."""
    kwargs.pop("dry_reply", None)
    return real_run_flow_turn(user_input, dry_reply=f"(dry reply to) {user_input}", **kwargs)


def _start(monkeypatch, tmp_path, *, session_mode: str = "flow"):
    state_dir, logs_dir = _bootstrap(tmp_path)
    monkeypatch.setattr(turn_api_mod, "run_flow_turn", _dry_run_flow_turn)
    profile = load_profile(None)
    httpd = server_mod.create_server(
        host="127.0.0.1",
        port=0,
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=profile,
        model=None,
        base_url="http://127.0.0.1:11434",
        session_mode=session_mode,
    )
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05})
    thread.daemon = True
    thread.start()
    time.sleep(0.1)
    return httpd, thread, port, state_dir, logs_dir


def _stop(httpd, thread) -> None:
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _get(port: int, path: str):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _post(port: int, path: str, payload: dict):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI: --session-mode flag exists, defaults to pipeline, does not collide
# with the dashboard's own --mode (chat_json/generate_raw kernel transport).
# ---------------------------------------------------------------------------


def test_cli_dashboard_session_mode_flag():
    p = build_parser()
    args = p.parse_args(["dashboard"])
    assert args.session_mode == "pipeline"
    args = p.parse_args(["dashboard", "--session-mode", "flow"])
    assert args.session_mode == "flow"
    # the dashboard's own --mode (kernel transport) is untouched
    args = p.parse_args(["dashboard", "--mode", "chat_json", "--session-mode", "flow"])
    assert args.mode == "chat_json"
    assert args.session_mode == "flow"


# ---------------------------------------------------------------------------
# POST /api/turn routes to the flow path; GET trace returns the FlowTrace.
# ---------------------------------------------------------------------------


def test_flow_session_post_turn_routes_to_flow_path(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path, session_mode="flow")
    try:
        status, _, body = _post(port, "/api/turn", {"text": "hello there, how's it going"})
        assert status == 200
        trace = json.loads(body)
        assert trace["schema"] == "ck.flow_trace.v1"
        assert "field_before" in trace
        assert "field_after" in trace
        assert "composed_prompt" in trace
        assert trace["displayed_text"] == "(dry reply to) hello there, how's it going"

        # never touches current.json / threads.json
        assert (state_dir / "current.json").exists()
        assert (state_dir / "flow_field.json").exists()

        # visible in session listing, marked mode: flow
        status, _, body = _get(port, "/api/session")
        session = json.loads(body)
        assert session["runtime_config"]["session_mode"] == "flow"
        turns = session["turns"]
        assert len(turns) == 1
        assert turns[0]["mode"] == "flow"
        assert turns[0]["turn_id"] == trace["turn_id"]
        assert turns[0]["answer"] == trace["displayed_text"]

        # fetchable by id and as "latest"
        status, _, body = _get(port, f"/api/turn/{trace['turn_id']}/trace")
        assert status == 200
        assert json.loads(body)["schema"] == "ck.flow_trace.v1"

        status, _, body = _get(port, "/api/turn/latest/trace")
        assert status == 200
        assert json.loads(body)["turn_id"] == trace["turn_id"]
    finally:
        _stop(httpd, thread)


def test_flow_session_brief_endpoint_does_not_crash(monkeypatch, tmp_path):
    """FlowTrace has a different shape than TurnTrace (no packet/passes/
    stages) — the brief endpoint must not blow up trying to read
    pipeline-only fields off it."""
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path, session_mode="flow")
    try:
        status, _, body = _post(port, "/api/turn", {"text": "what is this project for"})
        turn_id = json.loads(body)["turn_id"]

        status, headers, body = _get(port, f"/api/turn/{turn_id}/brief")
        assert status == 200
        text = body.decode("utf-8")
        assert turn_id in text
        assert "Field before" in text
        assert "Field after" in text
    finally:
        _stop(httpd, thread)


def test_pipeline_session_unaffected_by_flow_mode_existing(monkeypatch, tmp_path):
    """A dashboard started without --session-mode (or with pipeline)
    behaves exactly as before: session listing still marks turns, now with
    an additive mode: "pipeline" key, and POST /api/turn still calls the
    real pipeline path, never flow.run_flow_turn."""
    from conditioned_kernel.observatory.trace import run_traced_turn as real_run_traced_turn

    DRY_JSON = json.dumps(
        {
            "answer": "Design intent is edge-first substrate conditioning.",
            "evidence_used": ["This system is fully local."],
            "next_state": {"thread_touch": []},
        }
    )

    def _dry_run_traced_turn(user_input, **kwargs):
        kwargs.pop("dry_candidate_text", None)
        kwargs["max_repair"] = 0
        return real_run_traced_turn(user_input, dry_candidate_text=DRY_JSON, **kwargs)

    state_dir, logs_dir = _bootstrap(tmp_path)
    monkeypatch.setattr(turn_api_mod, "run_traced_turn", _dry_run_traced_turn)

    def _boom(*args, **kwargs):
        raise AssertionError("flow.run_flow_turn must never be called for a pipeline-mode dashboard")

    monkeypatch.setattr(turn_api_mod, "run_flow_turn", _boom)

    profile = load_profile(None)
    httpd = server_mod.create_server(
        host="127.0.0.1",
        port=0,
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=profile,
        model=None,
        base_url="http://127.0.0.1:11434",
    )
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05})
    thread.daemon = True
    thread.start()
    time.sleep(0.1)
    try:
        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        assert status == 200
        trace = json.loads(body)
        assert len(trace["stages"]) == 12
        assert trace["final_decision"]["decision"] == "accept"

        status, _, body = _get(port, "/api/session")
        session = json.loads(body)
        assert session["runtime_config"]["session_mode"] == "pipeline"
        turns = session["turns"]
        assert turns[0]["mode"] == "pipeline"
        assert turns[0]["turn_id"] == trace["turn_id"]
    finally:
        _stop(httpd, thread)


# ---------------------------------------------------------------------------
# SSE: field_before / traveled / field_after events, in order, for a flow
# turn — exercised directly at the Dashboard level (no socket needed: SSE
# publish is synchronous within run_turn()).
# ---------------------------------------------------------------------------


def test_flow_turn_broadcasts_field_before_traveled_field_after_events(monkeypatch, tmp_path):
    state_dir, logs_dir = _bootstrap(tmp_path)
    monkeypatch.setattr(turn_api_mod, "run_flow_turn", _dry_run_flow_turn)
    profile = load_profile(None)
    dashboard = turn_api_mod.Dashboard(
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=profile,
        session_mode="flow",
    )
    q = dashboard.subscribe()
    try:
        dashboard.run_turn("let's talk about something")
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        event_names = [line.split("\n", 1)[0].removeprefix("event: ") for line in events]
        assert event_names == ["field_before", "traveled", "field_after", "turn_complete"]
        traveled_payload = json.loads(events[1].split("\n")[1][len("data: "):])
        assert traveled_payload["displayed_text"].startswith("(dry reply to)")
    finally:
        dashboard.unsubscribe(q)


# ---------------------------------------------------------------------------
# Observer pane: not available for flow-mode turns, guarded not crashed.
# ---------------------------------------------------------------------------


def test_observer_stage_guarded_for_flow_turns(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path, session_mode="flow")
    try:
        status, _, body = _post(port, "/api/turn", {"text": "hello"})
        turn_id = json.loads(body)["turn_id"]

        # observer disabled by default -> 403 regardless of turn kind
        status, _, _ = _post(port, "/api/observer/stage", {"turn_id": turn_id})
        assert status == 403
    finally:
        _stop(httpd, thread)
