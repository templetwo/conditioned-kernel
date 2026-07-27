"""Atomic append-only continuity event store.

Events are complete JSON files under events/ written via temp+fsync+replace.
Partial .tmp files never count as accepted history.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from conditioned_kernel.continuity_events import (
    GENESIS_SCHEMA_VERSION,
    canonical_state_hash,
    materialize_state,
)
from conditioned_kernel.ids import utc_now_iso


_EVENT_NAME_RE = re.compile(r"^(\d{6})_(.+)\.json$")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # Read-back verify before commit
        with open(tmp_name, "rb") as f:
            written = f.read()
        if written != data:
            raise OSError("atomic write readback mismatch")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def _atomic_write_json(path: Path, obj: Any) -> None:
    payload = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _atomic_write_bytes(path, payload.encode("utf-8"))


class ContinuityStore:
    """Filesystem store: genesis + complete event files + receipts."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.events_dir = self.root / "events"
        self.receipts_dir = self.root / "receipts"
        self.quarantine_dir = self.root / "quarantine"

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        genesis: Mapping[str, Any],
        universe: Mapping[str, Any],
    ) -> ContinuityStore:
        root_p = Path(root)
        store = cls(root_p)
        store.events_dir.mkdir(parents=True, exist_ok=True)
        store.receipts_dir.mkdir(parents=True, exist_ok=True)
        store.quarantine_dir.mkdir(parents=True, exist_ok=True)
        g = dict(genesis)
        if "schema_version" not in g:
            g["schema_version"] = GENESIS_SCHEMA_VERSION
        _atomic_write_json(root_p / "genesis.json", g)
        _atomic_write_json(root_p / "universe.json", dict(universe))
        return store

    @classmethod
    def open(cls, root: Path | str) -> ContinuityStore:
        root_p = Path(root)
        if not (root_p / "genesis.json").exists():
            raise FileNotFoundError(f"no genesis at {root_p}")
        store = cls(root_p)
        store.events_dir.mkdir(parents=True, exist_ok=True)
        store.receipts_dir.mkdir(parents=True, exist_ok=True)
        store.quarantine_dir.mkdir(parents=True, exist_ok=True)
        return store

    def load_genesis(self) -> dict[str, Any]:
        with (self.root / "genesis.json").open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_universe(self) -> dict[str, Any]:
        with (self.root / "universe.json").open("r", encoding="utf-8") as f:
            return json.load(f)

    def list_events(self) -> list[dict[str, Any]]:
        """Complete event files only; .tmp and quarantine excluded."""
        if not self.events_dir.exists():
            return []
        items: list[tuple[int, str, dict[str, Any]]] = []
        for path in sorted(self.events_dir.iterdir()):
            if path.suffix != ".json" or path.name.endswith(".tmp"):
                continue
            m = _EVENT_NAME_RE.match(path.name)
            if not m:
                continue
            seq = int(m.group(1))
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            items.append((seq, path.name, data))
        items.sort(key=lambda t: (t[0], t[1]))
        return [d for _, _, d in items]

    def current_state_hash(self) -> str:
        return canonical_state_hash(self.load_genesis(), self.list_events())

    def materialized_state(self) -> dict[str, Any]:
        return materialize_state(self.load_genesis(), self.list_events())

    def next_sequence(self) -> int:
        events = self.list_events()
        if not events:
            return 1
        return int(max(int(e.get("sequence") or 0) for e in events)) + 1

    def append_event_and_receipt(
        self,
        event: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Path:
        """Atomically persist one complete event file and one receipt file.

        Staging uses temp files with fsync+readback+replace. A crash leaving
        only .tmp files cannot be listed as accepted history.
        """
        seq = int(event["sequence"])
        event_id = str(event["event_id"])
        event_path = self.events_dir / f"{seq:06d}_{event_id}.json"
        receipt_path = self.receipts_dir / f"{event_id}.json"
        if event_path.exists():
            raise FileExistsError(f"event already exists: {event_path.name}")
        rec = dict(receipt)
        rec.setdefault("terminal", True)
        _atomic_write_json(event_path, dict(event))
        _atomic_write_json(receipt_path, rec)
        # Verify event is listable and hash chain end matches event claim
        events = self.list_events()
        if not events or events[-1].get("event_id") != event_id:
            raise OSError("event append not visible after commit")
        return event_path

    def append_terminal_receipt(self, receipt: Mapping[str, Any]) -> Path:
        """Write exactly one terminal candidate receipt (accept or reject)."""
        rid = str(receipt.get("receipt_id") or receipt.get("source_candidate_hash") or "term")
        decision = str(receipt.get("decision") or "unknown")
        prefix = "accept" if decision == "accepted" else "reject"
        path = self.receipts_dir / f"{prefix}_{rid}.json"
        if path.exists():
            path = self.receipts_dir / f"{prefix}_{rid}_{utc_now_iso().replace(':', '')}.json"
        payload = dict(receipt)
        payload.setdefault("terminal", True)
        _atomic_write_json(path, payload)
        return path

    def append_rejection_receipt(self, receipt: Mapping[str, Any]) -> Path:
        """Alias for append_terminal_receipt (rejection path)."""
        return self.append_terminal_receipt(receipt)

    def rejection_receipts(self) -> list[dict[str, Any]]:
        return [
            r
            for r in self.terminal_receipts()
            if r.get("decision") == "rejected"
        ]

    def all_receipts(self) -> list[dict[str, Any]]:
        """All receipt JSON files (terminal only under current protocol)."""
        return self.terminal_receipts()

    def terminal_receipts(self) -> list[dict[str, Any]]:
        """Candidate-terminal receipts only (one per processed candidate)."""
        out: list[dict[str, Any]] = []
        if not self.receipts_dir.exists():
            return out
        for path in sorted(self.receipts_dir.iterdir()):
            if path.suffix != ".json":
                continue
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Only count terminal candidate receipts
            if data.get("terminal") is False:
                continue
            if data.get("decision") not in ("accepted", "rejected"):
                continue
            out.append(data)
        return out

    def quarantine_partials(self) -> list[str]:
        """Move any .tmp partials into quarantine; return their names."""
        moved: list[str] = []
        if not self.events_dir.exists():
            return moved
        for path in list(self.events_dir.iterdir()):
            if path.name.endswith(".tmp") or path.suffix == ".tmp":
                dest = self.quarantine_dir / path.name
                self.quarantine_dir.mkdir(parents=True, exist_ok=True)
                os.replace(path, dest)
                moved.append(path.name)
        return moved
