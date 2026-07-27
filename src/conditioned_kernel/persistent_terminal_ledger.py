"""RUN 00.8A — append-only durable terminalization ledger.

Keyed by (manifest_sha256, cell_id). Survives process restart.
Rejects duplicate terminalization, unplanned cells, and overwrites.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

LEDGER_SCHEMA_VERSION = "ck.persistent_terminal_ledger.v1"
LEDGER_FILENAME = "terminal_ledger.jsonl"
LEDGER_META_FILENAME = "terminal_ledger.meta.json"


class PersistentLedgerError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


class PersistentTerminalLedger:
    """Filesystem-backed append-only terminal ledger."""

    def __init__(
        self,
        path: Path | str,
        *,
        manifest_sha256: str,
        planned_cell_ids: set[str] | frozenset[str],
    ) -> None:
        self.root = Path(path)
        self.manifest_sha256 = str(manifest_sha256)
        self.planned_cell_ids = set(planned_cell_ids)
        self.root.mkdir(parents=True, exist_ok=True)
        self._ledger_path = self.root / LEDGER_FILENAME
        self._meta_path = self.root / LEDGER_META_FILENAME
        self._rows: dict[str, dict[str, Any]] = {}
        self._load()

    @classmethod
    def open(
        cls,
        path: Path | str,
        *,
        manifest_sha256: str,
        planned_cell_ids: set[str] | frozenset[str],
    ) -> "PersistentTerminalLedger":
        """Open from path only (no in-memory-only mode)."""
        return cls(path, manifest_sha256=manifest_sha256, planned_cell_ids=planned_cell_ids)

    def _load(self) -> None:
        if self._meta_path.is_file():
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            if str(meta.get("manifest_sha256")) != self.manifest_sha256:
                raise PersistentLedgerError(
                    "LEDGER_MANIFEST_MISMATCH",
                    f"ledger manifest {meta.get('manifest_sha256')} != {self.manifest_sha256}",
                )
        else:
            self._write_meta()

        if not self._ledger_path.is_file():
            self._ledger_path.write_text("", encoding="utf-8")
            return

        with self._ledger_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    raise PersistentLedgerError(
                        "LEDGER_CORRUPT_LINE", f"line {line_no}"
                    ) from e
                cid = str(row.get("cell_id") or "")
                msha = str(row.get("manifest_sha256") or "")
                if msha != self.manifest_sha256:
                    raise PersistentLedgerError("LEDGER_ROW_MANIFEST_MISMATCH", cid)
                if cid in self._rows:
                    raise PersistentLedgerError("LEDGER_DUPLICATE_ON_DISK", cid)
                self._rows[cid] = row

    def _write_meta(self) -> None:
        meta = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "manifest_sha256": self.manifest_sha256,
            "planned_cell_count": len(self.planned_cell_ids),
            "scientific_completion": False,
            "headline_eligible": False,
            "scientific_status": "commissioning_safety_only",
        }
        tmp = self._meta_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, self._meta_path)

    def has(self, cell_id: str) -> bool:
        return cell_id in self._rows

    def get(self, cell_id: str) -> dict[str, Any] | None:
        return self._rows.get(cell_id)

    def terminal_count(self) -> int:
        return len(self._rows)

    def all_rows(self) -> list[dict[str, Any]]:
        return [self._rows[cid] for cid in sorted(self._rows.keys())]

    def append_terminal(self, terminal_record: Mapping[str, Any]) -> dict[str, Any]:
        """Append one terminal record. Fail closed on dups/unplanned/wrong manifest."""
        cell_id = str(terminal_record.get("cell_id") or "")
        if not cell_id:
            raise PersistentLedgerError("MISSING_CELL_ID")
        if cell_id not in self.planned_cell_ids:
            raise PersistentLedgerError("UNPLANNED_CELL", cell_id)
        if cell_id in self._rows:
            raise PersistentLedgerError("DUPLICATE_TERMINALIZATION", cell_id)

        row = dict(terminal_record)
        row["manifest_sha256"] = self.manifest_sha256
        row["ledger_schema_version"] = LEDGER_SCHEMA_VERSION
        row["scientific_completion"] = False
        row["headline_eligible"] = False
        row["row_sha256"] = sha256_hex(
            canonical_json_bytes({k: v for k, v in row.items() if k != "row_sha256"})
        )

        line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        # Crash-safe append: write line + fsync
        with self._ledger_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

        self._rows[cell_id] = row
        return row

    def verify_integrity(self) -> dict[str, Any]:
        """Reload from disk and verify no corruption / duplicate keys."""
        disk_ids: list[str] = []
        if self._ledger_path.is_file():
            with self._ledger_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    cid = str(row["cell_id"])
                    if cid in disk_ids:
                        raise PersistentLedgerError("LEDGER_DUPLICATE_ON_DISK", cid)
                    disk_ids.append(cid)
                    # verify row hash if present
                    if "row_sha256" in row:
                        body = {k: v for k, v in row.items() if k != "row_sha256"}
                        if sha256_hex(canonical_json_bytes(body)) != row["row_sha256"]:
                            raise PersistentLedgerError("LEDGER_ROW_HASH_MISMATCH", cid)
        return {
            "ok": True,
            "terminal_n": len(disk_ids),
            "manifest_sha256": self.manifest_sha256,
        }

    def missing_cell_ids(self) -> list[str]:
        return sorted(cid for cid in self.planned_cell_ids if cid not in self._rows)
