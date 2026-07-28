"""Debug-brief markdown builders — spec §11 (compact / full) and the
`GET /api/turn/:id/brief` "full debug brief" description in spec §12.

Two distinct payloads, kept separate per spec §11:

* `build_compact_brief` — the (never-auto-sent) cloud observer payload:
  composition figures, candidate, non-passing checks, evidence audit,
  source map, persistence. Prior dialogue bodies are withheld by default
  (replaced with byte counts and similarity) unless the caller explicitly
  opts in.
* `build_full_debug_brief` — for `GET /api/turn/:id/brief` / `curl`, so
  Claude Code can read a turn without touching the running dashboard:
  everything the compact brief has, plus the full compiled packet and the
  complete TurnTrace JSON.

Every figure here is read straight off the already-assembled TurnTrace
dict this module is handed — nothing is recomputed with a different rule
than `trace.py` / `compute.py` already applied. Citation audit and memory
repetition (needed for the withheld-dialogue summary) go through the same
`compute.py` functions the frontend panels use, never a re-typed copy.
"""

from __future__ import annotations

import json
from typing import Any

from conditioned_kernel.observatory import compute

ASK_LABELS: dict[str, str] = {
    "explain": "Explain this turn",
    "bug": "Where is the bug?",
    "change": "What should Claude Code change?",
}

# Spec §11: "The system prompt must force the distinction between designed
# behaviour and implementation defect, forbid inventing file contents or
# values, and forbid describing model reasoning or attention." Shown
# verbatim by the observer stage endpoint — "Show the exact prompt that was
# sent."
OBSERVER_SYSTEM_PROMPT = (
    "You are a build-time observer reading one Interior View trace from the Conditioned "
    "Kernel project. You are not part of the running system: you never call or wrap "
    "pipeline.run_turn, and nothing you say is written to state/ or logs/. Distinguish "
    "sharply between designed behaviour (a rule the code deliberately applies — e.g. a "
    "companion-mode advisory that is recorded but not enforced) and an implementation "
    "defect (the code did something its own rules did not intend). Never invent file "
    "contents, byte counts, or values that are not present in the brief below — if the "
    "brief does not settle a question, say so and name the value that would settle it. "
    "Never describe the model's reasoning or attention; you may describe what the "
    "pipeline's code did, never what the kernel 'was thinking'."
)


def _final_pass(trace: dict[str, Any]) -> dict[str, Any]:
    passes = trace.get("passes") or []
    return passes[-1] if passes else {}


def _composition_section(trace: dict[str, Any]) -> str:
    rows = trace.get("context_share_bytes") or []
    lines = ["| Source | Bytes | Share |", "|---|---|---|"]
    for r in rows:
        lines.append(f"| {r.get('source')} | {r.get('bytes')} B | {r.get('share_pct')}% |")
    total = sum(r.get("bytes", 0) for r in rows)
    lines.append("")
    lines.append(
        f"*Byte census of the model input — not influence, attention, or causal "
        f"contribution. Total: {total} B.*"
    )
    return "\n".join(lines)


def _candidate_section(trace: dict[str, Any]) -> str:
    fp = _final_pass(trace)
    lines = [
        f"**Answer** ({fp.get('word_count', 0)} words, decision={fp.get('decision')}):",
        "```",
        str(fp.get("answer") or "(no answer)"),
        "```",
        f"- evidence_used: {json.dumps(fp.get('evidence_used') or [], ensure_ascii=False)}",
        f"- thread_touch: {json.dumps(fp.get('thread_touch') or [], ensure_ascii=False)}",
        f"- pass_index: {fp.get('pass_index')} of {len(trace.get('passes') or [])} pass(es)",
    ]
    return "\n".join(lines)


def _non_passing_checks_section(trace: dict[str, Any]) -> str:
    fp = _final_pass(trace)
    violations = fp.get("violations") or []
    advisories = fp.get("advisories") or []
    if not violations and not advisories:
        return "*All checks passed — no violations, no advisories.*"
    lines: list[str] = []
    if violations:
        lines.append("**FAIL (violations — rejected the candidate):**")
        for v in violations:
            lines.append(f"- {v}")
    if advisories:
        lines.append("**ADVISORY (recorded, not enforced in companion mode):**")
        for a in advisories:
            lines.append(f"- {a}")
    return "\n".join(lines)


def _evidence_audit_section(trace: dict[str, Any]) -> str:
    fp = _final_pass(trace)
    packet = fp.get("packet") or trace.get("packet") or {}
    evidence_used = fp.get("evidence_used") or []
    if not evidence_used:
        return "*No citations to audit — evidence_used is empty.*"
    audit = compute.citation_audit(packet, evidence_used)
    lines = ["| Citation | Status | Reason |", "|---|---|---|"]
    for row in audit:
        cited = str(row.get("citation") or "")[:80].replace("|", "\\|")
        reason = str(row.get("reason") or "").replace("|", "\\|")
        lines.append(f"| {cited} | {row.get('status')} | {reason} |")
    return "\n".join(lines)


def _source_map_section(trace: dict[str, Any]) -> str:
    lines = ["| # | Stage | Source |", "|---|---|---|"]
    for s in trace.get("stages") or []:
        loc = f"{s.get('source_module')}:{s.get('source_line')} · {s.get('source_function')}"
        lines.append(f"| {s.get('index', 0):02d} | {s.get('name')} | {loc} |")
    return "\n".join(lines)


def _persistence_section(trace: dict[str, Any]) -> str:
    persistence = trace.get("persistence") or {}
    applied = persistence.get("applied_updates") or []
    lines = [
        f"- recent_turn_appended: {persistence.get('recent_turn_appended')}",
        f"- applied_updates: {json.dumps(applied, ensure_ascii=False)}",
    ]
    return "\n".join(lines)


def _dialogue_summary_withheld(trace: dict[str, Any]) -> str:
    """Prior dialogue bodies withheld — spec §11: replaced with byte counts
    and similarity, never the literal text, unless the caller explicitly
    passed `include_prior_dialogue=True` to `build_compact_brief`."""
    fp = _final_pass(trace)
    packet = fp.get("packet") or trace.get("packet") or {}
    recent = packet.get("recent_turns") or []
    rep = compute.memory_repetition(recent)
    total_bytes = compute.bytes_len(
        json.dumps(recent, ensure_ascii=False, separators=(",", ":"))
    )
    plural = "y" if len(recent) == 1 else "ies"
    return (
        f"*{len(recent)} recent dialogue entr{plural} withheld ({total_bytes} B total). "
        f"Pairwise token-similarity max: {round(rep.get('pairwise_max', 0.0) * 100)}% "
        f"(repetition detected: {rep.get('detected')}, threshold {rep.get('threshold')}).*"
    )


def _dialogue_full(trace: dict[str, Any]) -> str:
    fp = _final_pass(trace)
    packet = fp.get("packet") or trace.get("packet") or {}
    recent = packet.get("recent_turns") or []
    if not recent:
        return "*No recent dialogue in this packet.*"
    lines = []
    for i, t in enumerate(recent):
        if not isinstance(t, dict):
            continue
        lines.append(
            f"- [{i}] user: {t.get('user')!r} · answer: {t.get('answer')!r} · ts: {t.get('ts')}"
        )
    return "\n".join(lines)


def build_compact_brief(
    trace: dict[str, Any],
    *,
    ask: str = "explain",
    include_prior_dialogue: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Returns `(markdown, disclosure)`. Never includes the full packet JSON
    or the raw trace JSON — that is the full debug brief's job, and the
    disclosure dict says so honestly (spec §11's seven disclosure fields,
    plus the constant `persists_nothing` guarantee)."""
    ask_label = ASK_LABELS.get(ask, ASK_LABELS["explain"])
    dialogue_section = (
        _dialogue_full(trace) if include_prior_dialogue else _dialogue_summary_withheld(trace)
    )
    parts = [
        f"# Interior View — compact brief ({ask_label})",
        f"turn_id: {trace.get('turn_id')} · session: {trace.get('session_id')} · "
        f"decision: {(trace.get('final_decision') or {}).get('label')}",
        "",
        "## The human's words",
        "```",
        str(trace.get("user_input") or ""),
        "```",
        "",
        "## Composition (context share, bytes)",
        _composition_section(trace),
        "",
        "## Candidate",
        _candidate_section(trace),
        "",
        "## Non-passing checks",
        _non_passing_checks_section(trace),
        "",
        "## Evidence audit",
        _evidence_audit_section(trace),
        "",
        "## Source map",
        _source_map_section(trace),
        "",
        "## Persistence",
        _persistence_section(trace),
        "",
        "## Prior dialogue",
        dialogue_section,
        "",
        "---",
        "*Compact brief: recent-dialogue bodies are withheld by default, and the full "
        "packet JSON / full trace JSON are never included here — see the full debug "
        "brief (`GET /api/turn/:id/brief`) for those.*",
    ]
    markdown = "\n".join(parts)
    byte_count = compute.bytes_len(markdown)
    disclosure = {
        "destination": "cloud (Claude, build-time observer only)",
        "payload_kind": "compact_brief",
        "byte_count": byte_count,
        "includes_current_user_message": True,
        "includes_prior_dialogue_bodies": bool(include_prior_dialogue),
        "includes_full_packet_json": False,
        "includes_file_paths": True,
        "persists_nothing": True,
    }
    return markdown, disclosure


def build_full_debug_brief(trace: dict[str, Any]) -> str:
    """`GET /api/turn/:id/brief` — everything, including the packet and the
    full TurnTrace JSON, for Claude Code / local inspection via `curl`.
    Never sent to a cloud endpoint on its own — the observer only ever
    stages the compact brief by default (spec §11: "The full brief should
    not be the default cloud payload; 20 KB costs ~20s")."""
    fp = _final_pass(trace)
    packet = fp.get("packet") or trace.get("packet") or {}
    parts = [
        "# Interior View — full debug brief",
        f"turn_id: {trace.get('turn_id')} · session: {trace.get('session_id')} · "
        f"started: {trace.get('started_at')} · completed: {trace.get('completed_at')}",
        f"decision: {(trace.get('final_decision') or {}).get('label')}",
        "",
        "## The human's words",
        "```",
        str(trace.get("user_input") or ""),
        "```",
        "",
        "## Composition (context share, bytes)",
        _composition_section(trace),
        "",
        "## Candidate",
        _candidate_section(trace),
        "",
        "## Non-passing checks",
        _non_passing_checks_section(trace),
        "",
        "## Evidence audit",
        _evidence_audit_section(trace),
        "",
        "## Source map (12 stages)",
        _source_map_section(trace),
        "",
        "## Persistence",
        _persistence_section(trace),
        "",
        "## Recent dialogue (full)",
        _dialogue_full(trace),
        "",
        "## Full compiled packet",
        "```json",
        json.dumps(packet, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Full TurnTrace JSON",
        "```json",
        json.dumps(trace, ensure_ascii=False, indent=2),
        "```",
        "",
        "---",
        "*Every number above is computed from this same trace by the rules "
        "`conditioned_kernel.observatory.compute` applies — never transcribed. Context "
        "share is a byte census, not attention.*",
    ]
    return "\n".join(parts)


__all__ = [
    "ASK_LABELS",
    "OBSERVER_SYSTEM_PROMPT",
    "build_compact_brief",
    "build_full_debug_brief",
]
