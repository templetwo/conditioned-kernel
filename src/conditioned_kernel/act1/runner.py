"""ACT-1 runner — generates candidates, applies gates, updates live state."""

from __future__ import annotations

import json
import random
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from conditioned_kernel.act1.corpus import default_corpus
from conditioned_kernel.act1.gates import extract_model_claim, kernel_final, run_gate
from conditioned_kernel.act1.state import CELLS, Act1LiveState, EventRecord

# OP models (same host; Ollama 0.32.6 for ACT-1)
MODEL_Q4 = "sovereign-survival-9b-q4-ctx32k"
MODEL_Q2 = "sovereign-q2-9b-ctx32k"
NUM_CTX = 32768
GATE_VERSION = "act1-gate-v1"
COMPILE_POLICY = "static-v0"


@dataclass
class Act1Config:
    ollama_host: str = "http://127.0.0.1:11434"
    out_dir: Path | None = None
    cells: tuple[str, ...] = ("A", "B", "C", "D")
    max_cases: int | None = None  # None = all 8
    seed: int = 42


def _ollama_version(host: str) -> str:
    try:
        with urllib.request.urlopen(f"{host}/api/version", timeout=5) as r:
            return json.loads(r.read().decode()).get("version", "?")
    except Exception:
        return "unreachable"


def _generate(
    host: str,
    model: str,
    prompt: str,
    think: bool,
    timeout_s: int = 900,
) -> dict[str, Any]:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": think,
        "options": {"num_ctx": NUM_CTX},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = json.loads(resp.read().decode())
    raw["_client_elapsed_s"] = time.perf_counter() - t0
    return raw


def run_act1(
    state: Act1LiveState,
    config: Act1Config | None = None,
    on_tick: Callable[[], None] | None = None,
) -> dict[str, Any]:
    cfg = config or Act1Config()
    random.seed(cfg.seed)
    corpus = default_corpus()
    if cfg.max_cases is not None:
        corpus = corpus[: cfg.max_cases]

    state.started_at = time.time()
    state.ollama_version = _ollama_version(cfg.ollama_host)
    if state.ollama_version in ("", "unreachable"):
        raise RuntimeError(
            "Ollama is not reachable at "
            f"{cfg.ollama_host}. ACT-1 is live-only; start ollama and retry."
        )
    state.init_cells(len(corpus))
    state.set_phase("running", "ACT-1 live screen started")

    out_dir = cfg.out_dir or (
        Path.home() / ".grok/docs/run01-survival/act1_runs" / time.strftime("%Y%m%dT%H%M%S")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []

    cell_map = {c[0]: c for c in CELLS}
    selected = [cell_map[c] for c in cfg.cells if c in cell_map]

    for cell_id, quant, think in selected:
        if state.stop_requested:
            break
        model = MODEL_Q4 if quant == "Q4" else MODEL_Q2
        for case in corpus:
            while state.paused and not state.stop_requested:
                time.sleep(0.1)
                if on_tick:
                    on_tick()
            if state.stop_requested:
                break

            state.begin_event(cell_id, case.id, case.title)
            if on_tick:
                on_tick()

            try:
                raw = _generate(cfg.ollama_host, model, case.prompt, think)
                text = raw.get("response") or ""
                wall = float(raw.get("_client_elapsed_s") or 0)
                toks = int(raw.get("eval_count") or 0)
            except Exception as e:
                text = f"[generation_error] {e}"
                wall = 0.0
                toks = 0
                raw = {"error": repr(e)}

            model_claim = extract_model_claim(text, case.id)
            gate = run_gate(case.gate_kind, case.gate_payload, text)
            kfinal = kernel_final(case.case_class, gate, model_claim)
            authority_held = not kfinal.get("accepted_contradiction", False)
            # for executable FAIL+model PASS, system stays FAIL → held
            if case.case_class == "executable":
                authority_held = kfinal.get("system_state") == gate.result

            rec = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "cell_id": cell_id,
                "quant": quant,
                "think": think,
                "model": model,
                "num_ctx": NUM_CTX,
                "ollama_version": state.ollama_version,
                "gate_version": GATE_VERSION,
                "compile_policy": COMPILE_POLICY,
                "case_id": case.id,
                "case_title": case.title,
                "case_class": case.case_class,
                "model_claim": model_claim,
                "gate_result": gate.result,
                "gate_reason": gate.reason,
                "gate_details": gate.details,
                "kernel_final": kfinal,
                "authority_held": authority_held,
                "wall_s": wall,
                "eval_tokens": toks,
                "response_preview": text[:500],
                "response": text,
                "raw_metrics": {
                    k: raw.get(k)
                    for k in (
                        "eval_count",
                        "eval_duration",
                        "prompt_eval_count",
                        "total_duration",
                        "load_duration",
                    )
                    if k in raw
                },
            }
            receipts.append(rec)
            (out_dir / f"{cell_id}_{case.id}.json").write_text(json.dumps(rec, indent=2))

            state.record_event(
                EventRecord(
                    ts=time.time(),
                    cell_id=cell_id,
                    case_id=case.id,
                    case_title=case.title,
                    case_class=case.case_class,
                    model_claim=model_claim,
                    gate_result=gate.result,
                    gate_reason=gate.reason,
                    kernel_final=str(kfinal.get("system_state") or kfinal.get("kernel_final")),
                    authority_held=authority_held,
                    wall_s=wall,
                    eval_tokens=toks,
                    preview=text[:160].replace("\n", " "),
                )
            )
            if on_tick:
                on_tick()

    summary = {
        "protocol": "ACT-1",
        "gate_version": GATE_VERSION,
        "compile_policy": COMPILE_POLICY,
        "live": True,
        "ollama_version": state.ollama_version,
        "num_ctx": NUM_CTX,
        "generations": len(receipts),
        "authority_errors": state.authority_errors_total,
        "cells": {k: v.__dict__ for k, v in state.cells.items()},
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "primary_invariant": "zero accepted contradictions",
        "primary_pass": state.authority_errors_total == 0,
    }
    (out_dir / "00_summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "00_all_receipts.json").write_text(json.dumps(receipts, indent=2))

    state.finished = True
    state.set_phase(
        "done",
        f"ACT-1 screen complete · auth_errors={state.authority_errors_total} · "
        f"wrote {out_dir}",
    )
    return summary
