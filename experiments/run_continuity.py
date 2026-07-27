#!/usr/bin/env python3
"""Continuity experiment runner — two episodes across a real process boundary.

Preregistered in docs/CONTINUITY_EXPERIMENT.md. This orchestrator exists to make
the boundary genuine rather than notional:

    Episode A   subprocess #1   does work, writes state, artifacts frozen
    boundary    model evicted from VRAM, parent process reaps the child
    Episode B   subprocess #2   fresh PID, primes, then resumes from context only

Distinct PIDs are recorded on the receipt. Without them this risks measuring
ordinary within-window context retention rather than continuity.

Each arm gets its OWN Episode B subprocess so arms cannot contaminate each other
through a shared prompt cache.

Usage:
    python experiments/run_continuity.py                       # full run
    python experiments/run_continuity.py --limit 2 --dry       # offline smoke
    python experiments/run_continuity.py --episode a --task-file …   # internal
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conditioned_kernel.compile import (  # noqa: E402
    CANDIDATE_FORMAT,
    build_arrival_packet,
    build_model_input,
)
from conditioned_kernel.continuity import (  # noqa: E402
    build_bare_serialized,
    build_broken_packet,
    context_hashes,
    score_episode_b,
)
from conditioned_kernel.edge import DEFAULT_PROFILE_ID, load_profile  # noqa: E402
from conditioned_kernel.continuity_gate import (  # noqa: E402
    ExecutionScope,
    verify_event_receipt_pair,
)
from conditioned_kernel.continuity_live import (  # noqa: E402
    live_plumbing_headline_policy,
    run_episode_a_live,
    run_episode_b_live,
)
from conditioned_kernel.continuity_store import ContinuityStore  # noqa: E402
from conditioned_kernel.generate import DEFAULT_BASE_URL, OllamaClient, RunStatus  # noqa: E402
from conditioned_kernel.outcomes import (  # noqa: E402
    EmptyManifestError,
    ExecutionOutcome,
    ManifestCell,
    TerminalLedger,
    TerminalStatus,
    build_manifest,
    outcome_from_inference,
)
from conditioned_kernel.state import SubstrateState  # noqa: E402

ARMS = ("bare_serialized", "ck_packet", "broken_packet")


def continuity_headline_policy() -> dict[str, Any]:
    """Legacy three-arm path policy (Episode A lifecycle deferred historically)."""
    return {
        "headline_eligible": False,
        "scientific_status": "deferred_episode_a_lifecycle",
        "headline_ineligible_reason": "episode_a_accept_persist_reload_not_implemented",
    }


# Re-export for tests / external callers
__all_live__ = (
    "episode_a_live",
    "episode_b_live",
    "live_plumbing_headline_policy",
    "run_live_plumbing",
)


def episode_a_live(
    task: dict[str, Any],
    model: str,
    prof: Any,
    *,
    store_root: Path,
    dry: bool = False,
    dry_candidate_text: str | None = None,
) -> dict[str, Any]:
    """Episode A worker: typed inference → continuity_gate → durable store."""
    r = run_episode_a_live(
        task,
        store_root=store_root,
        model=model,
        timeout_s=float(prof.timeout_s),
        num_ctx=int(prof.num_ctx),
        dry=dry,
        dry_candidate_text=dry_candidate_text,
        provenance={"model": model, "profile": prof.profile_id},
    )
    gate_dict = None
    if r.gate is not None:
        gate_dict = {
            "decision": r.gate.decision.value,
            "reason_code": r.gate.reason_code,
            "reason_codes": list(r.gate.reason_codes),
            "candidate_hash": r.gate.candidate_hash,
            "scientific_completion": bool(r.gate.receipt.get("scientific_completion")),
            "execution_scope": r.gate.receipt.get("execution_scope"),
            "events_n": len(r.gate.events),
            "event_id": r.gate.receipt.get("event_id"),
        }
    return {
        "pid": os.getpid(),
        "end_time": _now(),
        "mode": "live_plumbing",
        "store_path": r.store_path,
        "inference_status": r.inference_status,
        "inference": r.inference,
        "final_response": r.final_response,
        "gate": gate_dict,
        "gate_invocations": r.gate_invocations,
        "packet_hash": r.packet_hash,
        "events_n": r.events_n,
        "rejection_receipts_n": r.rejection_receipts_n,
        "scientific_completion": False,
        "dry_run": r.dry_run,
        "error": r.error,
    }


def episode_b_live(
    task: dict[str, Any],
    model: str,
    prof: Any,
    *,
    store_root: Path,
    dry: bool = False,
    invoke_model: bool = False,
) -> dict[str, Any]:
    """Episode B worker: fresh open of store → verified replay → packet."""
    start_pid, start_time = os.getpid(), _now()
    r = run_episode_b_live(
        task,
        store_root=store_root,
        model=model,
        timeout_s=float(prof.timeout_s),
        num_ctx=int(prof.num_ctx),
        dry=dry,
        invoke_model=invoke_model and not dry,
    )
    return {
        "pid": start_pid,
        "start_time": start_time,
        "end_time": _now(),
        "mode": "live_plumbing",
        "replay_ok": r.replay_ok,
        "state_hash": r.state_hash,
        "packet_hash": r.packet_hash,
        "relation_count": r.relation_count,
        "accepted_relations": r.accepted_relations,
        "packet": r.packet,
        "inference_status": r.inference_status,
        "inference": r.inference,
        "scientific_completion": False,
        "dry_run": r.dry_run,
        "used_episode_a_memory": r.used_episode_a_memory,
        "error": r.error,
    }

# Same rules the CK system prompt states, minus the compiled structure. Fixed
# here in code (and in the protocol) rather than chosen at run time, because
# whoever writes the bare condition decides the outcome.
# Two bare system prompts, because the first run conflated instruction with
# structure. CK's system prompt says "answer: short reply THAT MENTIONS THE
# GOAL" and its packet carries must_reference_goal; my original control said
# only "short reply". A 0.5B model follows the goal instruction literally and
# mentions nothing else -- so CK goal-echoed while the control answered, and
# the measured gap was partly instruction, not structure.
#
# fair  = byte-identical wording to CK's system prompt. Isolates STRUCTURE.
# plain = the original. Isolates INSTRUCTION+STRUCTURE together.
BARE_SYSTEM_FAIR = (
    "Local conditioned-kernel transducer. "
    "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
    "answer: short reply that mentions the goal. "
    "evidence_used: copy exact strings from facts or open_threads. "
    "next_state.thread_touch: array of real open_threads id values, or []. "
    "Never invent thread ids. No files, URLs, tools, or cloud."
)
BARE_SYSTEM_PLAIN = (
    "Local assistant. Return ONLY valid JSON with keys answer, evidence_used, next_state. "
    "answer: short reply. evidence_used: copy exact strings you relied on. "
    "next_state.thread_touch: array of thread ids, or []. "
    "No files, URLs, tools, or cloud."
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def evict(model: str) -> None:
    """Drop the model from VRAM so Episode B is a genuine cold load."""
    try:
        with httpx.Client(timeout=15.0) as c:
            c.post(f"{DEFAULT_BASE_URL}/api/generate", json={"model": model, "keep_alive": 0})
    except Exception:
        pass
    time.sleep(3)


def seed_state_dir(task: dict[str, Any], root: Path) -> Path:
    """Materialise the task's seed state as a real substrate directory."""
    seed = (task.get("episode_a") or {}).get("seed_state") or {}
    d = root / "state"
    d.mkdir(parents=True, exist_ok=True)
    flags = {"sensors": False, "tools": False, "cloud": False,
             "max_repair_passes": 1, "edge_target": "jetson_orin_nano_8gb",
             "one_model_only": True}
    (d / "current.json").write_text(json.dumps({
        "goal": seed.get("goal", ""),
        "active_profile": "orin_nano_8gb",
        "session_id": "sess_continuity",
        "flags": flags,
        "seed_facts": list(seed.get("facts") or []),
    }, indent=2))
    (d / "threads.json").write_text(json.dumps(list(seed.get("threads") or []), indent=2))
    (d / "methods.json").write_text("[]")
    return d


def artifacts_from(task: dict[str, Any], state: SubstrateState, extra_log: list[str]) -> dict:
    """The single frozen artifact set every arm derives from."""
    seed = (task.get("episode_a") or {}).get("seed_state") or {}
    return {
        "state": {"goal": state.current.get("goal", "")},
        "facts": list(seed.get("facts") or []) or state.fact_list(),
        "threads": list(seed.get("threads") or []),
        "episode_a_log": extra_log,
    }


# --------------------------------------------------------------------------
# Episode workers (run as subprocesses)
# --------------------------------------------------------------------------


def episode_a(task: dict[str, Any], model: str, prof: Any, dry: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ck_epA_") as tmp:
        root = Path(tmp)
        state_dir = seed_state_dir(task, root)
        state = SubstrateState.load(state_dir=state_dir, logs_dir=root / "logs")
        prompt = (task.get("episode_a") or {}).get("prompt", "")
        packet = build_arrival_packet(state, prompt, profile=prof, enforce_budget=True)
        text = ""
        if not dry:
            mi = build_model_input(packet, model=model, num_ctx=prof.num_ctx,
                                   temperature=prof.temperature, seed=prof.seed)
            res = OllamaClient(timeout=prof.timeout_s).run(mi)
            text = res.output or ""
        return {
            "pid": os.getpid(),
            "end_time": _now(),
            "prompt": prompt,
            "raw": text,
            "artifacts": artifacts_from(task, state, [f"episode_a answered: {text[:160]}"] if text else []),
        }


def episode_b(task: dict[str, Any], arm: str, artifacts: dict, model: str,
              prof: Any, dry: bool, bare_mode: str = "fair") -> dict[str, Any]:
    bare_system = BARE_SYSTEM_FAIR if bare_mode == "fair" else BARE_SYSTEM_PLAIN
    start_pid, start_time = os.getpid(), _now()
    with tempfile.TemporaryDirectory(prefix="ck_epB_") as tmp:
        root = Path(tmp)
        state_dir = seed_state_dir(task, root)
        state = SubstrateState.load(state_dir=state_dir, logs_dir=root / "logs")
        prompt = (task.get("episode_b") or {}).get("prompt", "")
        ck_packet = build_arrival_packet(state, prompt, profile=prof, enforce_budget=True)
        budget = len(json.dumps(ck_packet, ensure_ascii=False, separators=(",", ":")).encode())
        bare_text = build_bare_serialized(artifacts, budget)
        broken = build_broken_packet(ck_packet)

        client = OllamaClient(timeout=prof.timeout_s)
        primed = False
        if not dry:
            # Episode B is definitionally a cold load; prime so the measured
            # generation is not the first-after-load numeric mode.
            try:
                client.run(build_model_input(
                    build_arrival_packet(state, "warmup", profile=prof, enforce_budget=True),
                    model=model, num_ctx=prof.num_ctx))
                primed = True
            except Exception:
                pass

        if arm == "ck_packet":
            mi = build_model_input(ck_packet, model=model, num_ctx=prof.num_ctx,
                                   temperature=prof.temperature, seed=prof.seed)
        elif arm == "broken_packet":
            mi = build_model_input(broken, model=model, num_ctx=prof.num_ctx,
                                   temperature=prof.temperature, seed=prof.seed)
        else:
            # The bare arm must NOT receive the compiled packet. Wrapping the
            # naive dump in build_arrival_packet would hand the control the
            # state_digest, facts, threads and acceptance contract as well --
            # i.e. CK plus extra text, which is not a control at all. It gets a
            # plain chat message with the same system rules and the same
            # format= constraint, so the ONLY difference is structure.
            mi = {
                "schema_version": "ck.v0",
                "mode": "chat_json",
                "model": model,
                "packet_id": ck_packet["packet_id"],
                "payload": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": bare_system},
                        {"role": "user", "content": f"{bare_text}\n\nQUESTION: {prompt}"},
                    ],
                    "format": CANDIDATE_FORMAT,
                    "stream": False,
                    "options": {
                        "temperature": prof.temperature,
                        "seed": prof.seed,
                        "num_ctx": prof.num_ctx,
                    },
                },
            }

        # Dry plumbing is never a completed scientific observation.
        if dry:
            exec_outcome = ExecutionOutcome.dry_run_only(reason="continuity_dry")
            return {
                "arm": arm,
                "pid": start_pid,
                "start_time": start_time,
                "status": TerminalStatus.DRY_RUN_ONLY.value,
                "error": None,
                "primed": primed,
                "raw": None,
                "scores": {},
                "dry_run": True,
                "scientific_completion": False,
                "execution_outcome": exec_outcome.to_dict(),
                **context_hashes(ck_packet, bare_text, broken),
            }

        res = client.run(mi)
        # Never coerce a missing final response into "". Only observed output
        # (including genuine empty string) is scorable text.
        if res.observed:
            text = res.output if res.output is not None else ""
            scored = score_episode_b(text, task=task, packet=ck_packet, artifacts=artifacts)
            # Inference-layer status remains "completed" for quality-conditional
            # means. Scientific completion for continuity Episode B is deferred
            # until Episode A accept/persist is repaired (out of 00.6A scope).
            exec_outcome = ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output=text,
                scientific_completion=False,
                dry_run=False,
                quality_admitted=True,
                decision=None,
                reason_codes=("episode_b_observed", "scientific_completion_deferred"),
                error=None,
                inference=res.to_dict(),
            )
            row_status = RunStatus.COMPLETED.value
        else:
            text = None
            scored = {}
            exec_outcome = outcome_from_inference(res)
            row_status = exec_outcome.status.value

        return {
            "arm": arm,
            "pid": start_pid,
            "start_time": start_time,
            "status": row_status,
            "error": res.error,
            "primed": primed,
            "raw": text,
            "scores": scored,
            "dry_run": False,
            "scientific_completion": exec_outcome.scientific_completion,
            "execution_outcome": exec_outcome.to_dict(),
            **context_hashes(ck_packet, bare_text, broken),
        }


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------


def _spawn(args: list[str], payload: dict) -> dict:
    """Run a worker in its OWN process. The boundary is the point."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        pay = f.name
    out = pay + ".out"
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args, "--payload", pay, "--out-json", out],
        capture_output=True, text=True,
    )
    try:
        return json.loads(Path(out).read_text())
    except Exception:
        return {"error": f"worker failed rc={r.returncode}: {r.stderr[-400:]}"}
    finally:
        for p in (pay, out):
            Path(p).unlink(missing_ok=True)


def run_live_plumbing(
    tasks: list[dict[str, Any]],
    *,
    model: str,
    prof: Any,
    dry: bool,
    out: Path,
    store_base: Path,
    invoke_episode_b_model: bool = False,
    inject_final_response: str | None = None,
) -> dict[str, Any]:
    """Bounded live plumbing: Episode A → process boundary → fresh Episode B.

    scientific_completion_n is always 0. Headline ineligible (live_plumbing_only).
    """
    run_id = f"live_plumbing_{int(time.time())}"
    store_base.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    policy = live_plumbing_headline_policy()

    # Planned passages: (task, episode A) and (task, episode B)
    planned: list[ManifestCell] = []
    for t in tasks:
        tid = str(t.get("id"))
        planned.append(
            ManifestCell(
                run_id=run_id, task_id=tid, condition_id="live_ck", episode="A"
            )
        )
        planned.append(
            ManifestCell(
                run_id=run_id, task_id=tid, condition_id="live_ck", episode="B"
            )
        )
    ledger = TerminalLedger(planned, run_id=run_id)

    for t in tasks:
        tid = str(t.get("id"))
        store_root = store_base / tid
        dry_cand = inject_final_response
        if dry and dry_cand is None:
            # dry with no inject: pure plumbing without model or gate accept
            dry_cand = None

        # --- Episode A (subprocess) ---
        ep_a_payload = {
            "task": t,
            "store_root": str(store_root),
            "dry_candidate_text": dry_cand,
            "live_plumbing": True,
        }
        dry_flags = ["--dry"] if dry else []
        ep_a = _spawn(
            [
                "--episode", "a-live",
                "--model", model,
                "--profile", prof.profile_id,
                *dry_flags,
            ],
            ep_a_payload,
        )
        cell_a = next(c for c in planned if c.task_id == tid and c.episode == "A")
        if ep_a.get("error") and not ep_a.get("inference_status"):
            oc_a = ExecutionOutcome.not_run(
                cell=cell_a, reason="episode_a_worker_error"
            )
        elif dry and ep_a.get("dry_run") and ep_a.get("gate") is None:
            oc_a = ExecutionOutcome.dry_run_only(cell=cell_a, reason="live_plumbing_dry")
        elif ep_a.get("gate", {}).get("decision") == "accepted":
            oc_a = ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output=ep_a.get("final_response"),
                scientific_completion=False,
                dry_run=False,
                quality_admitted=True,
                decision="accept",
                reason_codes=("live_plumbing_accepted", "scientific_completion_deferred"),
                **ExecutionOutcome._cell_fields(cell_a),
            )
        elif ep_a.get("gate", {}).get("decision") == "rejected":
            oc_a = ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output=ep_a.get("final_response"),
                scientific_completion=False,
                dry_run=False,
                quality_admitted=False,
                decision="reject",
                reason_codes=tuple(ep_a.get("gate", {}).get("reason_codes") or ("rejected",)),
                **ExecutionOutcome._cell_fields(cell_a),
            )
        elif ep_a.get("inference_status") in (
            TerminalStatus.TIMEOUT.value,
            TerminalStatus.NO_FINAL_RESPONSE.value,
            TerminalStatus.TRANSPORT_ERROR.value,
            TerminalStatus.INVALID_RESPONSE.value,
        ):
            st = TerminalStatus(ep_a["inference_status"])
            oc_a = ExecutionOutcome.from_lifecycle(
                cell=cell_a,
                status=st,
                output=None,
                reason_codes=(ep_a["inference_status"],),
                error=ep_a.get("error"),
            )
        else:
            oc_a = ExecutionOutcome.not_run(
                cell=cell_a, reason=str(ep_a.get("error") or "episode_a_unknown")
            )
        ledger.record(cell_a.cell_id, oc_a)

        # Durable terminal facts: load receipts from disk and verify consistency.
        # Fail closed if disk receipt contradicts live-plumbing non-science rule.
        disk_receipts: list[dict[str, Any]] = []
        if store_root.exists() and (store_root / "genesis.json").exists():
            store = ContinuityStore.open(store_root)
            disk_receipts = store.terminal_receipts()
            events = store.list_events()
            for rec in disk_receipts:
                if rec.get("execution_scope") != ExecutionScope.LIVE_PLUMBING.value:
                    # offline inject path always uses live_plumbing scope from gate
                    if rec.get("execution_scope") not in (
                        ExecutionScope.LIVE_PLUMBING.value,
                        ExecutionScope.DRY_RUN.value,
                        None,  # pure dry without gate
                    ):
                        raise SystemExit(
                            f"RECEIPT_SCOPE_MISMATCH: {rec.get('execution_scope')}"
                        )
                if rec.get("scientific_completion") is True:
                    raise SystemExit(
                        "RECEIPT_SCIENCE_LIE: persisted scientific_completion=true "
                        "under live plumbing"
                    )
                if rec.get("decision") == "accepted":
                    matching = [
                        e for e in events if e.get("event_id") == rec.get("event_id")
                    ]
                    if not matching:
                        raise SystemExit(
                            f"RECEIPT_EVENT_MISSING: event_id={rec.get('event_id')}"
                        )
                    verify_event_receipt_pair(matching[0], rec)

        rows.append(
            {
                "task_id": tid,
                "episode": "A",
                **ep_a,
                "manifest_cell_id": cell_a.cell_id,
                "persisted_terminal_receipt": disk_receipts[-1] if disk_receipts else None,
            }
        )

        # --- Episode B (fresh subprocess; store path only) ---
        ep_b_payload = {
            "task": t,
            "store_root": str(store_root),
            "live_plumbing": True,
            "invoke_model": bool(invoke_episode_b_model) and not dry,
        }
        ep_b = _spawn(
            [
                "--episode", "b-live",
                "--model", model,
                "--profile", prof.profile_id,
                *dry_flags,
            ],
            ep_b_payload,
        )
        cell_b = next(c for c in planned if c.task_id == tid and c.episode == "B")
        if dry:
            oc_b = ExecutionOutcome.dry_run_only(cell=cell_b, reason="live_plumbing_dry")
        elif ep_b.get("replay_ok") is False:
            oc_b = ExecutionOutcome.from_lifecycle(
                cell=cell_b,
                status=TerminalStatus.COMPLETED_INVALID,
                output=None,
                reason_codes=("replay_failed",),
                error=ep_b.get("error"),
            )
        elif ep_b.get("replay_ok"):
            oc_b = ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output=None,
                scientific_completion=False,
                dry_run=False,
                quality_admitted=bool(ep_b.get("relation_count")),
                reason_codes=("episode_b_replay_ok", "live_plumbing_only"),
                **ExecutionOutcome._cell_fields(cell_b),
            )
        else:
            oc_b = ExecutionOutcome.not_run(
                cell=cell_b, reason=str(ep_b.get("error") or "episode_b_unknown")
            )
        ledger.record(cell_b.cell_id, oc_b)
        rows.append({"task_id": tid, "episode": "B", **ep_b, "manifest_cell_id": cell_b.cell_id})

        print(
            f"  {tid}: A status={ep_a.get('inference_status')} "
            f"gate={ep_a.get('gate', {}).get('decision')} events={ep_a.get('events_n')} "
            f"| B replay={ep_b.get('replay_ok')} rels={ep_b.get('relation_count')} "
            f"pids={ep_a.get('pid')}/{ep_b.get('pid')}",
            flush=True,
        )

    ledger.validate()
    diag = ledger.diagnostic_counts()

    # Collect all persisted terminal receipts from all task stores.
    persisted: list[dict[str, Any]] = []
    for t in tasks:
        tid = str(t.get("id"))
        sr = store_base / tid
        if sr.exists() and (sr / "genesis.json").exists():
            persisted.extend(ContinuityStore.open(sr).terminal_receipts())

    # Scientific completion count derived only from durable receipts (must be 0).
    sci_n = sum(1 for r in persisted if r.get("scientific_completion") is True)
    if sci_n != 0:
        raise SystemExit(
            f"RECEIPT_SCIENCE_LIE: {sci_n} persisted receipt(s) claim scientific_completion"
        )

    report = {
        "created_at": _now(),
        "run_id": run_id,
        "mode": "live_plumbing",
        "model": model,
        "profile": prof.profile_id,
        "dry_run": bool(dry),
        "n_tasks": len(tasks),
        "rows": rows,
        "persisted_terminal_receipts": persisted,
        "terminal_ledger": {
            "planned_n": diag["planned_n"],
            "terminal_n": diag["terminal_n"],
            "scientific_completion_n": sci_n,
            "diagnostic_counts": {**diag, "scientific_completion_n": sci_n},
        },
        **policy,
        "scientific_completion_n": sci_n,
    }
    event = {
        "event": "continuity.live_plumbing.completed",
        "run_id": run_id,
        "model": model,
        "profile": prof.profile_id,
        "dry_run": bool(dry),
        "planned_n": diag["planned_n"],
        "terminal_n": diag["terminal_n"],
        "inference_completed_n": diag["inference_completed_n"],
        "accepted_n": diag["accepted_n"],
        "failed_n": diag["failed_n"],
        "dry_run_n": diag["dry_run_n"],
        "scientific_completion_n": sci_n,
        **policy,
        "artifact": str(out),
    }
    report["event"] = event
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in (
        "mode", "scientific_completion_n", "headline_eligible", "scientific_status"
    )}, indent=2), flush=True)
    print("CK_EVENT " + json.dumps(event, separators=(",", ":")), flush=True)
    print(f"wrote {out}", flush=True)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Continuity experiment (two-episode, three-arm)")
    p.add_argument("--tasks", type=Path,
                   default=ROOT / "experiments" / "probes" / "continuity_tasks.json")
    p.add_argument("--model", default=None)
    p.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--dry", action="store_true", help="no inference; exercises plumbing only")
    p.add_argument("--bare-mode", choices=["fair", "plain"], default="fair",
                   help="fair: control gets CK's exact system prompt (isolates structure). "
                        "plain: control gets a neutral prompt (confounds instruction+structure).")
    p.add_argument("--episode", choices=["a", "b", "a-live", "b-live"], default=None,
                   help="internal worker mode")
    p.add_argument("--arm", default=None)
    p.add_argument("--payload", type=Path, default=None)
    p.add_argument("--out-json", type=Path, default=None)
    p.add_argument(
        "--live-plumbing",
        action="store_true",
        help="RUN 00.6C path: Episode A continuity_assertions → store → fresh Episode B",
    )
    p.add_argument(
        "--store-dir",
        type=Path,
        default=None,
        help="Base directory for live-plumbing ContinuityStore (default: temp under out)",
    )
    p.add_argument(
        "--invoke-episode-b-model",
        action="store_true",
        help="After verified replay, invoke model once on Episode B (smoke only)",
    )
    p.add_argument(
        "--inject-final-response",
        type=str,
        default=None,
        help="Offline/test: inject Episode A final-response text (no Ollama)",
    )
    a = p.parse_args()

    prof = load_profile(a.profile)
    model = a.model or prof.model

    # ---- worker modes -----------------------------------------------------
    if a.episode:
        payload = json.loads(a.payload.read_text())
        if a.episode == "a":
            res = episode_a(payload["task"], model, prof, a.dry)
        elif a.episode == "b":
            res = episode_b(payload["task"], a.arm, payload["artifacts"], model, prof,
                            a.dry, a.bare_mode)
        elif a.episode == "a-live":
            res = episode_a_live(
                payload["task"],
                model,
                prof,
                store_root=Path(payload["store_root"]),
                dry=a.dry,
                dry_candidate_text=payload.get("dry_candidate_text"),
            )
        else:  # b-live
            res = episode_b_live(
                payload["task"],
                model,
                prof,
                store_root=Path(payload["store_root"]),
                dry=a.dry,
                invoke_model=bool(payload.get("invoke_model")),
            )
        a.out_json.write_text(json.dumps(res))
        return 0

    # ---- live plumbing orchestrator (00.6C) --------------------------------
    if a.live_plumbing:
        tasks = json.loads(a.tasks.read_text())
        if a.limit:
            tasks = tasks[: a.limit]
        out = a.out or (
            ROOT / "experiments" / "runs" / f"live_plumbing_{int(time.time())}.json"
        )
        store_base = a.store_dir or (out.parent / f"{out.stem}_stores")
        print(
            f"live_plumbing: {len(tasks)} task(s), model={model}, dry={a.dry}",
            flush=True,
        )
        run_live_plumbing(
            tasks,
            model=model,
            prof=prof,
            dry=a.dry,
            out=out,
            store_base=store_base,
            invoke_episode_b_model=a.invoke_episode_b_model,
            inject_final_response=a.inject_final_response,
        )
        return 0

    # ---- orchestrator -----------------------------------------------------
    tasks = json.loads(a.tasks.read_text())
    if a.limit:
        tasks = tasks[: a.limit]
    run_id = f"continuity_{int(time.time())}"
    task_ids = [str(t.get("id") or f"task_{i}") for i, t in enumerate(tasks)]
    # Fail closed before any generation: empty planned manifest is not a run.
    try:
        planned_cells = build_manifest(
            run_id=run_id,
            task_ids=task_ids,
            condition_ids=list(ARMS),
            episodes=["B"],
        )
        ledger = TerminalLedger(planned_cells, run_id=run_id)
    except EmptyManifestError as e:
        print(f"EMPTY_MANIFEST: {e}", file=sys.stderr, flush=True)
        print(
            "CK_EVENT "
            + json.dumps(
                {
                    "event": "continuity.run.aborted",
                    "reason_code": e.reason_code,
                    "error": str(e),
                    "headline_eligible": False,
                    "scientific_completion_n": 0,
                    "scientific_status": "deferred_episode_a_lifecycle",
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        return 3

    # flush=True throughout: a long run redirected to a file otherwise shows
    # NOTHING until the block buffer fills, which is indistinguishable from a
    # stall. Progress on a 15-minute experiment has to be observable.
    print(f"continuity: {len(tasks)} tasks x {len(ARMS)} arms, model={model}, dry={a.dry}",
          flush=True)
    cell_by_key = {(c.task_id, c.condition_id): c for c in planned_cells}

    def _outcome_from_episode_b(cell: ManifestCell, ep_b: dict, dry: bool) -> ExecutionOutcome:
        if dry:
            return ExecutionOutcome.dry_run_only(cell=cell, reason="continuity_dry")
        eo_dict = ep_b.get("execution_outcome") or {}
        status_token = str(eo_dict.get("status") or ep_b.get("status") or "")
        # Dry worker
        if status_token == TerminalStatus.DRY_RUN_ONLY.value or ep_b.get("dry_run"):
            return ExecutionOutcome.dry_run_only(cell=cell, reason="continuity_dry")
        # Observed answer (inference-layer completed)
        if ep_b.get("status") == RunStatus.COMPLETED.value:
            return ExecutionOutcome(
                status=TerminalStatus.COMPLETED_INVALID,
                output=ep_b.get("raw") if isinstance(ep_b.get("raw"), str) else None,
                scientific_completion=False,
                dry_run=False,
                quality_admitted=True,
                reason_codes=("episode_b_observed", "scientific_completion_deferred"),
                error=ep_b.get("error"),
                inference=eo_dict.get("inference"),
                **ExecutionOutcome._cell_fields(cell),
            )
        # Operational / lifecycle failure from worker
        known = {s.value: s for s in TerminalStatus}
        if status_token in known:
            st = known[status_token]
            return ExecutionOutcome.from_lifecycle(
                cell=cell,
                status=st,
                output=None if st is not TerminalStatus.COMPLETED_INVALID else ep_b.get("raw"),
                error=ep_b.get("error") or eo_dict.get("error"),
                reason_codes=tuple(eo_dict.get("reason_codes") or (status_token,)),
            )
        if ep_b.get("error"):
            return ExecutionOutcome.from_lifecycle(
                cell=cell,
                status=TerminalStatus.TRANSPORT_ERROR,
                output=None,
                error=str(ep_b.get("error")),
                reason_codes=("episode_b_error",),
            )
        return ExecutionOutcome.not_run(cell=cell, reason="untyped_episode_b")

    rows = []
    for t in tasks:
        tid = str(t.get("id"))
        dry_flags = ["--dry"] if a.dry else []
        ep_a = _spawn(
            ["--episode", "a", "--model", model, "--profile", a.profile, *dry_flags],
            {"task": t},
        )
        if ep_a.get("error"):
            print(f"  {tid}: episode A failed — {ep_a['error'][:120]}", flush=True)
            # Failed Episode A must not erase planned cells.
            for arm in ARMS:
                cell = cell_by_key[(tid, arm)]
                if a.dry:
                    oc = ExecutionOutcome.dry_run_only(cell=cell, reason="episode_a_failed_dry")
                else:
                    oc = ExecutionOutcome.not_run(
                        cell=cell,
                        reason="blocked_by_episode_a",
                        blocked_by_manifest_cell_id=f"{run_id}:{tid}:episode_a:A:0",
                    )
                ledger.record(cell.cell_id, oc)
                rows.append({
                    "task_id": tid,
                    "category": t.get("category"),
                    "arm": arm,
                    "status": oc.status.value,
                    "error": ep_a.get("error"),
                    "raw": None,
                    "scores": {},
                    "dry_run": oc.dry_run,
                    "scientific_completion": False,
                    "manifest_cell_id": cell.cell_id,
                    "execution_outcome": oc.to_dict(),
                    "cold_start_receipt": {
                        "episode_a_process_id": ep_a.get("pid"),
                        "episode_a_end_time": ep_a.get("end_time"),
                        "episode_b_process_id": None,
                        "episode_b_start_time": None,
                        "distinct_pids": False,
                        "model": model,
                        "generation_seed": prof.seed,
                        "token_budget": prof.num_ctx,
                        "load_state": "not_run",
                    },
                })
            continue
        if not a.dry:
            evict(model)  # boundary: nothing resident survives
        for arm in ARMS:
            cell = cell_by_key[(tid, arm)]
            ep_b = _spawn(
                [
                    "--episode", "b", "--arm", arm, "--model", model,
                    "--profile", a.profile, "--bare-mode", a.bare_mode, *dry_flags,
                ],
                {"task": t, "artifacts": ep_a["artifacts"]},
            )
            boundary_ok = bool(ep_a.get("pid")) and ep_b.get("pid") not in (None, ep_a.get("pid"))
            oc = _outcome_from_episode_b(cell, ep_b, a.dry)
            ledger.record(cell.cell_id, oc)
            row = {
                "task_id": tid,
                "category": t.get("category"),
                "arm": arm,
                "manifest_cell_id": cell.cell_id,
                "cold_start_receipt": {
                    "episode_a_process_id": ep_a.get("pid"),
                    "episode_a_end_time": ep_a.get("end_time"),
                    "episode_b_process_id": ep_b.get("pid"),
                    "episode_b_start_time": ep_b.get("start_time"),
                    "distinct_pids": boundary_ok,
                    "model": model,
                    "generation_seed": prof.seed,
                    "token_budget": prof.num_ctx,
                    "load_state": "primed" if ep_b.get("primed") else "unprimed",
                },
                **{k: v for k, v in ep_b.items() if k not in ("pid", "start_time", "primed")},
            }
            # Authoritative terminal fields from the ledger outcome.
            if a.dry or oc.status is TerminalStatus.DRY_RUN_ONLY:
                row["status"] = TerminalStatus.DRY_RUN_ONLY.value
                row["raw"] = None
                row["scores"] = {}
            elif oc.status in (
                TerminalStatus.TIMEOUT,
                TerminalStatus.TRANSPORT_ERROR,
                TerminalStatus.INVALID_RESPONSE,
                TerminalStatus.NO_FINAL_RESPONSE,
                TerminalStatus.NOT_RUN,
                TerminalStatus.PARSE_FAILED,
                TerminalStatus.SCHEMA_FAILED,
                TerminalStatus.SEMANTIC_FAILED,
            ):
                row["status"] = oc.status.value
                row["raw"] = None
            else:
                # Observed answer: keep inference-layer "completed" for diagnostic means.
                row["status"] = RunStatus.COMPLETED.value
            row["dry_run"] = oc.dry_run
            row["scientific_completion"] = bool(oc.scientific_completion)
            row["execution_outcome"] = oc.to_dict()
            rows.append(row)
            s = (row.get("scores") or {}).get("continuity_score")
            print(
                f"  {tid:34} {arm:16} status={row.get('status')} "
                f"score={s} pid_ok={boundary_ok}",
                flush=True,
            )

    by_arm: dict[str, list[float]] = {}
    for r in rows:
        # Dry runs never enter scientific or diagnostic means.
        if r.get("dry_run") or r.get("status") == TerminalStatus.DRY_RUN_ONLY.value:
            continue
        if r.get("status") == RunStatus.COMPLETED.value:
            by_arm.setdefault(r["arm"], []).append(
                float((r.get("scores") or {}).get("continuity_score") or 0.0)
            )
    summary = {arm: (sum(v) / len(v) if v else None) for arm, v in by_arm.items()}
    # Pin corpus identity. Two seats work this repo in tandem, and the corpus
    # was edited mid-run once already: a result measured against a corpus that
    # no longer exists is not interpretable unless it says which corpus.
    corpus_bytes = a.tasks.read_bytes()
    corpus_sha = hashlib.sha256(corpus_bytes).hexdigest()[:16]
    try:
        corpus_commit = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", str(a.tasks)],
            cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
        dirty = bool(subprocess.run(
            ["git", "diff", "--quiet", "--", str(a.tasks)],
            cwd=ROOT).returncode)
    except Exception:
        corpus_commit, dirty = None, None

    # Same environment block the matrix artifacts carry. Continuity runs were
    # missing it, so they recorded WHICH CORPUS they measured but not which
    # runtime or model build -- half a provenance record is not a provenance
    # record, and cross-device continuity comparison would have hit the exact
    # ollama-version confound already found on the ladder.
    try:
        sys.path.insert(0, str(ROOT / "experiments"))
        from run_matrix import collect_environment  # noqa: E402
        env = collect_environment(model)
    except Exception as e:  # provenance must never fail a run
        env = {"probe_error": f"{type(e).__name__}: {e}"}

    ledger.validate()
    ledger_dict = ledger.to_dict()
    diag = ledger.diagnostic_counts()  # facts only — no headline policy
    policy = continuity_headline_policy()  # experiment-owned
    # Dry runs are plumbing only: suppress scientific M1/M2 headlines.
    # Diagnostic means may still exist for non-dry observed rows, but they are
    # never headline-eligible until Episode A lifecycle is repaired.
    if a.dry:
        summary = {arm: None for arm in ARMS}
        m1 = None
        m2 = None
    else:
        m1 = (
            None if summary.get("ck_packet") is None or summary.get("broken_packet") is None
            else summary["ck_packet"] - summary["broken_packet"]
        )
        m2 = (
            None if summary.get("ck_packet") is None or summary.get("bare_serialized") is None
            else summary["ck_packet"] - summary["bare_serialized"]
        )
    report = {
        "created_at": _now(),
        "run_id": run_id,
        "model": model,
        "profile": prof.profile_id,
        "environment": env,
        "bare_mode": a.bare_mode,
        "dry_run": bool(a.dry),
        "corpus": {
            "path": str(a.tasks.relative_to(ROOT)),
            "sha256_16": corpus_sha,
            "last_commit": corpus_commit,
            "uncommitted_edits": dirty,
            "n_tasks_in_file": len(json.loads(corpus_bytes)),
        },
        "n_tasks": len(tasks),
        "arms": list(ARMS),
        "mean_continuity_by_arm": summary,
        "M1_ck_beats_broken": m1,
        "M2_ck_beats_bare": m2,
        "all_boundaries_distinct": all(
            r["cold_start_receipt"]["distinct_pids"] for r in rows) if rows else False,
        "terminal_ledger": {
            "planned_n": diag["planned_n"],
            "terminal_n": diag["terminal_n"],
            "scientific_completion_n": diag["scientific_completion_n"],
            "status_counts": ledger_dict["status_counts"],
            "diagnostic_counts": diag,
        },
        **policy,
        "rows": rows,
    }
    out = a.out or (ROOT / "experiments" / "runs" / f"continuity_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    # Structured lifecycle event. Monitors should follow event type, not prose.
    # Inference completion is NOT scientific success — counts are explicit.
    event = {
        "event": "continuity.run.completed" if not a.dry else "continuity.run.dry",
        "commit": subprocess.run(["git", "log", "-1", "--format=%h"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip() or None,
        "corpus_sha256_16": corpus_sha,
        "corpus_commit": corpus_commit,
        "mode": a.bare_mode,
        "model": model,
        "profile": prof.profile_id,
        "dry_run": bool(a.dry),
        "m1_ck_vs_broken": report["M1_ck_beats_broken"],
        "m2_ck_vs_bare": report["M2_ck_beats_bare"],
        "arms": report["mean_continuity_by_arm"],
        # Explicit ledger facts (do not collapse into a single rows_valid).
        "planned_n": diag["planned_n"],
        "terminal_n": diag["terminal_n"],
        "inference_completed_n": diag["inference_completed_n"],
        "final_response_present_n": diag["final_response_present_n"],
        "candidate_valid_n": diag["candidate_valid_n"],
        "accepted_n": diag["accepted_n"],
        "scientific_completion_n": diag["scientific_completion_n"],
        "dry_run_n": diag["dry_run_n"],
        "failed_n": diag["failed_n"],
        # Experiment policy (continuity-owned; not from the ledger).
        **policy,
        # Legacy alias retained but never implies science: always == scientific_completion_n.
        "rows_valid": diag["scientific_completion_n"],
        "rows_expected": diag["planned_n"],
        "rows_terminal": diag["terminal_n"],
        "all_boundaries_distinct": report["all_boundaries_distinct"],
        "artifact": str(out),
    }
    report["event"] = event
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in
                      ("mean_continuity_by_arm", "M1_ck_beats_broken", "M2_ck_beats_bare",
                       "all_boundaries_distinct")}, indent=2), flush=True)
    print("CK_EVENT " + json.dumps(event, separators=(",", ":")), flush=True)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
