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

# `ck dashboard` — Interior View observability dashboard (RUN 00.9A handoff).
# Deferred import (see `_cmd_dashboard`) so `conditioned_kernel.observatory`,
# which pulls in `http.server`, is only loaded when the subcommand actually
# runs — every other `ck` subcommand's import graph stays exactly as it was.


def _resolve_profile(args: argparse.Namespace):
    prof = load_profile(getattr(args, "profile", None) or DEFAULT_PROFILE_ID)
    # Step 0 DoD B: ordinary vs deliberate without changing model identity
    tp = getattr(args, "think_profile", None)
    if tp:
        prof = prof.with_think_profile(str(tp))
    return prof


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
    rt = prof.runtime_tuple()
    if rt.get("quant") or rt.get("digest_prefix") or prof.profile_id.startswith("macbook"):
        print(
            f"op:      model={rt.get('model')}  quant={rt.get('quant') or '—'}  "
            f"digest~{rt.get('digest_prefix') or '—'}  think={rt.get('think_profile')}  "
            f"ctx={rt.get('num_ctx')}  gate={rt.get('gate_version')}  "
            f"compile={rt.get('compile_policy')}"
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


def _cmd_chat(args: argparse.Namespace) -> int:
    """Sustained multi-turn session: compile → generate → accept loop on stdin.

    `--mode flow` forks to Studio Flow mode (`_cmd_chat_flow`) before any of
    the acceptance-court machinery below runs — Flow never calls `run_turn`.
    """
    if getattr(args, "mode", None) == "flow":
        return _cmd_chat_flow(args)

    prof = _apply_profile_defaults(args)
    state_dir = Path(args.state_dir) if args.state_dir else None
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)

    if getattr(args, "new_session", False):
        sid = state.begin_new_session()
        print(f"[ck] new session: {sid}", file=sys.stderr)
    else:
        sid = str(state.current.get("session_id") or "sess_unknown")
        n_recent = len(state.recent_turns())
        print(
            f"[ck] chat  session={sid}  profile={prof.profile_id}  "
            f"model={args.model}  recent_turns={n_recent}",
            file=sys.stderr,
        )
        print(
            "[ck] type quit/exit to stop; state persists for resume",
            file=sys.stderr,
        )

    turns_ok = 0
    while True:
        try:
            line = input("you> ")
        except EOFError:
            print(file=sys.stderr)
            break
        except KeyboardInterrupt:
            print("\n[ck] interrupted", file=sys.stderr)
            break

        text = (line or "").strip()
        if not text:
            continue
        if text.lower() in ("quit", "exit", ":q", "/quit", "/exit"):
            break

        result = run_turn(
            text,
            model=args.model,
            mode=args.mode,
            state_dir=state_dir,
            logs_dir=logs_dir,
            base_url=args.base_url,
            max_repair=args.max_repair,
            temperature=args.temperature,
            seed=args.seed,
            num_ctx=args.num_ctx,
            profile=prof,
        )

        if result.decision == "accept":
            print(f"ck> {result.answer}")
            turns_ok += 1
            if args.verbose:
                pb = (result.packet.get("_edge") or {}).get("packet_bytes")
                rt = len(result.packet.get("recent_turns") or [])
                print(
                    f"    -- ok packet_bytes={pb} prior_turns_in_packet={rt}",
                    file=sys.stderr,
                )
            continue

        # Stay in the loop on reject/error — do not crash the session.
        if result.decision == "error":
            print(f"[ck error] {result.error}", file=sys.stderr)
            print("ck> (turn failed; try again or quit)", file=sys.stderr)
            continue

        print(
            "[ck reject] substrate did not accept that candidate.\n"
            f"  violations: {result.receipt.get('violations')}\n"
            f"  raw (untrusted): {(result.answer or '')[:240]}",
            file=sys.stderr,
        )
        print("ck> (rejected; try rephrasing or quit)", file=sys.stderr)

    print(f"[ck] session end  accepted_turns={turns_ok}", file=sys.stderr)
    return 0


def _cmd_chat_flow(args: argparse.Namespace) -> int:
    """Studio Flow mode: field before → model speaks through field → output
    reaches Anthony → substrate observes what traveled → field integrates
    and shifts → next turn.

    No validation court, no accept/reject branch in the speech path — every
    nonempty generation is displayed plainly; observations live only in the
    dashboard trace, never as terminal noise. `--new-session` here clears
    only `state/flow_field.json` — it never touches `current.json` or
    `threads.json` (those stay companion/measurement state).

    Deferred import: `conditioned_kernel.flow` is only loaded when this
    subcommand actually runs, same convention as `_cmd_dashboard`'s
    deferred `observatory` import above.
    """
    from conditioned_kernel.flow import clear_flow_field, flow_field_path, run_flow_turn

    prof = _apply_profile_defaults(args)
    state_dir = Path(args.state_dir) if args.state_dir else None
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)

    if getattr(args, "new_session", False):
        clear_flow_field(state.root)
        print(f"[ck] flow: cleared {flow_field_path(state.root)}", file=sys.stderr)

    sid = str(state.current.get("session_id") or "sess_unknown")
    print(
        f"[ck] chat --mode flow  session={sid}  profile={prof.profile_id}  model={args.model}",
        file=sys.stderr,
    )
    print("[ck] type quit/exit to stop; field persists for resume", file=sys.stderr)

    while True:
        try:
            line = input("you> ")
        except EOFError:
            print(file=sys.stderr)
            break
        except KeyboardInterrupt:
            print("\n[ck] interrupted", file=sys.stderr)
            break

        text = (line or "").strip()
        if not text:
            continue
        if text.lower() in ("quit", "exit", ":q", "/quit", "/exit"):
            break

        result = run_flow_turn(
            text,
            model=args.model,
            state_dir=state_dir,
            logs_dir=logs_dir,
            base_url=args.base_url,
            temperature=args.temperature,
            seed=args.seed,
            num_ctx=args.num_ctx,
            profile=prof,
        )
        print(f"ck> {result.displayed_text}")
        if args.verbose:
            print(
                f"    -- turn={result.trace.turn_id} status={result.trace.reply_status} "
                f"observations={len(result.trace.observations)}",
                file=sys.stderr,
            )

    print("[ck] flow session end", file=sys.stderr)
    return 0


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


def _cmd_act1(args: argparse.Namespace) -> int:
    """Live ACT-1 Authority Crossover TUI (or headless screen). Real Ollama only."""
    from pathlib import Path

    from conditioned_kernel.act1.runner import Act1Config, run_act1
    from conditioned_kernel.act1.state import Act1LiveState
    from conditioned_kernel.act1.tui import run_tui

    cells = tuple(
        c.strip().upper()
        for c in (getattr(args, "cells", None) or "A,B,C,D").split(",")
        if c.strip()
    )
    out = getattr(args, "out_dir", None)
    cfg = Act1Config(
        max_cases=getattr(args, "max_cases", None),
        cells=cells,
        out_dir=Path(out) if out else None,
    )
    if getattr(args, "no_tui", False):
        state = Act1LiveState()
        summary = run_act1(state, cfg)
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("primary_pass") else 1
    return run_tui(cfg)


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Serve the Interior View observability dashboard.

    Reuses `ck chat`'s profile/state/logs resolution pattern exactly:
    `_apply_profile_defaults` fills unset runtime knobs from the edge
    profile, `--new-session` clears recent dialogue memory the same way
    `ck chat --new-session` does. Everything else is delegated to
    `observatory.server.serve`, which owns the actual socket.

    `--session-mode flow` changes what `--new-session` clears, mirroring
    `ck chat --mode flow --new-session` exactly: only
    `state/flow_field.json` is cleared, and `state.begin_new_session()` (a
    `current.json` mutation) is never called for a flow-mode dashboard —
    the hard boundary between Flow's own field state and companion/
    measurement state applies here too, not just at the CLI chat path.
    """
    from conditioned_kernel.observatory.server import serve

    prof = _apply_profile_defaults(args)
    state_dir = Path(args.state_dir) if args.state_dir else None
    logs_dir = Path(args.logs_dir) if args.logs_dir else None
    session_mode = getattr(args, "session_mode", None) or "pipeline"

    if getattr(args, "new_session", False):
        state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
        if session_mode == "flow":
            from conditioned_kernel.flow import clear_flow_field, flow_field_path

            clear_flow_field(state.root)
            print(f"[ck] dashboard flow: cleared {flow_field_path(state.root)}", file=sys.stderr)
        else:
            sid = state.begin_new_session()
            print(f"[ck] new session: {sid}", file=sys.stderr)

    return serve(
        host=args.host,
        port=args.port,
        state_dir=state_dir,
        logs_dir=logs_dir,
        profile=prof,
        model=args.model,
        base_url=args.base_url,
        observer_enabled=bool(args.observer),
        open_browser=not bool(getattr(args, "no_browser", False)),
        session_mode=session_mode,
    )


def _runtime_parent(*, include_mode: bool = True) -> argparse.ArgumentParser:
    """Shared runtime flags — defaults come from edge profile when left unset.

    `include_mode=False` omits `--mode` so a subparser (currently only
    `chat`) can define its own `--mode` with an expanded choice set without
    tripping argparse's "conflicting option string" error (you cannot
    re-add an option string a parent already registered). Every other
    subcommand keeps the original chat_json/generate_raw-only `--mode`,
    behavior byte-identical to before.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--state-dir", default=None, help="Override state directory")
    parent.add_argument("--logs-dir", default=None, help="Override logs directory")
    parent.add_argument("--base-url", default="http://127.0.0.1:11434")
    parent.add_argument(
        "--profile",
        default=DEFAULT_PROFILE_ID,
        help=f"Edge profile (default: {DEFAULT_PROFILE_ID})",
    )
    parent.add_argument(
        "--think-profile",
        choices=["ordinary", "deliberate", "off", "on"],
        default=None,
        help=(
            "Step 0: ordinary/think-off vs deliberate/think-on without swapping the model. "
            "Same weights; only the thinking channel changes."
        ),
    )
    parent.add_argument("--model", default=None, help="Override profile model")
    if include_mode:
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
    runtime_no_mode = _runtime_parent(include_mode=False)
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

    ch = sub.add_parser(
        "chat",
        parents=[runtime_no_mode],
        help="Multi-turn session (stdin loop; state persists for resume)",
    )
    ch.add_argument(
        "--mode",
        choices=["chat_json", "generate_raw", "flow"],
        default=None,
        help=(
            "chat_json/generate_raw select the Ollama transport (companion "
            "acceptance-court path, default from edge profile). flow selects "
            "Studio Flow mode: a living field, no candidate schema, no "
            "accept/reject — see `ck chat --mode flow --help`-equivalent in docs."
        ),
    )
    ch.add_argument(
        "--new-session",
        action="store_true",
        help=(
            "Companion mode: clear recent dialogue memory and bump session_id "
            "(goal/threads kept). Flow mode (--mode flow): clear state/flow_field.json "
            "only — current.json/threads.json are never touched by flow mode."
        ),
    )
    ch.add_argument("-v", "--verbose", action="store_true")
    ch.set_defaults(func=_cmd_chat)

    sm = sub.add_parser("smoke", parents=[runtime], help="Smoke test (live Ollama or --dry)")
    sm.add_argument("--dry", action="store_true", help="Skip Ollama; inject valid candidate")
    sm.set_defaults(func=_cmd_smoke)

    dp = sub.add_parser(
        "dashboard",
        parents=[runtime],
        help="Serve the Interior View observability dashboard (loopback, static assets)",
    )
    dp.add_argument(
        "--new-session",
        action="store_true",
        help="Clear recent dialogue memory and bump session_id before serving",
    )
    dp.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    dp.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default: 127.0.0.1, loopback only)",
    )
    dp.add_argument(
        "--observer",
        action="store_true",
        help="Enable the build-time Claude observer pane/API (default: off, never auto-sends)",
    )
    dp.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to open a browser tab automatically",
    )
    dp.add_argument(
        "--session-mode",
        choices=["pipeline", "flow"],
        default="pipeline",
        help=(
            "pipeline (default): serve the existing acceptance-court companion path, "
            "unchanged. flow: POST /api/turn routes through Studio Flow "
            "(conditioned_kernel.flow.run_flow_turn) instead of pipeline.run_turn, and "
            "the Interior View renders FIELD BEFORE / WHAT TRAVELED / FIELD AFTER for "
            "each turn -- the dashboard-visible twin of `ck chat --mode flow`. Distinct "
            "from this command's own --mode (chat_json/generate_raw kernel transport), "
            "which flow mode still honors."
        ),
    )
    dp.set_defaults(func=_cmd_dashboard)

    # ACT-1 — Authority Crossover live TUI (Step 0 validation; not a ladder test)
    a1 = sub.add_parser(
        "act1",
        help=(
            "ACT-1 Authority Crossover — live terminal TUI against real Ollama models. "
            "MODEL vs KERNEL finalization across Q4/Q2 × think-off/on. "
            "Not a ladder test. Not Step 1. No synthetic/demo path."
        ),
    )
    a1.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit corpus size (default: full 8-case ACT-1 corpus)",
    )
    a1.add_argument(
        "--cells",
        default="A,B,C,D",
        help="Comma cells to run (default A,B,C,D = Q4-off,Q4-on,Q2-off,Q2-on)",
    )
    a1.add_argument(
        "--out-dir",
        default=None,
        help="Receipt directory (default: ~/.grok/docs/run01-survival/act1_runs/<timestamp>)",
    )
    a1.add_argument(
        "--no-tui",
        action="store_true",
        help="Headless runner only (print summary; still writes receipts)",
    )
    a1.set_defaults(func=_cmd_act1)

    # RUN 00.8B.2 — publication gate (no Ollama required)
    vp = sub.add_parser(
        "verify-publication",
        help="Verify governed-run artifact publication completeness (exit 0 iff complete)",
    )
    vp.add_argument("--run-dir", required=True, help="Governed run directory")
    vp.add_argument(
        "--commit-ref",
        default=None,
        help="Git commit to verify against (default: HEAD)",
    )
    vp.add_argument(
        "--repo-root",
        default=None,
        help="Repository root (default: auto-detect)",
    )
    vp.add_argument(
        "--staging",
        action="store_true",
        help="Pre-commit mode: skip commit-tree presence check",
    )
    vp.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit full publication receipt JSON",
    )
    vp.set_defaults(func=_cmd_verify_publication)

    fp = sub.add_parser(
        "finalize-governed-run",
        help="Finalize governed run: invoke publication verifier (fail closed if incomplete)",
    )
    fp.add_argument("--run-dir", required=True, help="Governed run directory")
    fp.add_argument("--commit-ref", default=None, help="Git commit (default: HEAD)")
    fp.add_argument("--repo-root", default=None, help="Repository root (default: auto)")
    fp.add_argument(
        "--staging",
        action="store_true",
        help="Pre-commit staging verification (no commit-tree check)",
    )
    fp.add_argument(
        "--execution-complete",
        action="store_true",
        help="Mark execution as complete (does not imply publication_complete)",
    )
    fp.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write receipts even when publication fails (still exit nonzero)",
    )
    fp.add_argument("--json", action="store_true", dest="as_json")
    fp.set_defaults(func=_cmd_finalize_governed_run)

    return p


def _cmd_verify_publication(args: argparse.Namespace) -> int:
    from conditioned_kernel.governed_run_finalization import (
        FinalizationError,
        verify_publication_only,
    )

    try:
        rec = verify_publication_only(
            run_dir=args.run_dir,
            repository_root=args.repo_root or str(repo_root()),
            commit_ref=args.commit_ref,
            staging_mode=bool(args.staging),
        )
    except FinalizationError as e:
        print(f"verify-publication: FAIL {e.reason_code}: {e}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(rec, indent=2, sort_keys=True))
    else:
        print(
            f"publication_complete={rec.get('publication_complete')} "
            f"declared={rec.get('declared_artifact_count')} "
            f"reasons={rec.get('reason_codes')}"
        )
    return 0 if rec.get("publication_complete") else 1


def _cmd_finalize_governed_run(args: argparse.Namespace) -> int:
    from conditioned_kernel.governed_run_finalization import (
        FinalizationError,
        finalize_governed_run,
    )

    try:
        result = finalize_governed_run(
            run_dir=args.run_dir,
            repository_root=args.repo_root or str(repo_root()),
            commit_ref=args.commit_ref,
            execution_complete=bool(args.execution_complete),
            staging_mode=bool(args.staging),
            write_receipts=True,
            fail_closed=not bool(args.allow_incomplete),
        )
    except FinalizationError as e:
        print(f"finalize-governed-run: FAIL {e.reason_code}: {e}", file=sys.stderr)
        # Attempt to still surface a receipt if written under allow path
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"finalize: execution_complete={result['execution_complete']} "
            f"publication_complete={result['publication_complete']} "
            f"review_ready={result['review_ready']} "
            f"release_ready={result['release_ready']}"
        )
        if result.get("reason_codes"):
            print(f"reasons: {result['reason_codes']}")
    return 0 if result["publication_complete"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Publication commands do not need state/logs defaults
    if args.command in ("verify-publication", "finalize-governed-run"):
        return int(args.func(args))
    if not getattr(args, "state_dir", None):
        args.state_dir = str(default_state_dir())
    if not getattr(args, "logs_dir", None):
        args.logs_dir = str(default_logs_dir())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
