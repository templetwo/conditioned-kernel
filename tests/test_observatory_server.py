"""Tests for the Interior View dashboard HTTP server
(observatory.server / observatory.turn_api).

Covers the handoff task's item 4 (server: boot on an ephemeral port,
GET /api/session, POST /api/turn -> trace, GET trace by id, brief
markdown, feedback write-only-append, replay persists nothing, static
index served, 404/403 on traversal attempts) and item 5 (observer off by
default: endpoints inert, frontend config says disabled, no external
hosts anywhere in server code).

The server is started on port 0 (OS-assigned) and driven at the raw wire
level with `http.client`, mirroring the manual self-check the server/
frontend builders already ran (see the RUN 00.9A dashboard build's
selfcheck script) but as real pytest assertions.

No live Ollama required: `Dashboard.run_turn` calls
`conditioned_kernel.observatory.turn_api.run_traced_turn`, which this
file monkeypatches to a thin wrapper that forces the repo's established
`dry_candidate_text` offline stub (see tests/test_pipeline_dry.py) before
delegating to the real `observatory.trace.run_traced_turn` — so every
assertion below still exercises the real trace/compute/server code, only
the model call itself is stubbed.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
import time
from pathlib import Path

from conditioned_kernel.edge import load_profile
from conditioned_kernel.observatory import server as server_mod
from conditioned_kernel.observatory import turn_api as turn_api_mod
from conditioned_kernel.observatory.trace import run_traced_turn as real_run_traced_turn

GOAL = (
    "Demonstrate conditioned-kernel substrate gain over bare generation "
    "on a small local model under Jetson Orin Nano 8GB edge budgets."
)

DRY_JSON = json.dumps(
    {
        "answer": (
            "Design intent is edge-first substrate conditioning: keep the model small "
            "and local, and measure gain under Jetson Orin Nano budgets without cloud "
            "or sensors."
        ),
        "evidence_used": [
            "This system is fully local.",
            "Edge target: jetson_orin_nano_8gb (one model at a time).",
        ],
        "next_state": {"thread_touch": ["thread_min_model"]},
    }
)


# ---------------------------------------------------------------------------
# Bootstrap + wire helpers
# ---------------------------------------------------------------------------


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
                "session_id": "sess_server_test",
                "receipt_count_24h": 0,
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


def _dry_run_traced_turn(user_input, **kwargs):
    """Offline stand-in for observatory.trace.run_traced_turn: forces
    dry_candidate_text + max_repair=0 so POST /api/turn can be exercised
    at the wire level with zero network calls and a deterministic
    accept. Only patched inside this test process (monkeypatch reverts it
    automatically) — never touches the shipped module on disk."""
    kwargs.pop("dry_candidate_text", None)
    kwargs["max_repair"] = 0
    return real_run_traced_turn(user_input, dry_candidate_text=DRY_JSON, **kwargs)


def _start(monkeypatch, tmp_path, *, observer_enabled: bool = False):
    state_dir, logs_dir = _bootstrap(tmp_path)
    monkeypatch.setattr(turn_api_mod, "run_traced_turn", _dry_run_traced_turn)
    profile = load_profile(None)
    httpd = server_mod.create_server(
        host="127.0.0.1",
        port=0,
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=profile,
        model=None,
        base_url="http://127.0.0.1:11434",
        observer_enabled=observer_enabled,
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


def _get(port: int, path: str) -> tuple[int, dict, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _post(port: int, path: str, payload: dict) -> tuple[int, dict, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Boot + GET /api/session
# ---------------------------------------------------------------------------


def test_server_boots_on_ephemeral_port_and_serves_session(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        assert port > 0
        status, _, body = _get(port, "/api/session")
        assert status == 200
        session = json.loads(body)
        assert session["session_id"] == "sess_server_test"
        assert session["turns"] == []
        assert session["runtime_config"]["paths"]["state_dir"] == str(state_dir)
        assert session["runtime_config"]["paths"]["logs_dir"] == str(logs_dir)
    finally:
        _stop(httpd, thread)


# ---------------------------------------------------------------------------
# POST /api/turn -> trace; GET trace by id; brief endpoint
# ---------------------------------------------------------------------------


def test_post_turn_returns_trace_visible_in_session_and_fetchable_by_id(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        assert status == 200
        trace = json.loads(body)
        turn_id = trace["turn_id"]
        assert turn_id
        assert len(trace["stages"]) == 12
        assert trace["final_decision"]["decision"] == "accept"

        status, _, body = _get(port, "/api/session")
        turns = json.loads(body)["turns"]
        assert any(t["turn_id"] == turn_id for t in turns)

        status, _, body = _get(port, f"/api/turn/{turn_id}/trace")
        assert status == 200
        assert json.loads(body)["turn_id"] == turn_id

        status, _, body = _get(port, "/api/turn/latest/trace")
        assert status == 200
        assert json.loads(body)["turn_id"] == turn_id

        status, _, _ = _get(port, "/api/turn/does-not-exist/trace")
        assert status == 404

        # a missing/blank body -> 400, never a silent 200
        status, _, _ = _post(port, "/api/turn", {"text": ""})
        assert status == 400
    finally:
        _stop(httpd, thread)


def test_brief_endpoint_returns_markdown(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, _, body = _post(port, "/api/turn", {"text": "What model is this?"})
        turn_id = json.loads(body)["turn_id"]

        status, headers, body = _get(port, f"/api/turn/{turn_id}/brief")
        assert status == 200
        assert "markdown" in headers.get("Content-Type", "")
        text = body.decode("utf-8")
        assert turn_id in text
        assert "Full compiled packet" in text
        assert "Full TurnTrace JSON" in text

        status, _, _ = _get(port, "/api/turn/does-not-exist/brief")
        assert status == 404

        # GET /api/turn/latest/brief is worth supporting (README §12)
        status, _, _ = _get(port, "/api/turn/latest/brief")
        assert status == 200
    finally:
        _stop(httpd, thread)


# ---------------------------------------------------------------------------
# POST /api/feedback — write-only, exactly one JSONL line per call, never
# read back into the pipeline
# ---------------------------------------------------------------------------


def test_feedback_appends_exactly_one_jsonl_line_per_call(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        turn_id = json.loads(body)["turn_id"]

        fb_path = logs_dir / "operator_feedback.jsonl"
        assert not fb_path.exists()

        status, _, body = _post(
            port,
            "/api/feedback",
            {"turn_id": turn_id, "marks": ["useful", "wrong_rejection"], "note": "test note"},
        )
        assert status == 200
        assert json.loads(body)["ok"] is True

        assert fb_path.exists()
        lines = fb_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["turn_id"] == turn_id
        assert record["note"] == "test note"
        assert record["marks"] == ["useful", "wrong_rejection"]

        status, _, _ = _post(port, "/api/feedback", {"turn_id": turn_id, "marks": [], "note": "second"})
        assert status == 200
        lines2 = fb_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines2) == 2
        assert lines2[0] == lines[0]  # first line untouched by the second append
    finally:
        _stop(httpd, thread)


def test_operator_feedback_jsonl_is_referenced_only_by_its_write_sink():
    """Static-inspection guard matching the conventions report's own grep:
    logs/operator_feedback.jsonl must be a pure write sink. The only
    module in the package allowed to name it is turn_api.py's
    Dashboard.feedback — nothing else, and nothing reads it back into the
    pipeline."""
    import conditioned_kernel

    pkg_root = Path(conditioned_kernel.__file__).resolve().parent
    hits: dict[str, int] = {}
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "operator_feedback" in text:
            hits[str(path.relative_to(pkg_root))] = text.count("operator_feedback")
    assert set(hits) == {"observatory/turn_api.py"}, hits


# ---------------------------------------------------------------------------
# POST /api/replay — persists nothing
# ---------------------------------------------------------------------------


def test_replay_persists_nothing(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        turn_id = json.loads(body)["turn_id"]

        state_files = ["current.json", "threads.json", "methods.json"]
        before_state = {f: (state_dir / f).read_bytes() for f in state_files}
        log_files = ["candidates.jsonl", "receipts.jsonl", "history.jsonl"]
        before_logs = {
            f: (logs_dir / f).read_bytes() if (logs_dir / f).exists() else None for f in log_files
        }

        status, _, body = _post(
            port,
            "/api/replay",
            {"turn_id": turn_id, "sections": {"recent": False, "state": False}},
        )
        assert status == 200
        result = json.loads(body)
        assert result["persists"] is False
        assert result["diff"]
        assert result["checks"]

        after_state = {f: (state_dir / f).read_bytes() for f in state_files}
        assert before_state == after_state

        after_logs = {
            f: (logs_dir / f).read_bytes() if (logs_dir / f).exists() else None for f in log_files
        }
        assert before_logs == after_logs

        # unknown turn id -> 404, never a silent empty replay
        status, _, _ = _post(port, "/api/replay", {"turn_id": "does-not-exist"})
        assert status == 404
    finally:
        _stop(httpd, thread)


# ---------------------------------------------------------------------------
# Static file serving + traversal protection
# ---------------------------------------------------------------------------


def test_static_index_is_served(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, headers, body = _get(port, "/")
        assert status == 200
        assert "text/html" in headers.get("Content-Type", "")
        assert b"Interior View" in body
    finally:
        _stop(httpd, thread)


def test_static_traversal_attempt_never_succeeds(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        status, _, _ = _get(port, "/../../../../../../etc/passwd")
        # server.py's _serve_static rejects any resolved path outside
        # STATIC_DIR with 403 forbidden; whatever the exact code, a
        # traversal attempt must never resolve to 200.
        assert status != 200
        assert status in (403, 404)

        status, _, _ = _get(port, "/does-not-exist-asset.txt")
        assert status == 404
    finally:
        _stop(httpd, thread)


# ---------------------------------------------------------------------------
# 5. Observer off by default
# ---------------------------------------------------------------------------


def test_observer_endpoints_inert_and_frontend_config_says_disabled(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path, observer_enabled=False)
    try:
        status, _, body = _get(port, "/api/observer/status")
        assert status == 200
        assert json.loads(body)["enabled"] is False

        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        turn_id = json.loads(body)["turn_id"]

        # neither staging nor sending is usable without --observer
        status, _, _ = _post(port, "/api/observer/stage", {"turn_id": turn_id})
        assert status != 200

        status, _, _ = _post(port, "/api/observer/send", {"turn_id": turn_id})
        assert status != 200

        # the frontend's own config payload says disabled too — this is
        # what GET /api/session hands the UI to decide whether to draw the
        # observer pane at all
        status, _, body = _get(port, "/api/session")
        server_cfg = json.loads(body)["runtime_config"]["server"]
        assert server_cfg["observer_enabled"] is False
    finally:
        _stop(httpd, thread)


def test_observer_enabled_stages_but_never_auto_sends(monkeypatch, tmp_path):
    """With --observer set, staging works and discloses the seven fields
    spec §11 requires, but /api/observer/send is a stub that reports
    ok=False — nothing is ever actually transmitted (criterion 22)."""
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path, observer_enabled=True)
    try:
        status, _, body = _get(port, "/api/observer/status")
        assert json.loads(body)["enabled"] is True

        status, _, body = _post(port, "/api/turn", {"text": "Summarize design intent."})
        turn_id = json.loads(body)["turn_id"]

        status, _, body = _post(
            port,
            "/api/observer/stage",
            {"turn_id": turn_id, "ask": "explain", "payload_kind": "compact"},
        )
        assert status == 200
        staged = json.loads(body)
        disclosure = staged["disclosure"]
        for field in (
            "destination",
            "payload_kind",
            "byte_count",
            "includes_current_user_message",
            "includes_prior_dialogue_bodies",
            "includes_full_packet_json",
            "includes_file_paths",
            "persists_nothing",
        ):
            assert field in disclosure, field
        assert disclosure["persists_nothing"] is True
        assert disclosure["includes_full_packet_json"] is False  # compact brief only

        status, _, body = _post(
            port,
            "/api/observer/send",
            {"turn_id": turn_id, "ask": "explain", "payload_kind": "compact"},
        )
        assert status == 200
        sent = json.loads(body)
        assert sent["ok"] is False
        assert sent["stub"] is True
    finally:
        _stop(httpd, thread)


def test_no_external_hosts_in_observatory_server_code():
    """Acceptance criterion 19: the dashboard makes no external network
    request with --observer off (and this build never wires a real send
    at all — see observer_send's stub above). Every http(s):// literal
    anywhere in the observatory package must point at the local Ollama
    daemon (127.0.0.1 / localhost) or be a runtime-formatted local bind
    string — never a fixed external host."""
    import conditioned_kernel.observatory as obs_pkg

    pkg_dir = Path(obs_pkg.__file__).resolve().parent
    pattern = re.compile(r"https?://([\w.{}-]+)")
    offenders = []
    for path in pkg_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            host = m.group(1)
            if host.startswith("127.0.0.1") or host.startswith("localhost") or host.startswith("{"):
                continue
            offenders.append((str(path.relative_to(pkg_dir)), m.group(0)))
    assert offenders == [], offenders


def test_no_external_hosts_in_static_frontend_assets():
    """Same guard applied to the shipped static frontend (tech constraint:
    no external CDN assets, no remote fonts, no internet dependency)."""
    import conditioned_kernel.observatory as obs_pkg

    static_dir = Path(obs_pkg.__file__).resolve().parent / "static"
    pattern = re.compile(r"https?://[^\"'\s)]+")
    offenders = []
    for path in static_dir.rglob("*"):
        if not path.is_file() or path.suffix not in (".html", ".css", ".js"):
            continue
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            offenders.append((str(path.relative_to(static_dir)), m.group(0)))
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# SSE smoke test (bonus: exercises the /api/stream route from the spec §12
# endpoint table; not itself required by the task's item 4/5 list)
# ---------------------------------------------------------------------------


def test_sse_stream_connects_and_server_survives_client_disconnect(monkeypatch, tmp_path):
    httpd, thread, port, state_dir, logs_dir = _start(monkeypatch, tmp_path)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/stream")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "event-stream" in resp.getheader("Content-Type", "")
        first_chunk = resp.fp.read1(64) if hasattr(resp.fp, "read1") else resp.read(64)
        assert first_chunk.startswith(b":")
        conn.close()  # simulate client disconnect mid-stream
        time.sleep(0.2)

        status, _, _ = _get(port, "/api/session")
        assert status == 200
    finally:
        _stop(httpd, thread)
