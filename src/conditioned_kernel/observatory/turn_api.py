"""Dashboard business logic — session/turn store, one-traced-turn wiring,
feedback logging, replay wiring, and observer payload staging.

This module has no HTTP-framework dependency (it never imports
`http.server`); `server.py` is a thin stdlib routing layer on top of the
`Dashboard` class defined here. Keeping the split means the observable
behaviour here can be exercised directly, without opening a socket.

Nothing here changes what the pipeline does. `Dashboard.run_turn` calls
`observatory.trace.run_traced_turn`, which calls the real
`pipeline.run_turn` exactly once — this module never reimplements a turn,
never mutates `state/` itself, and only ever appends to
`logs/operator_feedback.jsonl`, a file the pipeline does not read back
(spec §13's "observation only" contract).
"""

from __future__ import annotations

import json
import os
import queue
import tempfile
import threading
from pathlib import Path
from typing import Any

from conditioned_kernel.edge import (
    DEFAULT_PROFILE_ID,
    EdgeProfile,
    edge_status_report,
    load_profile,
)
from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.observatory import brief, compute
from conditioned_kernel.observatory import replay as replay_mod
from conditioned_kernel.observatory.trace import TurnTrace, run_traced_turn
from conditioned_kernel.paths import default_logs_dir, default_state_dir
from conditioned_kernel.state import SubstrateState, append_jsonl

# ---------------------------------------------------------------------------
# Turn summaries — the shape GET /api/session's "turns" list and the
# conversation column consume. Keeps full traces out of the list payload.
# ---------------------------------------------------------------------------


def _summarize_turn(data: dict[str, Any]) -> dict[str, Any]:
    fd = data.get("final_decision") or {}
    return {
        "turn_id": data.get("turn_id"),
        "session_id": data.get("session_id"),
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at"),
        "user_input": data.get("user_input"),
        "decision": fd.get("decision"),
        "label": fd.get("label"),
        "answer": fd.get("answer"),
        "pass_count": len(data.get("passes") or []),
        "packet_bytes": data.get("packet_bytes"),
        "violations": fd.get("violations") or [],
        "advisories": fd.get("advisories") or [],
        "observations": data.get("observations") or [],
        "error": data.get("error"),
    }


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


class TurnStore:
    """In-memory + on-disk store of traced turns, so `GET` endpoints work
    across requests and survive a server restart. Persists to
    `<logs_dir>/dashboard/turns/<turn_id>.json` — a dashboard-owned
    directory, never read by the pipeline (same write-only-ledger
    convention as `logs/*.jsonl`, just one JSON document per turn rather
    than an append-only line log, because a turn's trace needs to be
    replaced-in-place-by-id-lookup rather than scanned sequentially)."""

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = Path(logs_dir)
        self.dir = self.logs_dir / "dashboard" / "turns"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._order: list[str] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        files = sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            turn_id = data.get("turn_id")
            if not turn_id:
                continue
            self._by_id[turn_id] = data
            self._order.append(turn_id)

    def add(self, trace: TurnTrace) -> dict[str, Any]:
        data = trace.to_dict()
        with self._lock:
            if trace.turn_id not in self._by_id:
                self._order.append(trace.turn_id)
            self._by_id[trace.turn_id] = data
            _atomic_write_json(self.dir / f"{trace.turn_id}.json", data)
        return data

    def get(self, turn_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._by_id.get(turn_id)

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._order:
                return None
            return self._by_id.get(self._order[-1])

    def list_summaries(self, *, session_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._order)
            by_id = dict(self._by_id)
        out = []
        for turn_id in ids:
            data = by_id[turn_id]
            if session_id is not None and data.get("session_id") != session_id:
                continue
            out.append(_summarize_turn(data))
        return out


class Dashboard:
    """Owns the runtime configuration one `ck dashboard` process was
    started with, the turn store, and the SSE subscriber list. One
    instance per server process."""

    def __init__(
        self,
        *,
        state_dir: Path | None = None,
        logs_dir: Path | None = None,
        profile: EdgeProfile | None = None,
        model: str | None = None,
        base_url: str = "http://127.0.0.1:11434",
        host: str = "127.0.0.1",
        port: int = 8765,
        observer_enabled: bool = False,
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir else default_state_dir()
        self.logs_dir = Path(logs_dir) if logs_dir else default_logs_dir()
        self.profile = profile or load_profile(DEFAULT_PROFILE_ID)
        self.model = model
        self.base_url = base_url
        self.host = host
        self.port = port
        self.observer_enabled = bool(observer_enabled)

        self.store = TurnStore(self.logs_dir)
        self._turn_lock = threading.Lock()
        self._sub_lock = threading.Lock()
        self._subscribers: list[queue.Queue[str]] = []

    # ---- session / conversation column ----

    def current_session_id(self) -> str:
        state = SubstrateState.load(state_dir=self.state_dir, logs_dir=self.logs_dir)
        return str(state.current.get("session_id") or "sess_unknown")

    def session_payload(self) -> dict[str, Any]:
        state = SubstrateState.load(state_dir=self.state_dir, logs_dir=self.logs_dir)
        session_id = str(state.current.get("session_id") or "sess_unknown")
        report = edge_status_report(self.profile)
        use_model = self.model or self.profile.model
        runtime_config = {
            "kernel": {
                "model": use_model,
                "mode": self.profile.mode,
                "think": bool(self.profile.think),
                "temperature": self.profile.temperature,
                "seed": self.profile.seed,
                "num_ctx": self.profile.num_ctx,
                "keep_alive": self.profile.keep_alive,
                "timeout_s": self.profile.timeout_s,
                "stream": bool(self.profile.stream),
                "endpoint": self.base_url,
            },
            "edge_profile": self.profile.to_dict(),
            "edge_report": report,
            "acceptance_mode": "companion",
            "paths": {
                "state_dir": str(self.state_dir),
                "logs_dir": str(self.logs_dir),
            },
            "server": {
                "host": self.host,
                "port": self.port,
                "observer_enabled": self.observer_enabled,
            },
        }
        return {
            "session_id": session_id,
            "goal": state.current.get("goal", ""),
            "open_thread_count": len(state.open_threads()),
            "recent_turns_on_disk": len(state.recent_turns()),
            "runtime_config": runtime_config,
            "turns": self.store.list_summaries(session_id=session_id),
        }

    # ---- turns ----

    def run_turn(self, text: str) -> dict[str, Any]:
        """Run exactly one turn through the real pipeline (via
        `run_traced_turn`), store the resulting trace, and publish its
        stages over SSE. Serialized by a lock: this is a single-operator
        local dashboard, and two concurrent turns against the same
        `state_dir` would otherwise race on `accept_candidate`'s writes —
        a race that exists in the pipeline itself, not introduced here."""
        with self._turn_lock:
            trace = run_traced_turn(
                text,
                model=self.model,
                state_dir=self.state_dir,
                logs_dir=self.logs_dir,
                base_url=self.base_url,
                profile=self.profile,
            )
            data = self.store.add(trace)
        self._broadcast_turn(trace)
        return data

    def get_trace(self, turn_id: str) -> dict[str, Any] | None:
        if turn_id in ("latest", ""):
            return self.store.latest()
        return self.store.get(turn_id)

    def get_full_brief(self, turn_id: str) -> str | None:
        trace = self.get_trace(turn_id)
        if trace is None:
            return None
        return brief.build_full_debug_brief(trace)

    # ---- feedback (write-only, never read back — spec §13) ----

    def feedback(
        self, *, turn_id: Any, marks: list[Any], note: Any
    ) -> dict[str, Any]:
        record = {
            "turn_id": turn_id,
            "marks": [str(m) for m in (marks or [])],
            "note": str(note or ""),
            "ts": utc_now_iso(),
        }
        append_jsonl(self.logs_dir / "operator_feedback.jsonl", record)
        return record

    # ---- replay (persists nothing — spec §7, §10) ----

    def replay(self, turn_id: str, sections: dict[str, Any] | None) -> dict[str, Any]:
        trace = self.get_trace(turn_id)
        if trace is None:
            raise KeyError(f"unknown turn_id {turn_id!r}")
        passes = trace.get("passes") or []
        if not passes:
            raise ValueError(f"turn {turn_id!r} has no passes to replay")
        fp = passes[-1]
        packet = fp.get("packet") or trace.get("packet") or {}
        if not packet:
            raise ValueError(f"turn {turn_id!r} has no packet to replay")
        # trace.py's TurnTrace.runtime_config is a flat dict (model, mode,
        # temperature, seed, num_ctx, keep_alive, think, ...) — see
        # trace.run_traced_turn's own construction of it.
        rc = trace.get("runtime_config") or {}
        result = replay_mod.run_replay(
            packet,
            model=rc.get("model"),
            mode=rc.get("mode"),
            temperature=rc.get("temperature"),
            seed=rc.get("seed"),
            num_ctx=rc.get("num_ctx"),
            keep_alive=rc.get("keep_alive"),
            think=bool(rc.get("think", False)),
            evidence_used=fp.get("evidence_used") or [],
            thread_touch=fp.get("thread_touch") or [],
            sections=sections,
        )
        result["turn_id"] = turn_id
        return result

    # ---- observer (build-time only, default off, no auto-send — spec §11) ----

    def observer_stage(
        self,
        *,
        turn_id: str,
        ask: str,
        payload_kind: str,
        include_prior_dialogue: bool,
    ) -> dict[str, Any]:
        trace = self.get_trace(turn_id)
        if trace is None:
            raise KeyError(f"unknown turn_id {turn_id!r}")
        if payload_kind == "full":
            markdown = brief.build_full_debug_brief(trace)
            disclosure = {
                "destination": "cloud (Claude, build-time observer only)",
                "payload_kind": "full_debug_brief",
                "byte_count": compute.bytes_len(markdown),
                "includes_current_user_message": True,
                "includes_prior_dialogue_bodies": True,
                "includes_full_packet_json": True,
                "includes_file_paths": True,
                "persists_nothing": True,
            }
        else:
            markdown, disclosure = brief.build_compact_brief(
                trace, ask=ask, include_prior_dialogue=include_prior_dialogue
            )
        return {
            "turn_id": turn_id,
            "ask": ask,
            "ask_label": brief.ASK_LABELS.get(ask, ask),
            "system_prompt": brief.OBSERVER_SYSTEM_PROMPT,
            "payload": markdown,
            "disclosure": disclosure,
        }

    def observer_send(
        self,
        *,
        turn_id: str,
        ask: str,
        payload_kind: str,
        include_prior_dialogue: bool,
    ) -> dict[str, Any]:
        """No cloud call is configured in this build. The Interior View
        dashboard makes no external network request regardless of
        `--observer` (acceptance criterion 19) — this endpoint only ever
        stages a payload and reports that plainly, never a silent failure
        (spec §11)."""
        staged = self.observer_stage(
            turn_id=turn_id,
            ask=ask,
            payload_kind=payload_kind,
            include_prior_dialogue=include_prior_dialogue,
        )
        staged["ok"] = False
        staged["stub"] = True
        staged["message"] = (
            "Cloud send is not configured in this build. The payload above was staged "
            "but nothing was transmitted — the dashboard makes no external network "
            "request. Wiring a real Claude API call is a separate, explicit decision "
            "outside this build's scope."
        )
        return staged

    # ---- SSE pub-sub ----

    def subscribe(self) -> "queue.Queue[str]":
        q: queue.Queue[str] = queue.Queue()
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[str]") -> None:
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        with self._sub_lock:
            subs = list(self._subscribers)
        if not subs:
            return
        data = json.dumps(payload, ensure_ascii=False)
        message = f"event: {event_type}\ndata: {data}\n\n"
        for q in subs:
            q.put(message)

    def _broadcast_turn(self, trace: TurnTrace) -> None:
        """One SSE event per completed `StageTrace`, then a `turn_complete`
        event. `run_traced_turn` drives the real pipeline synchronously and
        exposes no mid-turn hook (see trace.py's module docstring — adding
        one would mean touching `pipeline.py`, which this build avoids as
        unnecessary), so these are published back-to-back immediately after
        the one real turn finishes rather than genuinely concurrently with
        it. The content of every event is still the pipeline's own real
        per-stage status and flag, never fabricated timing or fabricated
        content — only the *pacing* is post-hoc."""
        for stage in trace.stages:
            self._publish("stage", {"turn_id": trace.turn_id, "stage": stage.to_dict()})
        self._publish(
            "turn_complete",
            {"turn_id": trace.turn_id, "decision": trace.final_decision.get("decision")},
        )


__all__ = ["Dashboard", "TurnStore"]
