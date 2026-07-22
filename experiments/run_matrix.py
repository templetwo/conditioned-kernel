#!/usr/bin/env python3
"""Experiment matrix under edge profile (post M1 audit).

- Fair controls: same format= / instructions when --fair-format (default)
- Headline comparison: budget_matched_bare
- Unified score_output for all conditions
- Frozen state snapshot (no mutation of live state/)
- Timestamped artifacts only; --write-last optional
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conditioned_kernel.compile import CANDIDATE_FORMAT, build_arrival_packet  # noqa: E402
from conditioned_kernel.edge import DEFAULT_PROFILE_ID, load_profile  # noqa: E402
from conditioned_kernel.generate import (  # noqa: E402
    DEFAULT_BASE_URL,
    OllamaClient,
    OllamaError,
)
from conditioned_kernel.pipeline import run_turn  # noqa: E402
from conditioned_kernel.score import (  # noqa: E402
    aggregate_condition,
    paired_gain,
    score_output,
    substrate_gain,
)
from conditioned_kernel.state import SubstrateState  # noqa: E402


def collect_environment(model: str) -> dict[str, Any]:
    """Record what the run actually executed on.

    Two runs labelled with the same profile are NOT comparable unless the
    device, runtime and model build match. A Mac and a Jetson produced
    materially different results from an identical model digest under
    identical profile/seed, with the Ollama version as an uncontrolled
    confound. Without this block that difference is invisible in the artifact.
    """
    env: dict[str, Any] = {
        "host_machine": platform.machine(),
        "host_system": platform.system(),
        "host_release": platform.release(),
        "python": platform.python_version(),
        "ollama_version": None,
        "model_digest": None,
        "model_bytes": None,
        "model_quantization": None,
    }
    base = DEFAULT_BASE_URL.rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as c:
            v = c.get(f"{base}/api/version")
            if v.status_code == 200:
                env["ollama_version"] = v.json().get("version")
            t = c.get(f"{base}/api/tags")
            if t.status_code == 200:
                for m in t.json().get("models") or []:
                    if m.get("name") == model:
                        env["model_digest"] = m.get("digest")
                        env["model_bytes"] = m.get("size")
                        env["model_quantization"] = (m.get("details") or {}).get(
                            "quantization_level"
                        )
                        break
    except Exception as e:  # environment metadata must never fail a run
        env["probe_error"] = f"{type(e).__name__}: {e}"
    return env


def prime_model(client: OllamaClient, model: str, prof: Any) -> dict[str, Any]:
    """Burn and discard one generation so all measured inferences are warm.

    See experiments/DETERMINISM.md (F-D1..F-D4). Returns a receipt describing
    what was done, recorded in the artifact so a reader knows the load state
    the numbers were produced under.
    """
    receipt: dict[str, Any] = {"primed": False, "error": None}
    try:
        fair_generate(
            client,
            model,
            "warmup",
            num_ctx=prof.num_ctx,
            system="Reply with the single word: ok",
            use_format=False,
        )
        receipt["primed"] = True
    except Exception as e:  # priming must never abort a run
        receipt["error"] = f"{type(e).__name__}: {e}"
    return receipt


def fair_generate(
    client: OllamaClient,
    model: str,
    prompt: str,
    *,
    num_ctx: int,
    system: str,
    use_format: bool,
) -> str:
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "seed": 42, "num_ctx": num_ctx},
    }
    if use_format:
        payload["format"] = CANDIDATE_FORMAT
    r = client.generate({"mode": "chat_json", "payload": payload})
    return OllamaClient.extract_text(r, "chat_json")


def budget_matched_prompt(state: SubstrateState, user_input: str) -> str:
    parts = [
        "STATE DUMP (unordered):",
        state.current.get("goal", ""),
        *(state.fact_list()),
        *[f"{t.get('id')}: {t.get('title', '')}" for t in state.open_threads()],
        "QUESTION:",
        user_input,
    ]
    return "\n".join(p for p in parts if p)


def load_probes(path: Path | None) -> list[dict]:
    if path and path.exists():
        return list(json.loads(path.read_text(encoding="utf-8")))
    return []


def freeze_state(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("current.json", "threads.json", "methods.json"):
        s = src / name
        if s.exists():
            shutil.copy2(s, dest / name)


def main() -> int:
    p = argparse.ArgumentParser(description="Conditioned Kernel matrix (audit-hardened)")
    p.add_argument("--model", default=None)
    p.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    p.add_argument("--probes", type=Path, default=ROOT / "experiments" / "probes" / "v0_probes.json")
    p.add_argument(
        "--conditions",
        default="bare,budget_matched_bare,ck_strict",
    )
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override profile timeout_s. Thinking models (Qwen3.5) exceed the "
             "edge profile's 90s and time out, which scores as 0 rather than as failure.",
    )
    p.add_argument(
        "--fair-format",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Give format= JSON schema to ALL conditions (default: true)",
    )
    p.add_argument(
        "--prime",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Discard one warmup generation so all scored inferences are warm "
             "(default: true; see experiments/DETERMINISM.md)",
    )
    p.add_argument(
        "--write-last",
        action="store_true",
        help="Also write experiments/runs/last_matrix.json (off by default)",
    )
    p.add_argument(
        "--mutate-live-state",
        action="store_true",
        help="Allow CK accepts to write live state/ (default: frozen snapshot)",
    )
    args = p.parse_args()

    prof = load_profile(args.profile)
    model = args.model or prof.model
    probes = load_probes(args.probes)
    if args.limit and args.limit > 0:
        probes = probes[: args.limit]

    timeout_s = args.timeout if args.timeout else prof.timeout_s
    client = OllamaClient(timeout=timeout_s)
    try:
        client.heartbeat()
    except OllamaError as e:
        print(f"Ollama required: {e}", file=sys.stderr)
        return 2

    live_state = ROOT / "state"
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.mutate_live_state:
        state_dir = live_state
        logs_dir = ROOT / "logs"
    else:
        tmp = tempfile.TemporaryDirectory(prefix="ck_matrix_")
        state_dir = Path(tmp.name) / "state"
        logs_dir = Path(tmp.name) / "logs"
        freeze_state(live_state, state_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)

    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]

    fair_system = (
        "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
        "answer: short reply that answers the user question (not a copy of the goal). "
        "evidence_used: copy strings from provided facts when present. "
        "next_state.thread_touch: [] or real thread ids. "
        "No cloud, no invented files."
    )

    rows: list[dict] = []
    by_cond: dict[str, list] = {c: [] for c in conditions}

    print(
        f"matrix profile={prof.profile_id} model={model} ctx={prof.num_ctx} "
        f"probes={len(probes)} fair_format={args.fair_format} "
        f"frozen_state={not args.mutate_live_state} prime={args.prime}"
    )

    # Pin load state before measuring. On CUDA + Q4_K_M the first inference
    # after a model load can return a different (but individually stable)
    # answer than every later one -- see experiments/DETERMINISM.md. Measuring
    # with the model in an unknown residency state made the same command
    # return +0.031 and -0.125. Priming discards one generation so every
    # scored inference runs in the same (warm) state.
    primed = prime_model(client, model, prof) if args.prime else None

    try:
        for probe in probes:
            prompt = probe.get("prompt") or ""
            pid = probe.get("id") or "probe"
            # Shared packet surface for scoring (same state for all conditions)
            packet = build_arrival_packet(state, prompt, profile=prof, enforce_budget=True)

            for cond in conditions:
                row: dict = {
                    "probe_id": pid,
                    "category": probe.get("category"),
                    "condition": cond,
                    "model": model,
                    "profile": prof.profile_id,
                    "num_ctx": prof.num_ctx,
                    "prompt": prompt,
                    "fair_format": args.fair_format,
                }
                try:
                    if cond == "bare":
                        text = fair_generate(
                            client,
                            model,
                            prompt,
                            num_ctx=prof.num_ctx,
                            system=fair_system,
                            use_format=args.fair_format,
                        )
                        row["raw"] = text
                        row["decision"] = "n/a_bare"
                        row["scores"] = score_output(text, packet=packet, probe=probe)
                    elif cond == "budget_matched_bare":
                        text = fair_generate(
                            client,
                            model,
                            budget_matched_prompt(state, prompt),
                            num_ctx=prof.num_ctx,
                            system=fair_system,
                            use_format=args.fair_format,
                        )
                        row["raw"] = text
                        row["decision"] = "n/a_budget_matched"
                        row["scores"] = score_output(text, packet=packet, probe=probe)
                    elif cond == "ck_strict":
                        tr = run_turn(
                            prompt,
                            model=model,
                            client=client,
                            profile=prof,
                            state_dir=state_dir,
                            logs_dir=logs_dir,
                        )
                        # re-freeze after each CK turn so packet state stays constant
                        if not args.mutate_live_state:
                            freeze_state(live_state, state_dir)
                            state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
                            packet = build_arrival_packet(
                                state, prompt, profile=prof, enforce_budget=True
                            )
                        row["raw"] = tr.answer
                        row["decision"] = tr.decision
                        row["ok"] = tr.ok
                        row["passes"] = tr.passes
                        # Prefer full candidate raw if present
                        raw = tr.candidate.get("raw_text") or tr.answer
                        if tr.candidate.get("parse_ok") and not tr.candidate.get("raw_text"):
                            raw = json.dumps(
                                {
                                    "answer": tr.candidate.get("answer"),
                                    "evidence_used": tr.candidate.get("evidence_used"),
                                    "next_state": tr.candidate.get("next_state"),
                                }
                            )
                        row["scores"] = score_output(
                            str(raw),
                            packet=tr.packet or packet,
                            probe=probe,
                            passes=tr.passes,
                            decision=tr.decision,
                        )
                    else:
                        row["error"] = f"unknown_condition:{cond}"
                        row["scores"] = {}
                except Exception as e:  # noqa: BLE001
                    row["error"] = str(e)
                    row["scores"] = {}

                # Explicit outcome on every row. A timeout is not a zero: output
                # is null when nothing was observed, "" only when the model
                # genuinely answered with nothing.
                if row.get("error") or row.get("decision") == "error":
                    err = str(row.get("error") or "decision=error")
                    status = (
                        "timeout"
                        if ("timeout" in err.lower() or "timed out" in err.lower())
                        else "transport_error"
                    )
                    row["inference"] = {
                        "status": status,
                        "output": None,
                        "error": err,
                        "timeout_seconds": timeout_s,
                        "valid_measurement": False,
                    }
                else:
                    row["inference"] = {
                        "status": "completed",
                        "output": row.get("raw"),
                        "error": None,
                        "timeout_seconds": timeout_s,
                        "valid_measurement": True,
                    }

                rows.append(row)
                by_cond.setdefault(cond, []).append(row)
                sc = row.get("scores") or {}
                print(
                    f"  [{cond}] {pid} decision={row.get('decision')} "
                    f"struct={sc.get('structural_score', 0):.2f} "
                    f"sem={sc.get('semantic_score', 0):.2f} "
                    f"accept={sc.get('accept', False)} "
                    f"echo={sc.get('goal_echo', False)} "
                    f"key={sc.get('key_ok', False)}"
                )
    finally:
        if tmp is not None:
            tmp.cleanup()

    aggregates = {c: aggregate_condition(by_cond.get(c, [])) for c in conditions}
    gains: dict = {}
    # HEADLINE: budget_matched_bare
    if "ck_strict" in aggregates and "budget_matched_bare" in aggregates:
        gains["headline_vs_budget_matched_bare"] = substrate_gain(
            aggregates["ck_strict"], aggregates["budget_matched_bare"]
        )
    # PRIMARY: paired and fail-closed. A probe counts only if both sides were
    # observed; partial coverage yields no headline at all.
    if "ck_strict" in by_cond and "budget_matched_bare" in by_cond:
        gains["headline_paired_vs_budget_matched_bare"] = paired_gain(
            by_cond["ck_strict"], by_cond["budget_matched_bare"]
        )
    if "ck_strict" in aggregates and "bare" in aggregates:
        gains["context_vs_bare_information_access"] = {
            **substrate_gain(aggregates["ck_strict"], aggregates["bare"]),
            "note": "Measures information access + condition effects; not the headline substrate claim.",
        }

    report = {
        "created_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "profile": prof.profile_id,
        "model": model,
        "num_ctx": prof.num_ctx,
        "probe_count": len(probes),
        "conditions": conditions,
        "fair_format": args.fair_format,
        "frozen_state": not args.mutate_live_state,
        "headline_control": "budget_matched_bare",
        "environment": collect_environment(model),
        "timeout_s": timeout_s,
        "load_state": {"prime": args.prime, "receipt": primed},
        "audit_note": "Post M1_AUDIT.md corrections. Do not cite pre-audit +0.60.",
        "aggregates": aggregates,
        "substrate_gain": gains,
        "rows": rows,
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or (ROOT / "experiments" / "runs" / f"matrix_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.write_last:
        last = ROOT / "experiments" / "runs" / "last_matrix.json"
        last.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n=== aggregates ===")
    print(json.dumps(aggregates, indent=2))
    print("=== substrate_gain (headline = vs budget_matched_bare) ===")
    print(json.dumps(gains, indent=2))
    print(f"wrote {out}")
    if not args.write_last:
        print("(last_matrix.json not updated; pass --write-last to overwrite pointer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
