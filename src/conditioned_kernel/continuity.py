"""Continuity experiment: arm construction and Episode B scoring.

New module by design. The measurement layer (score.py, return_path/, generate.py)
is frozen at 54 passing tests during this build and is imported from, never
edited. See docs/CONTINUITY_EXPERIMENT.md for the preregistered design.

Three arms are built from ONE frozen Episode A artifact set, so "same amount of
information" is a construction rule rather than an aspiration:

    bare_serialized  naive chronological dump, truncated to the same byte budget
    ck_packet        the compiled arrival packet
    broken_packet    deliberately corrupted packet -- permanent floor control

Whoever writes the bare condition decides the outcome, so its serialization is
specified here and in the protocol, not chosen at run time.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Frozen-layer imports. Read-only dependency.
from conditioned_kernel.return_path.validate import _fact_contradictions, is_responsive

# ---------------------------------------------------------------------------
# Arm construction
# ---------------------------------------------------------------------------


def _budget_bytes(packet: dict[str, Any]) -> int:
    """The byte budget every arm must match: whatever the CK packet costs."""
    return len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def build_bare_serialized(artifacts: dict[str, Any], budget_bytes: int) -> str:
    """Naive chronological dump of the same artifacts, truncated to budget.

    Deliberately unstructured: no ordering by relevance, no labelling, no
    schema. This is the honest 'ordinary prompt carrying the same information'
    control. Order is insertion order of the frozen artifacts, which is
    chronological by construction.
    """
    parts: list[str] = []
    state = artifacts.get("state") or {}
    if state.get("goal"):
        parts.append(str(state["goal"]))
    for fact in artifacts.get("facts") or []:
        parts.append(str(fact))
    for t in artifacts.get("threads") or []:
        if isinstance(t, dict):
            parts.append(f"{t.get('id', '')} {t.get('title', '')}".strip())
        else:
            parts.append(str(t))
    for entry in artifacts.get("episode_a_log") or []:
        parts.append(str(entry))
    blob = "\n".join(p for p in parts if p)
    encoded = blob.encode("utf-8")[:budget_bytes]
    # avoid splitting a multibyte char at the boundary
    return encoded.decode("utf-8", errors="ignore")


def build_broken_packet(packet: dict[str, Any], *, seed: int = 42) -> dict[str, Any]:
    """Floor control: structurally intact, semantically destroyed.

    Keeps the shape (so any advantage cannot be attributed to formatting alone)
    while blanking the state that carries continuity. If an arm scores at or
    below this on a given run, the instrument did not detect continuity that
    day -- which is why it stays in EVERY run, not just a one-off validation.
    """
    broken = json.loads(json.dumps(packet))  # deep copy
    digest = broken.get("state_digest") or {}
    if "goal" in digest:
        digest["goal"] = "[REDACTED]"
    broken["state_digest"] = digest
    broken["facts"] = ["[REDACTED]" for _ in (broken.get("facts") or [])]
    broken["open_threads"] = [
        {"id": "thread_redacted", "title": "[REDACTED]"} for _ in (broken.get("open_threads") or [])
    ]
    broken["_broken"] = True
    return broken


def context_hashes(
    ck_packet: dict[str, Any], bare_text: str, broken_packet: dict[str, Any]
) -> dict[str, Any]:
    """Receipt fields proving what each arm actually received."""

    def h(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()[:16]

    ck_bytes = json.dumps(ck_packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    br_bytes = json.dumps(broken_packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    bare_bytes = bare_text.encode("utf-8")
    return {
        "continuity_packet_hash": h(ck_bytes),
        "bare_context_hash": h(bare_bytes),
        "broken_packet_hash": h(br_bytes),
        "ck_packet_bytes": len(ck_bytes),
        "bare_context_bytes": len(bare_bytes),
        "broken_packet_bytes": len(br_bytes),
        # Equal-budget claim is reported, never assumed.
        "budget_delta_bytes": len(bare_bytes) - len(ck_bytes),
    }


# ---------------------------------------------------------------------------
# Grounding (continuity dimension 5)
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:gb|mb|kb|b|m|k|billion|million|%|x)?\b", re.I)


def extract_numeric_claims(text: str) -> list[str]:
    """Numeric tokens an answer asserts. Crude on purpose -- mechanical, not NLI."""
    return [m.group(0).strip().lower() for m in _NUMERIC_RE.finditer(text or "")]


def evidence_blob(packet: dict[str, Any], artifacts: dict[str, Any]) -> str:
    """Everything the answer is allowed to have gotten a specific from."""
    parts = [json.dumps(packet, ensure_ascii=False), json.dumps(artifacts, ensure_ascii=False)]
    return " ".join(parts).lower()


def grounding_violations(
    answer: str,
    packet: dict[str, Any],
    artifacts: dict[str, Any],
    forbidden_inventions: list[str] | None = None,
) -> list[str]:
    """Unsupported numeric or categorical claims fail unless grounded in evidence.

    This is the narrow repair for the observed gemma3:1b failure, where the
    model was ACCEPTED while asserting "the minimum viable model size is 2GB" --
    a fabricated specific that passed because the answer key only required the
    phrase "minimum viable" to appear.

    Deliberately narrow. It does not become a general truth-validation
    subsystem; it checks that specifics came from somewhere.
    """
    viol: list[str] = []
    blob = evidence_blob(packet, artifacts)
    for claim in extract_numeric_claims(answer):
        # Word-boundary match, never a bare substring. Stripping "2gb" to "2"
        # and doing `"2" in blob` matches the 2 inside "120" -- which let the
        # observed gemma3:1b fabrication read as grounded.
        num = re.match(r"\d+(?:\.\d+)?", claim)
        if not num:
            continue
        unit = claim[num.end():].strip()
        pattern = rf"\b{re.escape(num.group(0))}\s*{re.escape(unit)}\b" if unit \
            else rf"\b{re.escape(num.group(0))}\b"
        if not re.search(pattern, blob):
            viol.append(f"ungrounded_numeric:{claim}")
    for phrase in forbidden_inventions or []:
        if str(phrase).lower() in (answer or "").lower():
            viol.append(f"forbidden_invention:{phrase}")
    return viol


# ---------------------------------------------------------------------------
# Episode B scoring — seven dimensions, scored separately
# ---------------------------------------------------------------------------


_TRACE_TOKEN_RE = re.compile(r"\b(?:thread_[a-z0-9_]+|[A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)+)\b")


def progress_trace_tokens(progress_trace: dict[str, Any] | None) -> list[str]:
    """Concrete identifiers a progress claim must reference.

    The corpus schema (published in the work order) declares progress_trace as
    {kind, check} where `check` is a prose assertion naming the trace, e.g.
    "answer or next_state.thread_touch references thread_gamma_receipt or
    CK-SPRINT-GAMMA-7". The identifiers inside it ARE the mechanical part, so
    they are extracted rather than requiring the corpus to restate them.

    `accept_any_of` is honoured first if a task supplies it, so both shapes work.
    """
    pt = progress_trace or {}
    explicit = [str(x) for x in (pt.get("accept_any_of") or []) if str(x).strip()]
    if explicit:
        return explicit
    # Schema field names appear inside `check` prose but are not traces --
    # crediting them would let a generic mention of "thread_touch" fire the
    # dimension without referencing any actual state.
    stop = {"thread_touch", "next_state", "episode_a", "episode_b", "answer_key"}
    found = set(_TRACE_TOKEN_RE.findall(str(pt.get("check") or "")))
    return sorted(t for t in found if t.lower() not in stop)


def _mentions_any(text: str, options: list[str]) -> bool:
    t = (text or "").lower()
    return any(str(o).lower() in t for o in options if str(o).strip())


def score_episode_b(
    answer: str,
    *,
    task: dict[str, Any],
    packet: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    """Score one Episode B answer across the seven continuity dimensions.

    Reported separately rather than collapsed into one acceptance flag, because
    a single flag is what let goal-echo degeneracy score 1.0 in the M1 audit.
    """
    ep_b = task.get("episode_b") or {}
    answer = answer or ""
    state = artifacts.get("state") or {}

    goal = str(state.get("goal") or (packet.get("state_digest") or {}).get("goal") or "")
    goal_tokens = [w for w in re.findall(r"[a-z0-9]{5,}", goal.lower())][:8]

    threads = artifacts.get("threads") or []
    thread_ids = [str(t.get("id")) for t in threads if isinstance(t, dict) and t.get("id")]
    thread_titles = [str(t.get("title")) for t in threads if isinstance(t, dict) and t.get("title")]

    key = ep_b.get("answer_key") or {}
    nxt = ep_b.get("correct_next_action") or {}
    grounded = ep_b.get("grounded_claims") or {}
    forbidden = list(grounded.get("forbidden_inventions") or [])

    g_viol = grounding_violations(answer, packet, artifacts, forbidden)
    contradictions = _fact_contradictions(answer, packet)

    # Absence-based dimensions (no contradiction, avoided failure, no invention)
    # are satisfied vacuously by ANY text. Gating them on length was not enough:
    # an irrelevant sentence ("the weather in Paris is nice") still collected
    # all three and scored 0.43, and a goal echo scored 0.57. That is a free
    # floor under every arm, including the broken-packet control, which would
    # compress exactly the range this experiment needs to measure.
    #
    # Rule: you are not credited for contradicting nothing if you resumed
    # nothing. Absence dimensions require positive engagement with the resume
    # task. recovers_goal is deliberately EXCLUDED from what counts as
    # engagement, because echoing the goal is the known degenerate strategy.

    # Anything already present in the Episode B prompt cannot demonstrate
    # carried state -- reproducing the question is not continuity. Observed:
    # broken_packet (state REDACTED) scored 0.571 by restating the question,
    # because the trace code appeared in the prompt, fired progress_trace, and
    # that unlocked the three absence dimensions. Same amplification path as
    # goal-echo, entering through the question instead of the goal.
    _prompt_l = str(ep_b.get("prompt") or "").lower()

    def _not_given(tokens: list[str]) -> list[str]:
        return [t for t in tokens if str(t).lower() not in _prompt_l]

    _trace_tokens = _not_given(progress_trace_tokens(ep_b.get("progress_trace")))
    _positive = {
        "recovers_goal": bool(goal_tokens) and _mentions_any(answer, goal_tokens),
        "identifies_unresolved_state": _mentions_any(
            answer, _not_given(thread_ids + thread_titles)
        ),
        "correct_next_action": _mentions_any(answer, list(nxt.get("accept_any_of") or []))
        if nxt.get("accept_any_of")
        else False,
        "progress_trace": bool(_trace_tokens) and _mentions_any(answer, _trace_tokens),
    }
    engaged = (
        _positive["identifies_unresolved_state"]
        or _positive["correct_next_action"]
        or _positive["progress_trace"]
    )

    dims: dict[str, bool] = {
        # 1 — recovers the active goal
        "recovers_goal": bool(goal_tokens) and _mentions_any(answer, goal_tokens),
        # 2 — preserves explicit constraints (present and uncontradicted)
        "preserves_constraints": engaged and not contradictions,
        # 3 — identifies the unresolved state (tokens the question did not supply)
        "identifies_unresolved_state": _mentions_any(
            answer, _not_given(thread_ids + thread_titles)
        ),
        # 4 — avoids a previously discovered failure
        "avoids_known_failure": engaged
        and not _mentions_any(answer, list(task.get("known_failures") or [])),
        # 5 — does not invent unsupported prior findings
        "no_unsupported_invention": engaged and not g_viol,
        # 6 — chooses the correct next action
        "correct_next_action": _mentions_any(answer, list(nxt.get("accept_any_of") or []))
        if nxt.get("accept_any_of")
        else False,
        # 7 — produces measurable task progress
        "progress_trace": bool(_trace_tokens) and _mentions_any(answer, _trace_tokens),
    }

    must_any = key.get("must_mention_any") or []
    if must_any and isinstance(must_any[0], str):
        must_any = [must_any]
    key_ok = all(_mentions_any(answer, list(group)) for group in must_any) if must_any else True
    if _mentions_any(answer, list(key.get("must_not_mention_any") or [])):
        key_ok = False
    if len(answer.split()) < int(key.get("min_words") or 0):
        key_ok = False

    scored = [v for v in dims.values()]
    return {
        "dimensions": dims,
        "continuity_score": sum(1 for v in scored if v) / len(scored),
        "key_ok": key_ok,
        "responsive": bool(is_responsive(answer, str(ep_b.get("prompt") or ""))),
        "grounding_violations": g_viol,
        "contradictions": contradictions,
        "answer": answer[:500],
        "word_count": len(answer.split()),
    }
