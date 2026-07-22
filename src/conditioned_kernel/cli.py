"""Terminal surface for Conditioned Kernel (edge-default profiles)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from conditioned_kernel import __version__
from conditioned_kernel.edge import (
    DEFAULT_PROFILE_ID,
    edge_status_report,
    list_profiles,
    load_profile,
    packet_byte_size,
)
from conditioned_kernel.generate import OllamaClient, OllamaError
from conditioned_kernel.paths import default_logs_dir, default_state_dir, repo_root
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import SubstrateState


def _resolve_profile(args: argparse.Namespace):
    return load_profile(getattr(args, "profile", None) or DEFAULT_PROFILE_ID)


def _apply_profile_defaults(args: argparse.Namespace) -> Any:
    """Fill unset runtime knobs from the edge profile."""
    prof = _resolve_profile(args)
    if getattr(args, "model", None) in (None, ""):
        args.model = prof.model
    if getattr(args, "mode", None) in (None, ""):
        args.mode = prof.mode
    if getattr(args, "temperature", None) is None:
        args.temperature = prof.temperature
    if getattr(args, "seed", None) is None:
        args.seed = prof.seed
    if getattr(args, "num_ctx", None) is None:
        args.num_ctx = prof.num_ctx
    if getattr(args, "max_repair", None) is None:
        args.max_repair = prof.max_repair
    args._profile = prof
    return prof


def _cmd_status(args: argparse.Namespace) -> int:
    prof = _apply_profile_defaults(args)
    state = SubstrateState.load(
        state_dir=Path(args.state_dir) if args.state_dir else None,
        logs_dir=Path(args.logs_dir) if args.logs_dir else None,
    )
    print(f"Conditioned Kernel v{__version__}")
    print(f"repo:    {repo_root()}")
    print(f"state:   {state.root}")
    print(f"logs:    {state.logs_dir}")
    print(f"goal:    {state.current.get('goal', '')}")
    print(f"profile: {prof.profile_id}  (edge target: {prof.target_device})")
    report = edge_status_report(prof)
    print(
        f"edge:    ctx={report['num_ctx']}  packet≤{report['max_packet_bytes']}B  "
        f"keep_alive={report['keep_alive']}  one_model={report['one_model_only']}"
    )
    print(
        f"budget:  est working set ~{report['estimated_working_set_mb']}MB  "
        f"headroom ~{report['estimated_headroom_mb']}MB on {report['ram_gb_budget']}GB class"
    )
    print(f"host:    {report['host_arch']}")
    print(f"open threads: {len(state.open_threads())}")
    for t in state.open_threads():
        print(f"  - {t.get('id')}: {t.get('title')}")

    client = OllamaClient(base_url=args.base_url, timeout=min(10.0, prof.timeout_s))
    try:
        models = client.list_models()
        print(f"ollama:  ok ({len(models)} models) @ {args.base_url}")
        preferred = [
            m
            for m in models
            if any(x in m for x in ("0.5b", "1.5b", "350m", "1b", "360m"))
        ]
        show = preferred or models[:8]
        for m in show:
            mark = " *" if m == args.model or m.startswith(args.model) else ""
            print(f"  - {m}{mark}")
        if prof.one_model_only and len(models) > 1:
            print(
                "  note: edge profile is one_model_only — load a single quant at a time on Jetson"
            )
    except OllamaError as e:
        print(f"ollama:  DOWN — {e}")
        return 1
    return 0


def _cmd_edge(args: argparse.Namespace) -> int:
    """Show edge profiles and self-check budgets."""
    if args.list:
        for pid in list_profiles():
            mark = " (default)" if pid == DEFAULT_PROFILE_ID else ""
            p = load_profile(pid)
            print(f"{pid}{mark}: ctx={p.num_ctx} model={p.model} packet≤{p.max_packet_bytes}B")
        return 0

    prof = _apply_profile_defaults(args)
    report = edge_status_report(prof)
    print(json.dumps(report, indent=2))

    # Compile a sample packet and report size under budget
    state = SubstrateState.load(
        state_dir=Path(args.state_dir) if args.state_dir else None,
        logs_dir=Path(args.logs_dir) if args.logs_dir else None,
    )
    from conditioned_kernel.compile import build_arrival_packet

    packet = build_arrival_packet(
        state,
        "edge self-check: summarize design intent",
        profile=prof,
        enforce_budget=True,
    )
    size = packet_byte_size({k: v for k, v in packet.items() if not str(k).startswith("_")})
    ok = size <= prof.max_packet_bytes
    print(
        f"sample_packet_bytes: {size} / {prof.max_packet_bytes}  "
        f"{'OK' if ok else 'OVER BUDGET'}"
    )
    print(f"facts: {len(packet.get('facts') or [])}  threads: {len(packet.get('open_threads') or [])}")
    if not ok:
        return 1
    # Soft arch warning
    if prof.arch == "aarch64" and "aarch64" not in report["host_arch"] and "arm64" not in report["host_arch"]:
        print(
            "note: developing on non-ARM host is fine; product path is aarch64 Jetson. "
            "Keep this profile as default."
        )
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    prof = _apply_profile_defaults(args)
    prompt = args.prompt
    if not prompt:
        print("error: provide a prompt", file=sys.stderr)
        return 2

    result = run_turn(
        prompt,
        model=args.model,
        mode=args.mode,
        state_dir=Path(args.state_dir) if args.state_dir else None,
        logs_dir=Path(args.logs_dir) if args.logs_dir else None,
        base_url=args.base_url,
        max_repair=args.max_repair,
        temperature=args.temperature,
        seed=args.seed,
        num_ctx=args.num_ctx,
        profile=prof,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "decision": result.decision,
                    "answer": result.answer,
                    "receipt": result.receipt,
                    "passes": result.passes,
                    "error": result.error,
                    "profile_id": result.profile_id,
                    "packet_id": result.packet.get("packet_id"),
                    "candidate_id": result.candidate.get("candidate_id"),
                    "packet_bytes": (result.packet.get("_edge") or {}).get("packet_bytes"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if result.ok else 1

    if result.decision == "accept":
        print(result.answer)
        if args.verbose:
            print(
                f"\n-- profile={result.profile_id} "
                f"receipt={result.receipt.get('receipt_id')} "
                f"pass={result.candidate.get('pass_index')} "
                f"packet_bytes={(result.packet.get('_edge') or {}).get('packet_bytes')} "
                f"violations={result.receipt.get('violations')}",
                file=sys.stderr,
            )
        return 0

    if result.decision == "error":
        print(f"[ck error] {result.error}", file=sys.stderr)
        return 2

    print(
        "[ck reject] substrate did not accept the candidate.\n"
        f"profile: {result.profile_id}\n"
        f"violations: {result.receipt.get('violations')}\n"
        f"raw answer (untrusted): {result.answer[:500]}",
        file=sys.stderr,
    )
    return 1


def _cmd_smoke(args: argparse.Namespace) -> int:
    prof = _apply_profile_defaults(args)
    print(f"smoke: profile={prof.profile_id} model={args.model} mode={args.mode} ctx={args.num_ctx}")
    prompt = "In one or two sentences, state the current design intent using the packet goal."

    if args.dry:
        dry = json.dumps(
            {
                "answer": (
                    "Design intent is edge-first substrate conditioning: keep the model "
                    "small and local, put continuity in the substrate, and measure gain "
                    "under Jetson Orin Nano budgets without cloud or sensors."
                ),
                "evidence_used": [
                    "This system is fully local.",
                    "Edge target: jetson_orin_nano_8gb (one model at a time).",
                ],
                "next_state": {
                    "thread_touch": ["thread_min_model"],
                },
            }
        )
        result = run_turn(
            prompt,
            model=args.model,
            mode=args.mode,
            state_dir=Path(args.state_dir) if args.state_dir else None,
            logs_dir=Path(args.logs_dir) if args.logs_dir else None,
            dry_candidate_text=dry,
            max_repair=0,
            profile=prof,
        )
    else:
        result = run_turn(
            prompt,
            model=args.model,
            mode=args.mode,
            state_dir=Path(args.state_dir) if args.state_dir else None,
            logs_dir=Path(args.logs_dir) if args.logs_dir else None,
            base_url=args.base_url,
            max_repair=args.max_repair,
            temperature=args.temperature,
            seed=args.seed,
            num_ctx=args.num_ctx,
            profile=prof,
        )

    print(f"decision: {result.decision}")
    print(f"ok: {result.ok}")
    print(f"profile: {result.profile_id}")
    if result.answer:
        print(f"answer: {result.answer[:300]}")
    if result.receipt:
        print(
            f"receipt: {result.receipt.get('receipt_id')} "
            f"violations={result.receipt.get('violations')}"
        )
    if result.packet:
        print(f"packet_bytes: {(result.packet.get('_edge') or {}).get('packet_bytes')}")
    if result.error:
        print(f"error: {result.error}")
    print(f"passes: {len(result.passes)}")
    return 0 if result.ok else 1


def _runtime_parent() -> argparse.ArgumentParser:
    """Shared runtime flags — defaults come from edge profile when left unset."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--state-dir", default=None, help="Override state directory")
    parent.add_argument("--logs-dir", default=None, help="Override logs directory")
    parent.add_argument("--base-url", default="http://127.0.0.1:11434")
    parent.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_ID,
        help=f"Edge profile (default: {DEFAULT_PROFILE_ID})",
    )
    parent.add_argument("--model", default=None, help="Override profile model")
    parent.add_argument(
        "--mode",
        choices=["chat_json", "generate_raw"],
        default=None,
        help="Override profile mode",
    )
    parent.add_argument("--temperature", type=float, default=None)
    parent.add_argument("--seed", type=int, default=None)
    parent.add_argument("--num-ctx", type=int, default=None)
    parent.add_argument("--max-repair", type=int, default=None)
    return parent


def build_parser() -> argparse.ArgumentParser:
    runtime = _runtime_parent()
    p = argparse.ArgumentParser(
        prog="ck",
        description=(
            "Conditioned Kernel — edge-first substrate-conditioned generation "
            f"(default profile: {DEFAULT_PROFILE_ID})"
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("status", parents=[runtime], help="Show substrate + edge + Ollama status")
    sp.set_defaults(func=_cmd_status)

    ep = sub.add_parser("edge", parents=[runtime], help="Edge profile report / self-check")
    ep.add_argument("--list", action="store_true", help="List available profiles")
    ep.set_defaults(func=_cmd_edge)

    ap = sub.add_parser("ask", parents=[runtime], help="Run one conditioned turn")
    ap.add_argument("prompt", nargs="?", default=None)
    ap.add_argument("--json", action="store_true", help="Emit machine-readable result")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.set_defaults(func=_cmd_ask)

    sm = sub.add_parser("smoke", parents=[runtime], help="Smoke test (live Ollama or --dry)")
    sm.add_argument("--dry", action="store_true", help="Skip Ollama; inject valid candidate")
    sm.set_defaults(func=_cmd_smoke)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "state_dir", None):
        args.state_dir = str(default_state_dir())
    if not getattr(args, "logs_dir", None):
        args.logs_dir = str(default_logs_dir())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
