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
from conditioned_kernel.generate import DEFAULT_BASE_URL, OllamaClient  # noqa: E402
from conditioned_kernel.state import SubstrateState  # noqa: E402

ARMS = ("bare_serialized", "ck_packet", "broken_packet")

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

        status, text, err = "completed", "", None
        if not dry:
            res = client.run(mi)
            status, text, err = res.status.value, (res.output or ""), res.error

        scored = score_episode_b(text, task=task, packet=ck_packet, artifacts=artifacts)
        return {
            "arm": arm,
            "pid": start_pid,
            "start_time": start_time,
            "status": status,
            "error": err,
            "primed": primed,
            "raw": text,
            "scores": scored,
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
    p.add_argument("--episode", choices=["a", "b"], default=None, help="internal worker mode")
    p.add_argument("--arm", default=None)
    p.add_argument("--payload", type=Path, default=None)
    p.add_argument("--out-json", type=Path, default=None)
    a = p.parse_args()

    prof = load_profile(a.profile)
    model = a.model or prof.model

    # ---- worker modes -----------------------------------------------------
    if a.episode:
        payload = json.loads(a.payload.read_text())
        if a.episode == "a":
            res = episode_a(payload["task"], model, prof, a.dry)
        else:
            res = episode_b(payload["task"], a.arm, payload["artifacts"], model, prof,
                            a.dry, a.bare_mode)
        a.out_json.write_text(json.dumps(res))
        return 0

    # ---- orchestrator -----------------------------------------------------
    tasks = json.loads(a.tasks.read_text())
    if a.limit:
        tasks = tasks[: a.limit]
    # flush=True throughout: a long run redirected to a file otherwise shows
    # NOTHING until the block buffer fills, which is indistinguishable from a
    # stall. Progress on a 15-minute experiment has to be observable.
    print(f"continuity: {len(tasks)} tasks x {len(ARMS)} arms, model={model}, dry={a.dry}",
          flush=True)

    rows = []
    for t in tasks:
        tid = t.get("id")
        dry = ["--dry"] if a.dry else []
        ep_a = _spawn(["--episode", "a", "--model", model, "--profile", a.profile, *dry], {"task": t})
        if ep_a.get("error"):
            print(f"  {tid}: episode A failed — {ep_a['error'][:120]}", flush=True)
            continue
        if not a.dry:
            evict(model)  # boundary: nothing resident survives
        for arm in ARMS:
            ep_b = _spawn(["--episode", "b", "--arm", arm, "--model", model,
                           "--profile", a.profile, "--bare-mode", a.bare_mode, *dry],
                          {"task": t, "artifacts": ep_a["artifacts"]})
            boundary_ok = bool(ep_a.get("pid")) and ep_b.get("pid") not in (None, ep_a.get("pid"))
            rows.append({
                "task_id": tid, "category": t.get("category"), "arm": arm,
                "cold_start_receipt": {
                    "episode_a_process_id": ep_a.get("pid"),
                    "episode_a_end_time": ep_a.get("end_time"),
                    "episode_b_process_id": ep_b.get("pid"),
                    "episode_b_start_time": ep_b.get("start_time"),
                    "distinct_pids": boundary_ok,
                    "model": model, "generation_seed": prof.seed,
                    "token_budget": prof.num_ctx, "load_state": "primed" if ep_b.get("primed") else "unprimed",
                },
                **{k: v for k, v in ep_b.items() if k not in ("pid", "start_time", "primed")},
            })
            s = (ep_b.get("scores") or {}).get("continuity_score")
            print(f"  {tid:34} {arm:16} score={s} pid_ok={boundary_ok}", flush=True)

    by_arm: dict[str, list[float]] = {}
    for r in rows:
        if r.get("status") == "completed":
            by_arm.setdefault(r["arm"], []).append(
                float((r.get("scores") or {}).get("continuity_score") or 0.0))
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

    report = {
        "created_at": _now(), "model": model, "profile": prof.profile_id,
        "bare_mode": a.bare_mode,
        "corpus": {
            "path": str(a.tasks.relative_to(ROOT)),
            "sha256_16": corpus_sha,
            "last_commit": corpus_commit,
            "uncommitted_edits": dirty,
            "n_tasks_in_file": len(json.loads(corpus_bytes)),
        },
        "n_tasks": len(tasks), "arms": list(ARMS),
        "mean_continuity_by_arm": summary,
        "M1_ck_beats_broken": (
            None if summary.get("ck_packet") is None or summary.get("broken_packet") is None
            else summary["ck_packet"] - summary["broken_packet"]),
        "M2_ck_beats_bare": (
            None if summary.get("ck_packet") is None or summary.get("bare_serialized") is None
            else summary["ck_packet"] - summary["bare_serialized"]),
        "all_boundaries_distinct": all(
            r["cold_start_receipt"]["distinct_pids"] for r in rows) if rows else False,
        "rows": rows,
    }
    out = a.out or (ROOT / "experiments" / "runs" / f"continuity_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    # Structured lifecycle event. Monitors should follow event type, not prose:
    # grepping human sentences is fragile and breaks silently when wording
    # changes. This line is the contract.
    valid = sum(1 for r in rows if r.get("status") == "completed")
    event = {
        "event": "continuity.run.completed",
        "commit": subprocess.run(["git", "log", "-1", "--format=%h"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip() or None,
        "corpus_sha256_16": corpus_sha,
        "corpus_commit": corpus_commit,
        "mode": a.bare_mode,
        "model": model,
        "profile": prof.profile_id,
        "m1_ck_vs_broken": report["M1_ck_beats_broken"],
        "m2_ck_vs_bare": report["M2_ck_beats_bare"],
        "arms": report["mean_continuity_by_arm"],
        "rows_valid": valid,
        "rows_expected": len(rows),
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
