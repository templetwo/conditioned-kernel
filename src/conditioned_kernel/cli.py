"""Terminal surface for Conditioned Kernel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from conditioned_kernel import __version__
from conditioned_kernel.generate import OllamaClient, OllamaError
from conditioned_kernel.paths import default_logs_dir, default_state_dir, repo_root
from conditioned_kernel.pipeline import run_turn
from conditioned_kernel.state import SubstrateState

DEFAULT_MODEL = "qwen2.5:0.5b"


def _cmd_status(args: argparse.Namespace) -> int:
    state = SubstrateState.load(
        state_dir=Path(args.state_dir) if args.state_dir else None,
        logs_dir=Path(args.logs_dir) if args.logs_dir else None,
    )
    print(f"Conditioned Kernel v{__version__}")
    print(f"repo:   {repo_root()}")
    print(f"state:  {state.root}")
    print(f"logs:   {state.logs_dir}")
    print(f"goal:   {state.current.get('goal', '')}")
    print(f"profile:{state.current.get('active_profile', '')}")
    print(f"open threads: {len(state.open_threads())}")
    for t in state.open_threads():
        print(f"  - {t.get('id')}: {t.get('title')}")

    client = OllamaClient(base_url=args.base_url)
    try:
        models = client.list_models()
        print(f"ollama: ok ({len(models)} models) @ {args.base_url}")
        preferred = [m for m in models if "0.5b" in m or "1.5b" in m or "350m" in m]
        show = preferred or models[:8]
        for m in show:
            mark = " *" if m == args.model else ""
            print(f"  - {m}{mark}")
    except OllamaError as e:
        print(f"ollama: DOWN — {e}")
        return 1
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
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
                    "packet_id": result.packet.get("packet_id"),
                    "candidate_id": result.candidate.get("candidate_id"),
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
                f"\n-- receipt {result.receipt.get('receipt_id')} "
                f"pass={result.candidate.get('pass_index')} "
                f"violations={result.receipt.get('violations')}",
                file=sys.stderr,
            )
        return 0

    if result.decision == "error":
        print(f"[ck error] {result.error}", file=sys.stderr)
        return 2

    print(
        "[ck reject] substrate did not accept the candidate.\n"
        f"violations: {result.receipt.get('violations')}\n"
        f"raw answer (untrusted): {result.answer[:500]}",
        file=sys.stderr,
    )
    return 1


def _cmd_smoke(args: argparse.Namespace) -> int:
    """Minimal live or dry smoke test that leaves a receipt when possible."""
    print(f"smoke: model={args.model} mode={args.mode}")
    prompt = "In one or two sentences, state the current design intent using the packet goal."

    if args.dry:
        # Valid JSON that should pass closed-set checks against default state
        dry = json.dumps(
            {
                "answer": (
                    "Design intent: demonstrate conditioned-kernel substrate gain "
                    "over bare generation on a small local model, fully local."
                ),
                "evidence_used": [
                    "This system is fully local.",
                    "Demonstrate conditioned-kernel substrate gain over bare generation on a small local model.",
                ],
                "next_state": {
                    "thread_touch": ["thread_min_model"],
                    "proposed_note": "Smoke dry-run accepted.",
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
        )

    print(f"decision: {result.decision}")
    print(f"ok: {result.ok}")
    if result.answer:
        print(f"answer: {result.answer[:300]}")
    if result.receipt:
        print(f"receipt: {result.receipt.get('receipt_id')} violations={result.receipt.get('violations')}")
    if result.error:
        print(f"error: {result.error}")
    print(f"passes: {len(result.passes)}")
    return 0 if result.ok else 1


def _runtime_parent() -> argparse.ArgumentParser:
    """Shared runtime flags (use as parents= so they work after the subcommand)."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--state-dir", default=None, help="Override state directory")
    parent.add_argument("--logs-dir", default=None, help="Override logs directory")
    parent.add_argument("--base-url", default="http://127.0.0.1:11434")
    parent.add_argument("--model", default=DEFAULT_MODEL)
    parent.add_argument("--mode", choices=["chat_json", "generate_raw"], default="chat_json")
    parent.add_argument("--temperature", type=float, default=0.3)
    parent.add_argument("--seed", type=int, default=42)
    parent.add_argument("--num-ctx", type=int, default=4096)
    parent.add_argument("--max-repair", type=int, default=1)
    return parent


def build_parser() -> argparse.ArgumentParser:
    runtime = _runtime_parent()
    p = argparse.ArgumentParser(
        prog="ck",
        description="Conditioned Kernel — local substrate-conditioned generation",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("status", parents=[runtime], help="Show substrate + Ollama status")
    sp.set_defaults(func=_cmd_status)

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
    # Defaults for paths display
    if not getattr(args, "state_dir", None):
        args.state_dir = str(default_state_dir())
    if not getattr(args, "logs_dir", None):
        args.logs_dir = str(default_logs_dir())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
