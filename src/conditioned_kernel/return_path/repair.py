"""Build structured repair plans for a second compile pass.

Hints are mechanical and concrete — teach the contract without greasing it.
"""

from __future__ import annotations

from typing import Any


def json_list(items: list[str]) -> str:
    return "[" + ", ".join(f'"{x}"' for x in items[:4]) + "]"


def _allowed_thread_ids(packet: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for t in packet.get("open_threads") or []:
        if isinstance(t, dict) and t.get("id"):
            out.append(str(t["id"]))
    return out


def _evidence_samples(packet: dict[str, Any], limit: int = 4) -> list[str]:
    samples: list[str] = []
    for fact in packet.get("facts") or []:
        samples.append(str(fact)[:160])
        if len(samples) >= limit:
            return samples
    for t in packet.get("open_threads") or []:
        if isinstance(t, dict) and t.get("title"):
            samples.append(str(t["title"])[:160])
        if len(samples) >= limit:
            break
    return samples


def _hint_for_violation(v: str, packet: dict[str, Any]) -> str | None:
    goal = str((packet.get("state_digest") or {}).get("goal") or "")
    threads = _allowed_thread_ids(packet)
    facts = _evidence_samples(packet, 3)

    if v == "goal_not_referenced":
        return (
            "FIX goal_not_referenced: first sentence must include key words from the goal. "
            f"Goal snippet: {goal[:160]}"
        )
    if v == "evidence_used_empty":
        return (
            "FIX evidence_used_empty: set evidence_used to 1-3 strings copied from facts. "
            f"Examples: {facts}"
        )
    if v.startswith("evidence_not_in_packet"):
        return (
            "FIX evidence_not_in_packet: do not invent evidence. "
            f"Copy exactly from: {facts}"
        )
    if v.startswith("unknown_thread_touch"):
        return (
            "FIX unknown_thread_touch: set next_state.thread_touch to [] "
            f"or a JSON array of exact ids only, e.g. {json_list(threads)}"
        )
    if v == "template_echo" or v == "template_echo_evidence":
        return (
            "FIX template_echo: do not copy placeholders. Write a real answer "
            "and real evidence strings from facts."
        )
    if v.startswith("parse_failed") or v.startswith("json_"):
        return (
            'FIX parse: return only JSON like '
            '{"answer":"...","evidence_used":["..."],"next_state":{"thread_touch":[]}}'
        )
    if v == "missing_answer" or v == "required_section:answer":
        return "FIX missing_answer: provide a non-empty answer string."
    if v.startswith("max_words_exceeded"):
        max_w = (packet.get("constraints") or {}).get("max_words", 120)
        return f"FIX max_words: shorten answer to ≤{max_w} words."
    if v.startswith("forbidden:"):
        return f"FIX forbidden content: remove {v.split(':', 1)[-1]} from answer."
    if v == "prior_answer_present_but_invalid_contract":
        return None  # meta note, skip as primary hint
    return f"FIX {v}"


def build_repair_annotations(
    receipt: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
) -> list[str]:
    """Backward-compatible list of short annotation strings."""
    plan = build_repair_plan(receipt, candidate, packet or {})
    return plan["annotations"]


def build_repair_plan(
    receipt: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured repair plan embedded into the next arrival packet."""
    packet = packet or {}
    violations = list(receipt.get("violations") or [])
    if candidate and candidate.get("parse_error"):
        violations.append(f"parse_failed:{candidate['parse_error']}")

    hints: list[str] = []
    for v in violations:
        h = _hint_for_violation(v, packet)
        if h and h not in hints:
            hints.append(h)

    goal = str((packet.get("state_digest") or {}).get("goal") or "")
    threads = _allowed_thread_ids(packet)
    facts = _evidence_samples(packet, 4)

    # Shape-only skeleton — NEVER put real prose a tiny model will copy verbatim
    example = {
        "answer": "STRING",
        "evidence_used": ["STRING_FROM_FACTS"],
        "next_state": {"thread_touch": []},
    }

    annotations: list[str] = []
    for v in violations:
        if v not in annotations:
            annotations.append(v[:120])
    annotations.extend(hints[:6])

    # Dedup preserve order
    seen: set[str] = set()
    deduped: list[str] = []
    for a in annotations:
        if a not in seen:
            seen.add(a)
            deduped.append(a)

    return {
        "pass_index": 1,
        "violations": violations[:8],
        "hints": hints[:6],
        "allowed_thread_ids": threads,
        "allowed_evidence_samples": facts,
        "goal_snippet": goal[:200],
        "example_json": example,
        "annotations": deduped[:12],
        "instruction": (
            "Previous output failed validation. Return corrected JSON only. "
            "Use allowed_evidence_samples or facts only. "
            "thread_touch only from allowed_thread_ids or []. "
            "Answer must reference the goal_snippet."
        ),
    }
