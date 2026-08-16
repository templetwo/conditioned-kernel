"""Filesystem substrate: load truth, write atomic JSON, append JSONL."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.paths import default_logs_dir, default_state_dir

# Studio first-flow: bound prior dialogue by UTF-8 bytes so packet budget
# cannot be blown by one long answer. Drop oldest until under the cap.
RECENT_TURNS_MAX_BYTES = 1200
RECENT_TURN_USER_MAX_CHARS = 200
RECENT_TURN_ANSWER_MAX_CHARS = 280

# Owned design-intent sentence (Anthony, 2026-08-16). Distinct from `goal`,
# which is the research-claim string the laboratory measures against.
DEFAULT_DESIGN_INTENT = (
    "Conditioned Kernel is the tiny local model and program on a Jetson that can "
    "eventually act as the brain of the companion, fully offline if the net is gone. "
    "The project exists to prove or disprove that changing the riverbed (the "
    "substrate) can make that small model punch far above its weight on token "
    "output. The intent itself stays flowing, like the river."
)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
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


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def _clip_text(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    if max_chars <= 1:
        return s[:max_chars]
    return s[: max_chars - 1].rstrip() + "…"


def recent_turns_byte_size(turns: list[dict[str, Any]]) -> int:
    """UTF-8 size of the compact serialized recent_turns list."""
    return len(
        json.dumps(turns, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def fit_recent_turns(
    turns: list[dict[str, Any]],
    *,
    max_bytes: int = RECENT_TURNS_MAX_BYTES,
) -> list[dict[str, Any]]:
    """Drop oldest entries (then hard-clip newest) until under max_bytes."""
    out = [dict(t) for t in turns if isinstance(t, dict)]
    while out and recent_turns_byte_size(out) > max_bytes:
        if len(out) > 1:
            out.pop(0)
            continue
        # Single entry still too large: shrink answer then user.
        only = dict(out[0])
        ans = str(only.get("answer") or "")
        user = str(only.get("user") or "")
        if len(ans) > 40:
            only["answer"] = _clip_text(ans, max(40, len(ans) // 2))
            out = [only]
            continue
        if len(user) > 40:
            only["user"] = _clip_text(user, max(40, len(user) // 2))
            out = [only]
            continue
        # Last resort: empty answer body, keep a stub.
        only["answer"] = _clip_text(ans, 20)
        only["user"] = _clip_text(user, 20)
        out = [only]
        if recent_turns_byte_size(out) > max_bytes:
            return []
        break
    return out


@dataclass
class SubstrateState:
    """In-memory snapshot of durable substrate files."""

    root: Path
    logs_dir: Path
    current: dict[str, Any] = field(default_factory=dict)
    threads: list[dict[str, Any]] = field(default_factory=list)
    methods: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        state_dir: Path | None = None,
        logs_dir: Path | None = None,
    ) -> "SubstrateState":
        root = Path(state_dir) if state_dir else default_state_dir()
        logs = Path(logs_dir) if logs_dir else default_logs_dir()
        return cls(
            root=root,
            logs_dir=logs,
            current=_read_json(root / "current.json", {}),
            threads=_read_json(root / "threads.json", []),
            methods=_read_json(root / "methods.json", []),
        )

    def open_threads(self) -> list[dict[str, Any]]:
        return [t for t in self.threads if t.get("status") == "open"]

    def fact_list(self) -> list[str]:
        flags = self.current.get("flags") or {}
        edge = flags.get("edge_target") or "jetson_orin_nano_8gb"
        facts = [
            "This system is fully local.",
            "Sensors are out of scope for v0." if not flags.get("sensors", False) else "Sensors enabled.",
            "The model is a replaceable linguistic transducer.",
            f"Edge target: {edge} (one model at a time)."
            if flags.get("one_model_only", True)
            else f"Edge target: {edge}.",
            f"One repair pass is allowed (max={flags.get('max_repair_passes', 1)}).",
            f"Active profile: {self.current.get('active_profile', 'orin_nano_8gb')}.",
            f"Current goal: {self.current.get('goal', '')}".strip(),
        ]
        intent = str(self.current.get("design_intent") or "").strip()
        if intent:
            facts.append(f"Design intent: {intent}")
        return [f for f in facts if f]

    def save_current(self) -> None:
        self.current["updated_at"] = utc_now_iso()
        self.current["open_thread_count"] = len(self.open_threads())
        _atomic_write_json(self.root / "current.json", self.current)

    def save_threads(self) -> None:
        _atomic_write_json(self.root / "threads.json", self.threads)

    def log_history(self, record: dict[str, Any]) -> None:
        append_jsonl(self.logs_dir / "history.jsonl", record)

    def log_candidate(self, record: dict[str, Any]) -> None:
        append_jsonl(self.logs_dir / "candidates.jsonl", record)

    def log_receipt(self, record: dict[str, Any]) -> None:
        append_jsonl(self.logs_dir / "receipts.jsonl", record)

    def log_error(self, record: dict[str, Any]) -> None:
        append_jsonl(self.logs_dir / "errors.jsonl", record)

    def recent_turns(self) -> list[dict[str, Any]]:
        raw = self.current.get("recent_turns") or []
        if not isinstance(raw, list):
            return []
        return [t for t in raw if isinstance(t, dict)]

    def append_recent_turn(
        self,
        user_input: str,
        answer: str,
        *,
        max_bytes: int = RECENT_TURNS_MAX_BYTES,
    ) -> list[dict[str, Any]]:
        """Append an accepted exchange; byte-cap by dropping oldest first."""
        entry = {
            "user": _clip_text(str(user_input), RECENT_TURN_USER_MAX_CHARS),
            "answer": _clip_text(str(answer), RECENT_TURN_ANSWER_MAX_CHARS),
            "ts": utc_now_iso(),
        }
        turns = self.recent_turns() + [entry]
        fitted = fit_recent_turns(turns, max_bytes=max_bytes)
        self.current["recent_turns"] = fitted
        self.save_current()
        return fitted

    def begin_new_session(self) -> str:
        """Clear dialogue memory and bump session_id. Goal/intent/threads stay."""
        stamp = utc_now_iso().replace(":", "").replace("-", "")[:15]
        new_id = f"sess_{stamp}"
        self.current["session_id"] = new_id
        self.current["recent_turns"] = []
        self.save_current()
        return new_id

    def apply_state_updates(self, updates: dict[str, Any] | None) -> list[str]:
        """Apply closed, allowlisted deltas only. Returns notes of what changed."""
        if not updates:
            return []
        notes: list[str] = []

        touch = updates.get("thread_touch") or []
        if isinstance(touch, list):
            for tid in touch:
                for t in self.threads:
                    if t.get("id") == tid or t.get("title") == tid:
                        t["last_touched_at"] = utc_now_iso()
                        notes.append(f"touched_thread:{t.get('id')}")

        # proposed_note is intentionally not persisted (M1 audit F10):
        # repair scaffolding leaked into state and is a contamination risk.

        if notes:
            self.save_current()
            self.save_threads()
        return notes
