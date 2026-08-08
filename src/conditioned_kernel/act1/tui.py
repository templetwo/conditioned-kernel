"""Live terminal TUI for ACT-1 — watch authority in real time."""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from conditioned_kernel.act1.runner import Act1Config, run_act1
from conditioned_kernel.act1.state import Act1LiveState


def _bar(done: int, total: int, width: int = 28) -> str:
    if total <= 0:
        return "·" * width
    filled = int(width * done / total)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _cell_line(c: dict[str, Any]) -> str:
    think = "on " if c.get("think") else "off"
    st = c.get("status", "?")
    mark = {"pending": "·", "running": "▶", "done": "✓", "error": "✗"}.get(st, "?")
    return (
        f" {mark} {c.get('cell_id')} {c.get('quant')}/{think}  "
        f"{c.get('done', 0)}/{c.get('total', 0)}  "
        f"dis={c.get('disagreements', 0)} auth_err={c.get('authority_errors', 0)}  "
        f"last gate={c.get('last_gate') or '—'} final={c.get('last_final') or '—'}"
    )


def render(state: Act1LiveState) -> str:
    s = state.snapshot()
    lines: list[str] = []
    lines.append("┌──────────────────────────────────────────────────────────────────────────┐")
    title = s["title"]
    lines.append(f"│ {title:<50} [LIVE] │")
    lines.append(
        f"│ host {s['host']:<20} ollama {str(s['ollama_version']):<12} ctx 32768     │"
    )
    lines.append("├──────────────────────────────────────────────────────────────────────────┤")
    lines.append("│  MODEL produces candidate → KERNEL gate decides → FINAL STATE            │")
    lines.append("│  Disagreement is evidence. It is not authority.                          │")
    lines.append("├──────────────────────────────────────────────────────────────────────────┤")
    cells = s.get("cells") or {}
    for cid in ("A", "B", "C", "D"):
        if cid in cells:
            line = _cell_line(cells[cid])
            lines.append(f"│{line:<74}│")
    lines.append("├──────────────────────────────────────────────────────────────────────────┤")
    done, total = s["generations_done"], s["generations_total"]
    lines.append(
        f"│ progress {_bar(done, total)}  {done}/{total:<4}  "
        f"auth_errors={s['authority_errors_total']:<3} elapsed={s['elapsed_s']:.0f}s │"
    )
    lines.append(f"│ phase: {s['phase']:<66}│")
    cur = (s.get("current_case") or "—")[:66]
    lines.append(f"│ now:   {cur:<66}│")
    msg = (s.get("message") or "")[:66]
    lines.append(f"│ msg:   {msg:<66}│")
    lines.append("├──────────────────────────────────────────────────────────────────────────┤")
    lines.append("│ recent (model → gate → kernel final)                                     │")
    recent = s.get("recent_events") or []
    if not recent:
        lines.append("│   (waiting for first generation…)                                        │")
    for ev in recent[-6:]:
        auth = "✓" if ev.get("authority_held") else "✗ AUTH LEAK"
        bit = (
            f"  {ev.get('cell_id')}/{ev.get('case_id')}: "
            f"{ev.get('model_claim')} → {ev.get('gate_result')} → "
            f"{ev.get('kernel_final')} {auth}"
        )[:74]
        lines.append(f"│{bit:<74}│")
    lines.append("├──────────────────────────────────────────────────────────────────────────┤")
    lines.append("│ keys: q=stop after current · p=pause/resume · (Ctrl-C abort)             │")
    lines.append("└──────────────────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)


def _try_rich_live(state: Act1LiveState, stop: threading.Event) -> bool:
    try:
        from rich.console import Console, Group
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except Exception:
        return False

    console = Console()

    def make_renderable():
        s = state.snapshot()
        table = Table(expand=True, show_header=True, header_style="bold")
        table.add_column("Cell", width=6)
        table.add_column("OP", width=10)
        table.add_column("Progress", width=10)
        table.add_column("Model", width=14)
        table.add_column("Gate", width=10)
        table.add_column("Final", width=12)
        table.add_column("Dis/Auth", width=10)
        for cid in ("A", "B", "C", "D"):
            c = (s.get("cells") or {}).get(cid) or {}
            think = "think-on" if c.get("think") else "think-off"
            st = c.get("status", "")
            style = {
                "running": "bold yellow",
                "done": "green",
                "error": "red",
            }.get(st, "dim")
            table.add_row(
                f"[{style}]{cid}[/{style}]",
                f"{c.get('quant')}/{think}",
                f"{c.get('done', 0)}/{c.get('total', 0)}",
                str(c.get("last_model") or "—"),
                str(c.get("last_gate") or "—"),
                str(c.get("last_final") or "—"),
                f"{c.get('disagreements', 0)}/{c.get('authority_errors', 0)}",
            )

        head = Text.assemble(
            ("ACT-1 Authority Crossover", "bold cyan"),
            ("  ·  ", "dim"),
            ("LIVE", "bold green"),
            ("  ·  ollama ", "dim"),
            (str(s.get("ollama_version") or "?"), "white"),
            (f"  ·  {s['generations_done']}/{s['generations_total']}", "dim"),
            (f"  ·  auth_errors={s['authority_errors_total']}", "bold red" if s["authority_errors_total"] else "green"),
        )
        body = Text(
            f"phase={s['phase']}  now={s.get('current_case') or '—'}\n"
            f"{s.get('message') or ''}\n\n"
            "MODEL claims  →  KERNEL gate  →  FINAL (gate wins on executable truth)\n"
            "Disagreement is evidence. Not authority."
        )
        recent_lines = []
        for ev in (s.get("recent_events") or [])[-6:]:
            auth = "✓ held" if ev.get("authority_held") else "✗ LEAK"
            recent_lines.append(
                f"{ev.get('cell_id')}/{ev.get('case_id')}: "
                f"{ev.get('model_claim')} → {ev.get('gate_result')} → "
                f"{ev.get('kernel_final')}  {auth}"
            )
        recent = Text("\n".join(recent_lines) or "(waiting…)", style="dim")
        return Group(
            head,
            Panel(table, title="Four operating points (Q4/Q2 × think off/on)", border_style="cyan"),
            Panel(body, title="Live", border_style="blue"),
            Panel(recent, title="Recent finalizations", border_style="white"),
            Text("q=stop after current · p=pause · Ctrl-C abort", style="dim"),
        )

    def input_loop():
        try:
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while not stop.is_set() and not state.finished:
                    r, _, _ = select.select([sys.stdin], [], [], 0.2)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch in ("q", "Q"):
                            state.stop_requested = True
                            state.set_phase("stopping", "stop requested — finishing current…")
                        elif ch in ("p", "P"):
                            state.paused = not state.paused
                            state.set_phase(
                                "paused" if state.paused else "running",
                                "paused" if state.paused else "resumed",
                            )
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass

    t = threading.Thread(target=input_loop, daemon=True)
    t.start()

    with Live(make_renderable(), console=console, refresh_per_second=4, screen=True) as live:
        while not stop.is_set() and not state.finished:
            live.update(make_renderable())
            time.sleep(0.25)
        live.update(make_renderable())
        time.sleep(0.5)
    return True


def _ansi_loop(state: Act1LiveState, stop: threading.Event) -> None:
    """Stdlib fallback — full-screen redraw."""
    hide = "\033[?25l"
    show = "\033[?25h"
    home = "\033[H\033[J"
    sys.stdout.write(hide)
    sys.stdout.flush()
    try:
        while not stop.is_set() and not state.finished:
            frame = home + render(state) + "\n"
            sys.stdout.write(frame)
            sys.stdout.flush()
            time.sleep(0.35)
        sys.stdout.write(home + render(state) + "\n")
        sys.stdout.flush()
        time.sleep(0.8)
    finally:
        sys.stdout.write(show)
        sys.stdout.flush()


def run_tui(config: Act1Config | None = None) -> int:
    """Start runner in background thread; paint live TUI in foreground."""
    cfg = config or Act1Config()
    state = Act1LiveState()
    stop = threading.Event()
    result: dict[str, Any] = {}

    def worker():
        nonlocal result
        try:
            result = run_act1(state, cfg)
        except Exception as e:
            state.set_phase("error", repr(e))
            state.finished = True
            result = {"error": repr(e)}

    th = threading.Thread(target=worker, daemon=True)
    th.start()

    try:
        if not _try_rich_live(state, stop):
            _ansi_loop(state, stop)
    except KeyboardInterrupt:
        state.stop_requested = True
        state.set_phase("stopping", "Ctrl-C — stopping…")
        th.join(timeout=30)
        stop.set()
        print(render(state))
        return 130

    th.join(timeout=5)
    stop.set()

    # final plain summary for scrollback
    print()
    print(render(state))
    if result:
        print()
        print(
            f"summary: generations={result.get('generations')} "
            f"authority_errors={result.get('authority_errors')} "
            f"primary_pass={result.get('primary_pass')} "
            f"out={result.get('out_dir')}"
        )
    return 0 if result.get("primary_pass", True) and "error" not in result else 1
