"""Interior View dashboard HTTP server — stdlib only.

`http.server.ThreadingHTTPServer`, nothing else. No web framework was
added: `pyproject.toml` carries only `httpx` (used elsewhere for the
Ollama transport), and per the handoff's non-negotiable constraint this
server does not add a dependency. Binds to `127.0.0.1` by default; makes
no external network request itself (the only outbound call in this whole
package's reach is `generate.OllamaClient` talking to the *local* Ollama
daemon the pipeline already talks to for `ck ask` / `ck chat` — nothing
here calls out to the internet).

Routing is a small `if/elif` ladder over `urlsplit(self.path).path`
rather than a router class or regex table, because the endpoint surface
is fixed and small (spec §12's table plus the observer surface from
§11) and a bigger abstraction would not pay for itself here.
"""

from __future__ import annotations

import json
import mimetypes
import queue
import signal
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from conditioned_kernel.edge import EdgeProfile, load_profile
from conditioned_kernel.observatory.turn_api import Dashboard

STATIC_DIR = (Path(__file__).resolve().parent / "static").resolve()

_MIME_OVERRIDES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}

_FALLBACK_INDEX_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Interior View</title></head><body style="
    "'font-family:system-ui;background:#171614;color:#DDD5C8;padding:2rem'>"
    "<h1>Interior View</h1>"
    "<p>The dashboard API is up. The static frontend has not been built at "
    f"<code>{STATIC_DIR}</code> yet.</p>"
    "<p>Try <code>/api/session</code> directly.</p>"
    "</body></html>"
)


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "InteriorView/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003 - stdlib override
        sys.stderr.write("[ck dashboard] " + (fmt % args) + "\n")

    @property
    def dashboard(self) -> Dashboard:
        return self.server.dashboard  # type: ignore[attr-defined]

    # ---- response helpers ----

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_text(self, status: int, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"invalid JSON body: {e}") from e
        return data if isinstance(data, dict) else {}

    # ---- GET ----

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        path = urlsplit(self.path).path
        try:
            if path == "/api/session":
                return self._send_json(200, self.dashboard.session_payload())
            if path == "/api/stream":
                return self._handle_stream()
            if path == "/api/observer/status":
                return self._send_json(200, {"enabled": self.dashboard.observer_enabled})
            if path.startswith("/api/turn/") and path.endswith("/trace"):
                turn_id = path[len("/api/turn/") : -len("/trace")]
                trace = self.dashboard.get_trace(turn_id)
                if trace is None:
                    return self._send_json(404, {"error": f"unknown turn_id {turn_id!r}"})
                return self._send_json(200, trace)
            if path.startswith("/api/turn/") and path.endswith("/brief"):
                turn_id = path[len("/api/turn/") : -len("/brief")]
                text = self.dashboard.get_full_brief(turn_id)
                if text is None:
                    return self._send_json(404, {"error": f"unknown turn_id {turn_id!r}"})
                return self._send_text(200, text, "text/markdown; charset=utf-8")
            if path.startswith("/api/"):
                return self._send_json(404, {"error": f"no such endpoint {path!r}"})
            return self._serve_static(path)
        except Exception as e:  # noqa: BLE001 - never crash the accept loop
            return self._send_json(500, {"error": f"{type(e).__name__}: {e}"})

    # ---- POST ----

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            body = self._read_json_body()
        except ValueError as e:
            return self._send_json(400, {"error": str(e)})
        try:
            if path == "/api/turn":
                return self._post_turn(body)
            if path == "/api/feedback":
                return self._post_feedback(body)
            if path == "/api/replay":
                return self._post_replay(body)
            if path == "/api/observer/stage":
                return self._post_observer_stage(body)
            if path == "/api/observer/send":
                return self._post_observer_send(body)
            if path.startswith("/api/"):
                return self._send_json(404, {"error": f"no such endpoint {path!r}"})
            return self._send_json(404, {"error": "not found"})
        except KeyError as e:
            return self._send_json(404, {"error": str(e)})
        except ValueError as e:
            return self._send_json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001 - never crash the accept loop
            return self._send_json(500, {"error": f"{type(e).__name__}: {e}"})

    def _post_turn(self, body: dict[str, Any]) -> None:
        text = str(body.get("text") or "").strip()
        if not text:
            return self._send_json(400, {"error": "text is required"})
        data = self.dashboard.run_turn(text)
        return self._send_json(200, data)

    def _post_feedback(self, body: dict[str, Any]) -> None:
        record = self.dashboard.feedback(
            turn_id=body.get("turn_id"),
            marks=body.get("marks") or [],
            note=body.get("note") or "",
        )
        return self._send_json(200, {"ok": True, "recorded": record})

    def _post_replay(self, body: dict[str, Any]) -> None:
        turn_id = body.get("turn_id")
        if not turn_id:
            return self._send_json(400, {"error": "turn_id is required"})
        result = self.dashboard.replay(turn_id, body.get("sections") or {})
        return self._send_json(200, result)

    def _post_observer_stage(self, body: dict[str, Any]) -> None:
        if not self.dashboard.observer_enabled:
            return self._send_json(403, {"error": "observer disabled — start with --observer"})
        turn_id = body.get("turn_id")
        if not turn_id:
            return self._send_json(400, {"error": "turn_id is required"})
        result = self.dashboard.observer_stage(
            turn_id=turn_id,
            ask=body.get("ask") or "explain",
            payload_kind=body.get("payload_kind") or "compact",
            include_prior_dialogue=bool(body.get("include_prior_dialogue", False)),
        )
        return self._send_json(200, result)

    def _post_observer_send(self, body: dict[str, Any]) -> None:
        if not self.dashboard.observer_enabled:
            return self._send_json(403, {"error": "observer disabled — start with --observer"})
        turn_id = body.get("turn_id")
        if not turn_id:
            return self._send_json(400, {"error": "turn_id is required"})
        result = self.dashboard.observer_send(
            turn_id=turn_id,
            ask=body.get("ask") or "explain",
            payload_kind=body.get("payload_kind") or "compact",
            include_prior_dialogue=bool(body.get("include_prior_dialogue", False)),
        )
        return self._send_json(200, result)

    # ---- SSE ----

    def _handle_stream(self) -> None:
        """`text/event-stream`, one `event: stage` per completed
        `StageTrace` and one `event: turn_complete` per finished turn (see
        `Dashboard._broadcast_turn`). No `Content-Length` is sent by
        design: HTTP/1.1 treats a response with neither `Content-Length`
        nor `Transfer-Encoding: chunked` as body-terminated-by-connection-
        close, which is exactly SSE's model — the connection simply stays
        open until the client disconnects."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = self.dashboard.subscribe()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    message = q.get(timeout=15.0)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.dashboard.unsubscribe(q)

    # ---- static files ----

    def _serve_static(self, url_path: str) -> None:
        rel = url_path.lstrip("/") or "index.html"
        candidate = (STATIC_DIR / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIR)
        except ValueError:
            return self._send_text(403, "forbidden", "text/plain; charset=utf-8")
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists() or not candidate.is_file():
            if rel in ("", "index.html"):
                return self._send_text(200, _FALLBACK_INDEX_HTML, "text/html; charset=utf-8")
            return self._send_text(404, "not found", "text/plain; charset=utf-8")
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _guess_mime(candidate))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


def create_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    profile: EdgeProfile | None = None,
    model: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
    observer_enabled: bool = False,
) -> ThreadingHTTPServer:
    """Build (but do not start) a bound `ThreadingHTTPServer`. Split out
    from `serve()` so tests can bind on port 0, inspect
    `httpd.server_address`, and shut it down without ever printing to
    stderr or touching `webbrowser`."""
    dashboard = Dashboard(
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=profile or load_profile(None),
        model=model,
        base_url=base_url,
        host=host,
        port=port,
        observer_enabled=observer_enabled,
    )
    httpd = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    httpd.daemon_threads = True
    httpd.dashboard = dashboard  # type: ignore[attr-defined]
    return httpd


def _install_sigterm_handler(httpd: ThreadingHTTPServer) -> None:
    """`except KeyboardInterrupt` in `serve()` only covers interactive
    Ctrl-C (SIGINT with its default disposition). A process supervisor —
    or anyone stopping this non-interactively with plain `kill <pid>` —
    sends SIGTERM instead, which Python does not turn into an exception by
    default; without this, `serve_forever()` would simply be killed
    mid-loop rather than reaching the `httpd.shutdown()` /
    `httpd.server_close()` in `serve()`'s `finally` block.

    `BaseServer.shutdown()` blocks until `serve_forever()`'s own loop
    notices the shutdown request and exits — calling it from *inside* a
    signal handler running on the same thread that's blocked in
    `serve_forever()` would deadlock, so the handler hands the call off to
    a short-lived helper thread instead. Registering a signal handler is
    only valid from the interpreter's main thread; skip it quietly
    (`serve()` is still exposed to embedders/tests via `create_server`
    without this convenience) if this ever runs somewhere else.
    """

    def _on_sigterm(signum: int, frame: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
    except (ValueError, OSError):
        pass


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    profile: EdgeProfile | None = None,
    model: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
    observer_enabled: bool = False,
    open_browser: bool = True,
) -> int:
    """Bind, print the localhost URL, optionally open a browser tab, and
    block in `serve_forever()` until Ctrl-C. Returns 0 on a clean
    Ctrl-C shutdown, 1 if the socket could not be bound."""
    try:
        httpd = create_server(
            host=host,
            port=port,
            state_dir=state_dir,
            logs_dir=logs_dir,
            profile=profile,
            model=model,
            base_url=base_url,
            observer_enabled=observer_enabled,
        )
    except OSError as e:
        print(f"[ck dashboard] failed to bind {host}:{port}: {e}", file=sys.stderr)
        return 1

    bound_host, bound_port = httpd.server_address[0], httpd.server_address[1]
    url = f"http://{bound_host}:{bound_port}/"
    print(f"[ck dashboard] Interior View serving at {url}", file=sys.stderr)
    if observer_enabled:
        print(
            "[ck dashboard] observer pane ENABLED (--observer) — default off, "
            "no automatic send",
            file=sys.stderr,
        )
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - headless/no-display is not fatal
            pass

    _install_sigterm_handler(httpd)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[ck dashboard] shutting down", file=sys.stderr)
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


__all__ = ["DashboardRequestHandler", "create_server", "serve", "STATIC_DIR"]
