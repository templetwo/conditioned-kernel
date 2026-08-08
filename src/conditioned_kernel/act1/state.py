"""Shared live state for ACT-1 runner + TUI."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


CELLS = (
    ("A", "Q4", False),
    ("B", "Q4", True),
    ("C", "Q2", False),
    ("D", "Q2", True),
)


@dataclass
class CellStats:
    cell_id: str
    quant: str
    think: bool
    done: int = 0
    total: int = 0
    authority_errors: int = 0
    disagreements: int = 0
    last_case: str = ""
    last_model: str = ""
    last_gate: str = ""
    last_final: str = ""
    status: str = "pending"  # pending | running | done | error
    wall_s: float = 0.0
    tokens: int = 0


@dataclass
class EventRecord:
    ts: float
    cell_id: str
    case_id: str
    case_title: str
    case_class: str
    model_claim: str
    gate_result: str
    gate_reason: str
    kernel_final: str
    authority_held: bool
    wall_s: float
    eval_tokens: int
    preview: str


@dataclass
class Act1LiveState:
    title: str = "ACT-1 Authority Crossover"
    ollama_version: str = ""
    host: str = "M3 Pro / 18 GB"
    phase: str = "idle"
    current_cell: str = ""
    current_case: str = ""
    message: str = "waiting to start"
    cells: dict[str, CellStats] = field(default_factory=dict)
    events: list[EventRecord] = field(default_factory=list)
    authority_errors_total: int = 0
    generations_done: int = 0
    generations_total: int = 0
    paused: bool = False
    stop_requested: bool = False
    finished: bool = False
    started_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def init_cells(self, n_cases: int) -> None:
        with self.lock:
            self.cells = {}
            for cid, quant, think in CELLS:
                self.cells[cid] = CellStats(
                    cell_id=cid,
                    quant=quant,
                    think=think,
                    total=n_cases,
                )
            self.generations_total = n_cases * len(CELLS)

    def set_phase(self, phase: str, message: str = "") -> None:
        with self.lock:
            self.phase = phase
            if message:
                self.message = message

    def begin_event(self, cell_id: str, case_id: str, title: str) -> None:
        with self.lock:
            self.current_cell = cell_id
            self.current_case = f"{case_id} — {title}"
            self.message = f"generating {cell_id}/{case_id}…"
            if cell_id in self.cells:
                self.cells[cell_id].status = "running"
                self.cells[cell_id].last_case = case_id

    def record_event(self, ev: EventRecord) -> None:
        with self.lock:
            self.events.append(ev)
            self.generations_done += 1
            c = self.cells.get(ev.cell_id)
            if c:
                c.done += 1
                c.last_case = ev.case_id
                c.last_model = ev.model_claim
                c.last_gate = ev.gate_result
                c.last_final = ev.kernel_final
                c.wall_s += ev.wall_s
                c.tokens += ev.eval_tokens
                if not ev.authority_held:
                    c.authority_errors += 1
                    self.authority_errors_total += 1
                if ev.model_claim != ev.gate_result and ev.gate_result not in ("N/A",):
                    c.disagreements += 1
                if c.done >= c.total:
                    c.status = "done"
            self.message = (
                f"{ev.cell_id}/{ev.case_id}: model={ev.model_claim} "
                f"gate={ev.gate_result} final={ev.kernel_final}"
            )

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "title": self.title,
                "ollama_version": self.ollama_version,
                "host": self.host,
                "phase": self.phase,
                "current_cell": self.current_cell,
                "current_case": self.current_case,
                "message": self.message,
                "cells": {k: asdict(v) for k, v in self.cells.items()},
                "authority_errors_total": self.authority_errors_total,
                "generations_done": self.generations_done,
                "generations_total": self.generations_total,
                "paused": self.paused,
                "finished": self.finished,
                "elapsed_s": (time.time() - self.started_at) if self.started_at else 0,
                "recent_events": [asdict(e) for e in self.events[-8:]],
            }
