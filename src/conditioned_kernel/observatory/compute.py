"""Computed values for the Interior View trace — the honesty contract.

Every figure this module returns is derived from a packet / candidate /
receipt the pipeline actually produced, using the same rules the pipeline
applies. Where the pipeline already exposes the rule as a function
(`validate._packet_evidence_pool`, `validate._evidence_ok`, ...) this module
imports and calls it rather than re-typing the threshold somewhere else that
could drift. Nothing here is transcribed into a display value ahead of time;
every function recomputes from its arguments on every call.

See design_handoff_interior_view/README.md §10 for the contract this module
implements, and §6/§7 for the stage-status and observation rules.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any, Callable

from conditioned_kernel.compile import _VOLATILE_PACKET_FIELDS
from conditioned_kernel.edge import enforce_packet_budget as _enforce_packet_budget
from conditioned_kernel.edge import packet_byte_size
from conditioned_kernel.generate import InferenceResult, OllamaClient
from conditioned_kernel.paths import repo_root
from conditioned_kernel.return_path.accept import accept_candidate
from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.repair import build_repair_plan
from conditioned_kernel.return_path.validate import (
    TEMPLATE_ECHO_MARKERS,
    _evidence_ok,
    _packet_evidence_pool,
    prior_accepted_answer,
    user_prompt_changed,
    validate_candidate,
)
from conditioned_kernel.state import SubstrateState, fit_recent_turns

# ---------------------------------------------------------------------------
# Symmetric token similarity — spec §10: "Similarity must be symmetric. Use
# Jaccard, |A∩B| / |A∪B|, over 4+-character lowercase tokens. Asymmetric
# containment scores 1.0 for any long answer that merely recites the same
# boilerplate, which is wrong." Every similarity figure in this module goes
# through this one function.
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")


def tokenize(text: str | None, *, min_len: int = 4) -> set[str]:
    """Lowercase alnum tokens of at least `min_len` characters."""
    if min_len == 4:
        return set(_TOKEN_RE.findall((text or "").lower()))
    return set(re.findall(rf"[a-z0-9]{{{min_len},}}", (text or "").lower()))


def jaccard_similarity(a: str | None, b: str | None, *, min_len: int = 4) -> float:
    """|A∩B| / |A∪B| over 4+-char lowercase tokens. The only similarity metric
    used anywhere in this module — see module docstring."""
    ta, tb = tokenize(a, min_len=min_len), tokenize(b, min_len=min_len)
    if not ta and not tb:
        return 0.0
    union = len(ta | tb)
    return (len(ta & tb) / union) if union else 0.0


def bytes_len(s: str) -> int:
    return len(s.encode("utf-8"))


# ---------------------------------------------------------------------------
# Context share — spec §10: buckets the MODEL INPUT, not the raw packet.
# packet_id / created_at excluded because build_model_input strips them.
# ---------------------------------------------------------------------------

_CONTEXT_SHARE_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("current_user_input", "Current user input", "packet.user_input"),
    ("recent_dialogue", "Recent dialogue", "packet.recent_turns"),
    (
        "durable_state",
        "Durable state",
        "state_digest · facts · open_threads · session_id · authoritative_obligation",
    ),
    (
        "system_instructions",
        "System instructions",
        "compile.build_model_input system string · packet.repair",
    ),
    ("output_schema", "Output schema", "compile.CANDIDATE_FORMAT"),
    ("constraints", "Constraints", "packet.constraints · packet.acceptance_contract"),
    (
        "context_field",
        "Context field selection",
        "packet.context_field selected/omitted contributions",
    ),
)


def _model_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """The exact key set build_model_input serializes (imported constant, not
    a re-typed copy of it)."""
    return {
        k: v
        for k, v in packet.items()
        if not str(k).startswith("_") and k not in _VOLATILE_PACKET_FIELDS
    }


def _keyed_bytes(model_packet: dict[str, Any], key: str) -> int:
    """Bytes one packet key contributes to the compact-serialized model
    packet: `"key":value` plus one separator byte. Absent keys contribute 0."""
    if key not in model_packet:
        return 0
    piece = json.dumps(key, ensure_ascii=False) + ":" + json.dumps(
        model_packet[key], ensure_ascii=False, separators=(",", ":")
    )
    return bytes_len(piece) + 1


def _system_text_from_model_input(model_input: dict[str, Any]) -> str:
    """Pull the literal system text back out of a real build_model_input
    payload, rather than keeping a second copy of the string compile.py
    builds inline (which would drift the moment that prompt changes)."""
    mode = model_input.get("mode")
    payload = model_input.get("payload") or {}
    if mode == "chat_json":
        for m in payload.get("messages") or []:
            if m.get("role") == "system":
                return str(m.get("content") or "")
        return ""
    prompt = str(payload.get("prompt") or "")
    marker = "\n\nARRIVAL_PACKET:\n"
    idx = prompt.find(marker)
    return prompt[:idx] if idx >= 0 else ""


def context_share_bytes(packet: dict[str, Any], model_input: dict[str, Any]) -> list[dict[str, Any]]:
    """Bucket model-input bytes by source (spec §10, §7 stage 04).

    Byte census only — never labelled influence, attention, or causal
    contribution. `source` is the human label the frontend export shape
    expects; `source_id` is a stable slug for programmatic lookup.
    """
    mp = _model_packet(packet)
    system_text = _system_text_from_model_input(model_input)
    schema = (model_input.get("payload") or {}).get("format")
    schema_bytes = (
        bytes_len(json.dumps(schema, ensure_ascii=False, separators=(",", ":"))) if schema else 0
    )
    system_bytes = bytes_len(json.dumps(system_text, ensure_ascii=False)) if system_text else 0

    # Companion model input is no longer a single Packet JSON; derive user/context
    # bytes from the actual messages when present.
    user_msg_bytes = 0
    payload = model_input.get("payload") or {}
    for m in payload.get("messages") or []:
        if m.get("role") == "user":
            user_msg_bytes += bytes_len(str(m.get("content") or ""))
    values = {
        "current_user_input": _keyed_bytes(mp, "user_input") or (
            bytes_len(str(packet.get("user_input") or "")) if user_msg_bytes else 0
        ),
        "recent_dialogue": _keyed_bytes(mp, "recent_turns"),
        "durable_state": (
            _keyed_bytes(mp, "state_digest")
            + _keyed_bytes(mp, "facts")
            + _keyed_bytes(mp, "open_threads")
            + _keyed_bytes(mp, "session_id")
            + _keyed_bytes(mp, "authoritative_obligation")
        ),
        "system_instructions": system_bytes + _keyed_bytes(mp, "repair"),
        "output_schema": schema_bytes,
        "constraints": _keyed_bytes(mp, "constraints") + _keyed_bytes(mp, "acceptance_contract"),
        # Observability census of the selection record (not model tokens as a blob —
        # volatile field excluded from model_packet; count selected content bytes).
        "context_field": sum(
            len(str((c or {}).get("content") or "").encode("utf-8"))
            for c in ((packet.get("context_field") or {}).get("selected") or [])
            if isinstance(c, dict)
        ),
    }
    # If companion field path, durable_state is the selected facts share
    if (packet.get("context_field") or {}).get("schema") == "ck.context_field.v1":
        # Prefer message user content for current_input visibility in companion
        if user_msg_bytes:
            # Approximate: message contains selected context + current human message
            cur = bytes_len(str(packet.get("user_input") or ""))
            values["current_user_input"] = cur
            values["durable_state"] = max(0, user_msg_bytes - cur)
    total = sum(values.values())
    rows: list[dict[str, Any]] = []
    for source_id, label, source_key in _CONTEXT_SHARE_SOURCES:
        b = values[source_id]
        rows.append(
            {
                "source": label,
                "source_id": source_id,
                "source_key": source_key,
                "bytes": b,
                "share_pct": round((b / total) * 100, 2) if total else 0.0,
            }
        )
    return rows


def verify_packet_bytes(packet: dict[str, Any]) -> tuple[int | None, int, bool]:
    """(logged, recomputed, match). `logged` is edge.enforce_packet_budget's
    own `_edge.packet_bytes` figure; `recomputed` is a fresh
    edge.packet_byte_size call (inference body only — observability maps
    excluded). A mismatch means the packet was mutated after budget
    enforcement ran."""
    logged = (packet.get("_edge") or {}).get("packet_bytes")
    recomputed = packet_byte_size(packet)
    return logged, recomputed, (logged is None or logged == recomputed)


# ---------------------------------------------------------------------------
# Evidence pool + citation matching — spec §10, reusing the real validators.
# ---------------------------------------------------------------------------


def evidence_pool(packet: dict[str, Any]) -> set[str]:
    """This *is* validate._packet_evidence_pool — imported, not reimplemented."""
    return _packet_evidence_pool(packet)


def labeled_evidence_pool(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """The same fields _packet_evidence_pool folds into its set, kept with a
    source-key label for the evidence pool inspector panel. Field-for-field
    identical to _packet_evidence_pool's construction (facts, open_threads
    id/title, recent_turns user/answer, state_digest.goal) so the pool shown
    to a human is the pool citations are actually checked against."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(source_key: str, value: Any) -> None:
        s = str(value or "").strip().lower()
        if s and s not in seen:
            seen.add(s)
            out.append({"source_key": source_key, "value": s, "length": len(s)})

    for i, fact in enumerate(packet.get("facts") or []):
        add(f"facts[{i}]", fact)
    for i, t in enumerate(packet.get("open_threads") or []):
        if isinstance(t, dict):
            add(f"open_threads[{i}].id", t.get("id"))
            add(f"open_threads[{i}].title", t.get("title"))
        else:
            add(f"open_threads[{i}]", t)
    for i, turn in enumerate(packet.get("recent_turns") or []):
        if isinstance(turn, dict):
            add(f"recent_turns[{i}].user", turn.get("user"))
            add(f"recent_turns[{i}].answer", turn.get("answer"))
        else:
            add(f"recent_turns[{i}]", turn)
    digest = packet.get("state_digest") or {}
    if digest.get("goal"):
        add("state_digest.goal", digest["goal"])
    if digest.get("design_intent"):
        add("state_digest.design_intent", digest["design_intent"])
    return out


def _find_pool_match(s: str, labeled: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in labeled:
        if s in entry["value"]:
            return entry
    for entry in labeled:
        if entry["value"] in s and entry["length"] >= 12:
            return entry
    return None


def _first_word_diff(a: str, b: str) -> dict[str, Any] | None:
    wa, wb = a.split(), b.split()
    for i in range(max(len(wa), len(wb))):
        ca = wa[i] if i < len(wa) else "(ends)"
        cb = wb[i] if i < len(wb) else "(ends)"
        if ca != cb:
            return {"index": i, "cited": ca, "pool": cb}
    return None


def _explain_miss(s: str, labeled: list[dict[str, Any]]) -> dict[str, Any]:
    """Truncation first, then a genuine near-miss, else simply not present.

    spec §10: "check truncation first: if a pool entry ends in `…` and
    contains a ≥12-character prefix of the citation, the real cause is
    state._clip_text clipping the stored answer to 280 characters on write.
    Only show a word-level divergence when the nearest entry is genuinely
    near-identical (≥0.6 similarity). Otherwise say the citation simply is
    not in the packet."
    """
    for entry in labeled:
        pv = entry["value"]
        if not pv.endswith("…"):
            continue
        cut = 0
        limit = min(len(s), len(pv))
        for i in range(limit, 11, -1):
            if s[:i] in pv:
                cut = i
                break
        if cut >= 12:
            return {
                "kind": "truncated",
                "match": entry,
                "similarity": jaccard_similarity(s, pv),
                "reason": (
                    f"the first {cut} characters of this citation are in {entry['source_key']}, "
                    "then the stored copy ends in … — state._clip_text clipped that answer "
                    "to 280 chars when it was written to memory"
                ),
            }
    near: dict[str, Any] | None = None
    score = -1.0
    for entry in labeled:
        sc = jaccard_similarity(s, entry["value"])
        if sc > score:
            near, score = entry, sc
    if near is not None and score >= 0.6:
        diff = _first_word_diff(s, near["value"])
        reason = (
            f"first divergence at word {diff['index']}: cited “{diff['cited']}” vs "
            f"{near['source_key']} has “{diff['pool']}”"
            if diff
            else "near-identical but no word-level divergence found"
        )
        return {"kind": "near", "match": near, "similarity": score, "reason": reason}
    return {
        "kind": "unrelated",
        "match": near,
        "similarity": max(score, 0.0),
        "reason": "the closest pool entry is not near-identical — the citation is not in the packet",
    }


def citation_audit(packet: dict[str, Any], evidence_used: list[str]) -> list[dict[str, Any]]:
    """Per-citation MATCHED / TOO_SHORT / MISS.

    The pass/fail line is validate._evidence_ok itself, called once per
    citation so the 12-char floor and substring rule are never re-typed here
    — only the richer "which pool entry, and why a miss" detail is local.
    An empty evidence_used list produces no rows here; that case is its own
    check (`evidence_used_empty`), not a per-citation miss.
    """
    if not evidence_used:
        return []
    pool = _packet_evidence_pool(packet)
    labeled = labeled_evidence_pool(packet)
    rows: list[dict[str, Any]] = []
    for item in evidence_used:
        s = str(item).strip().lower()
        ok, bad = _evidence_ok([item], pool)
        if ok:
            match = _find_pool_match(s, labeled)
            rows.append(
                {
                    "citation": item,
                    "status": "MATCHED",
                    "match": match,
                    "reason": (
                        f"citation is a substring of {match['source_key']}"
                        if match
                        else "matches the packet evidence pool"
                    ),
                }
            )
            continue
        reason_token = bad[0] if bad else "evidence_not_in_packet"
        if reason_token.startswith("evidence_too_short"):
            rows.append(
                {
                    "citation": item,
                    "status": "TOO_SHORT",
                    "match": None,
                    "reason": "under the 12-character floor in _evidence_ok",
                }
            )
            continue
        rows.append({"citation": item, "status": "MISS", **_explain_miss(s, labeled)})
    return rows


# ---------------------------------------------------------------------------
# Per-check validation table — spec §7 stage 09 point 1 / acceptance
# criterion 8 ("every validation result is visible individually").
#
# Enumerates every check `validate_candidate` (return_path/validate.py) can
# produce, in its exact source order, reading only the pass's own real
# candidate / packet / receipt — never re-running generation, never
# asserting a status validate_candidate itself did not determine. A check is
# SKIP only when the same precondition validate_candidate's own `if` gate
# requires was false this pass (an acceptance-mode branch, an unset
# contract flag, an empty required list, or — for authoritative_obligation —
# no obligation resolved). PASS/FAIL are read directly off
# receipt["violations"] / receipt["advisories"], never re-derived with a
# second copy of validate.py's own threshold logic.
# ---------------------------------------------------------------------------


def _check_row(name: str, status: str, reason: str, examined: str, severity: str) -> dict[str, Any]:
    return {"name": name, "status": status, "reason": reason, "examined": examined, "severity": severity}


def _violation_fired(violations: list[str], name: str) -> bool:
    """True if `name` (bare) or `f"{name}:<detail>"` is present — validate.py
    appends either shape depending on the check (see validate_candidate)."""
    return any(str(v) == name or str(v).startswith(name + ":") for v in violations)


def _violations_matching(violations: list[str], prefix: str) -> list[str]:
    return [v for v in violations if str(v) == prefix or str(v).startswith(prefix + ":")]


def derive_checks(
    candidate: dict[str, Any],
    packet: dict[str, Any],
    receipt: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every check `validate_candidate` can produce for one pass, individually.

    `candidate` / `packet` / `receipt` must be the pass's own real, logged
    objects (see trace.py's per-pass assembly — the logged candidate already
    reflects any companion-mode evidence grounding validate_candidate itself
    applied, so `candidate.get("evidence_used")` here is exactly what
    `_evidence_ok` evaluated). This function only reads them; it never calls
    validate_candidate and never invents a status it cannot settle from
    receipt["violations"] / receipt["advisories"] / the authoritative_*
    fields pipeline.py records unconditionally.
    """
    rows: list[dict[str, Any]] = []
    violations = [str(v) for v in (receipt.get("violations") or [])]
    advisories = [str(v) for v in (receipt.get("advisories") or [])]
    contract = packet.get("acceptance_contract") or {}
    acceptance_mode = str(
        receipt.get("acceptance_mode") or contract.get("acceptance_mode") or "measurement"
    )
    companion = acceptance_mode == "companion"

    answer = str(candidate.get("answer") or "").strip()
    evidence_used = [str(e) for e in (candidate.get("evidence_used") or [])]
    user_input = str(packet.get("user_input") or "")
    goal = str((packet.get("state_digest") or {}).get("goal") or "").strip()
    design_intent = str(
        (packet.get("state_digest") or {}).get("design_intent") or ""
    ).strip()
    fallback = bool(candidate.get("authoritative_fallback"))
    next_state = candidate.get("next_state") if isinstance(candidate.get("next_state"), dict) else {}
    thread_touch = [str(t) for t in (next_state.get("thread_touch") or [])]

    # 1. parse_ok
    if _violation_fired(violations, "parse_failed"):
        hit = _violations_matching(violations, "parse_failed")[0]
        detail = hit.split(":", 1)[1] if ":" in hit else "unknown"
        rows.append(_check_row(
            "parse_ok", "FAIL", f"parse_candidate could not parse the raw text: {detail}",
            "candidate.parse_ok, candidate.parse_error", "violation",
        ))
    else:
        rows.append(_check_row(
            "parse_ok", "PASS", "did not fire — raw candidate text parsed as a JSON object",
            "candidate.parse_ok, candidate.parse_error", "violation",
        ))

    # 2. nonempty_answer (validate.py's violation string is "missing_answer")
    if "missing_answer" in violations:
        rows.append(_check_row(
            "nonempty_answer", "FAIL", "candidate.answer is empty after stripping whitespace",
            "candidate.answer", "violation",
        ))
    else:
        rows.append(_check_row(
            "nonempty_answer", "PASS", f"did not fire — answer is non-empty ({len(answer)} chars)",
            "candidate.answer", "violation",
        ))

    # 3. template_echo
    if "template_echo" in violations:
        matched = next(
            (m for m in TEMPLATE_ECHO_MARKERS if m.lower() in answer.lower() or m in answer), None
        )
        reason = (
            f"answer contains the instruction fragment “{matched}”"
            if matched else "answer matched one of TEMPLATE_ECHO_MARKERS"
        )
        rows.append(_check_row(
            "template_echo", "FAIL", reason,
            f"answer vs {len(TEMPLATE_ECHO_MARKERS)} TEMPLATE_ECHO_MARKERS fragments", "violation",
        ))
    else:
        rows.append(_check_row(
            "template_echo", "PASS",
            f"did not fire — none of {len(TEMPLATE_ECHO_MARKERS)} TEMPLATE_ECHO_MARKERS fragments found",
            "answer vs TEMPLATE_ECHO_MARKERS", "violation",
        ))

    # 4. template_echo_evidence
    if "template_echo_evidence" in violations:
        junk = {"STRING_FROM_FACTS", "(copy a fact)", "STRING"}
        matched = next((e for e in evidence_used if e in junk), None)
        reason = (
            f"evidence_used contains the placeholder “{matched}”"
            if matched else "evidence_used contains a repair-template placeholder"
        )
        rows.append(_check_row(
            "template_echo_evidence", "FAIL", reason,
            f"evidence_used, {len(evidence_used)} item(s)", "violation",
        ))
    else:
        reason = (
            f"did not fire — no placeholder token in {len(evidence_used)} evidence_used item(s)"
            if evidence_used else "did not fire — evidence_used is empty, nothing to check"
        )
        rows.append(_check_row(
            "template_echo_evidence", "PASS", reason,
            f"evidence_used, {len(evidence_used)} item(s)", "violation",
        ))

    # 5. goal_echo — gated on answer, goal, and not an authoritative fallback
    # (validate.py: "Substrate authoritative fallbacks intentionally restate
    # the goal claim").
    if not (answer and goal and not fallback):
        if fallback:
            reason = (
                "not applicable — this candidate is a substrate authoritative fallback, which "
                "intentionally restates the goal claim and is exempted by validate_candidate"
            )
        elif not goal:
            reason = "not applicable — state_digest.goal is empty for this turn"
        else:
            reason = "not applicable — answer is empty"
        rows.append(_check_row("goal_echo", "SKIP", reason, "answer vs state_digest.goal", "violation"))
    elif "goal_echo" in violations:
        rows.append(_check_row(
            "goal_echo", "FAIL", "answer is a near-copy of the goal (validate.is_goal_echo)",
            f"answer vs state_digest.goal ({len(goal)} chars)", "violation",
        ))
    else:
        rows.append(_check_row(
            "goal_echo", "PASS",
            "did not fire — token overlap with the goal is below validate.is_goal_echo's threshold",
            f"answer vs state_digest.goal ({len(goal)} chars)", "violation",
        ))

    # 5b. intent_echo — same anti-paste for the design-intent sentence
    if not (answer and design_intent and not fallback):
        if fallback:
            reason = (
                "not applicable — this candidate is a substrate authoritative fallback, "
                "which may restate the design-intent claim and is exempted by validate_candidate"
            )
        elif not design_intent:
            reason = "not applicable — state_digest.design_intent is empty for this turn"
        else:
            reason = "not applicable — answer is empty"
        rows.append(
            _check_row(
                "intent_echo",
                "SKIP",
                reason,
                "answer vs state_digest.design_intent",
                "violation",
            )
        )
    elif "intent_echo" in violations:
        rows.append(
            _check_row(
                "intent_echo",
                "FAIL",
                "answer is a near-copy of the design intent (validate.is_intent_echo)",
                f"answer vs state_digest.design_intent ({len(design_intent)} chars)",
                "violation",
            )
        )
    else:
        rows.append(
            _check_row(
                "intent_echo",
                "PASS",
                "did not fire — token overlap with design_intent is below "
                "validate.is_intent_echo's threshold",
                f"answer vs state_digest.design_intent ({len(design_intent)} chars)",
                "violation",
            )
        )

    # 6. not_responsive — hard reject in measurement mode, advisory-only in
    # companion mode (validate.py branches on `companion` when it fires).
    nr_severity = "advisory" if companion else "violation"
    if not (answer and user_input and not fallback):
        if fallback:
            reason = "not applicable — substrate authoritative fallback is already claim-checked and exempted"
        elif not user_input:
            reason = "not applicable — packet.user_input is empty"
        else:
            reason = "not applicable — answer is empty"
        rows.append(_check_row("not_responsive", "SKIP", reason, "answer vs packet.user_input", nr_severity))
    else:
        fired = ("not_responsive" in advisories) if companion else ("not_responsive" in violations)
        if fired:
            status = "ADVISORY" if companion else "FAIL"
            reason = "insufficient lexical engagement with packet.user_input (validate.is_responsive)"
        else:
            status = "PASS"
            reason = "did not fire — answer shares enough load-bearing tokens with packet.user_input"
        rows.append(_check_row("not_responsive", status, reason, "answer vs packet.user_input", nr_severity))

    # 7. stale_response_repeat — companion-only, gated on a prior accepted
    # answer existing and the user's prompt having changed (validate.py:
    # `if companion and answer and not fallback: prior = ...; if prior and
    # user_prompt_changed(...) and is_substantial_repeat(...): ...`).
    prior_answer = prior_accepted_answer(packet)
    prompt_changed = user_prompt_changed(packet, user_input)
    applicable = companion and bool(answer) and not fallback and bool(prior_answer) and prompt_changed
    if not applicable:
        if not companion:
            reason = "not applicable — stale_response_repeat only runs in companion mode"
        elif fallback:
            reason = "not applicable — substrate authoritative fallback is exempted"
        elif not answer:
            reason = "not applicable — answer is empty"
        elif not prior_answer:
            reason = "not applicable — recent_turns has no prior accepted answer to compare against"
        else:
            reason = (
                "not applicable — packet.user_input is unchanged from recent_turns[-1].user, so "
                "this check does not compare answers"
            )
        rows.append(_check_row(
            "stale_response_repeat", "SKIP", reason, "answer vs prior_accepted_answer(packet)", "violation"
        ))
    elif "stale_response_repeat" in violations:
        rows.append(_check_row(
            "stale_response_repeat", "FAIL",
            "validate.is_substantial_repeat matched this answer against recent_turns[-1]'s accepted answer",
            "answer vs recent_turns[-1].answer", "violation",
        ))
    else:
        rows.append(_check_row(
            "stale_response_repeat", "PASS",
            "did not fire — validate.is_substantial_repeat found this answer sufficiently different "
            "from recent_turns[-1]'s accepted answer",
            "answer vs recent_turns[-1].answer", "violation",
        ))

    # 8-10. required_section ×N — enumerated from the contract's own
    # configured list (default answer/evidence_used/next_state), in order.
    required_sections = contract.get("required_sections") or ["answer", "evidence_used", "next_state"]
    for section in required_sections:
        name = f"required_section:{section}"
        fired = name in violations
        if section == "answer":
            examined, ok_reason, bad_reason = "candidate.answer", "present", "missing or empty"
        elif section == "evidence_used":
            examined = "candidate.evidence_used"
            ok_reason, bad_reason = "present and a list", "missing or not a list"
        elif section == "next_state":
            examined = "candidate.next_state"
            ok_reason, bad_reason = "present and an object", "missing or not an object"
        else:
            examined = f"candidate.{section}"
            ok_reason, bad_reason = "present", f"{name} fired"
        rows.append(_check_row(
            name, "FAIL" if fired else "PASS",
            bad_reason if fired else f"did not fire — {ok_reason}",
            examined, "violation",
        ))

    # 11. max_words
    max_words = int((packet.get("constraints") or {}).get("max_words") or 180)
    word_count = int(
        receipt.get("word_count")
        if receipt.get("word_count") is not None
        else (len(answer.split()) if answer else 0)
    )
    if any(v.startswith("max_words_exceeded:") for v in violations):
        rows.append(_check_row(
            "max_words", "FAIL", f"{word_count} words exceeds max_words={max_words}",
            "len(answer.split())", "violation",
        ))
    else:
        rows.append(_check_row(
            "max_words", "PASS", f"did not fire — {word_count} words within max_words={max_words}",
            "len(answer.split())", "violation",
        ))

    # 12. evidence_used_empty
    evidence_source = str(receipt.get("evidence_source") or candidate.get("evidence_source") or "model")
    if "evidence_used_empty" in violations:
        rows.append(_check_row(
            "evidence_used_empty", "FAIL", "evidence_used is empty", "evidence_used", "violation",
        ))
    else:
        rows.append(_check_row(
            "evidence_used_empty", "PASS",
            f"did not fire — evidence_used has {len(evidence_used)} item(s), supplied by {evidence_source}",
            "evidence_used", "violation",
        ))

    # 13/14. evidence_too_short / evidence_not_in_packet — validate._evidence_ok
    # returns early (`["evidence_used_empty"]`) when evidence_used is empty,
    # so its per-item loop never ran this pass — genuinely not applicable.
    if not evidence_used:
        skip_reason = (
            "not applicable — evidence_used is empty, so validate._evidence_ok's per-item loop "
            "never ran (see evidence_used_empty)"
        )
        rows.append(_check_row("evidence_too_short", "SKIP", skip_reason, "evidence_used items", "violation"))
        rows.append(_check_row("evidence_not_in_packet", "SKIP", skip_reason, "evidence_used items", "violation"))
    else:
        too_short = _violations_matching(violations, "evidence_too_short")
        if too_short:
            detail = ", ".join(v.split(":", 1)[1] for v in too_short if ":" in v)
            rows.append(_check_row(
                "evidence_too_short", "FAIL",
                f"{len(too_short)} of {len(evidence_used)} item(s) under the 12-character floor: {detail}",
                "len(item) for each evidence_used entry", "violation",
            ))
        else:
            rows.append(_check_row(
                "evidence_too_short", "PASS",
                f"did not fire — all {len(evidence_used)} item(s) are at least 12 characters",
                "len(item) for each evidence_used entry", "violation",
            ))

        pool = evidence_pool(packet)
        not_in_packet = _violations_matching(violations, "evidence_not_in_packet")
        if not_in_packet:
            detail = ", ".join(v.split(":", 1)[1] for v in not_in_packet if ":" in v)
            rows.append(_check_row(
                "evidence_not_in_packet", "FAIL",
                f"{len(not_in_packet)} of {len(evidence_used)} citation(s) matched no packet "
                f"evidence-pool string: {detail}",
                f"evidence_used vs _packet_evidence_pool ({len(pool)} strings)", "violation",
            ))
        else:
            rows.append(_check_row(
                "evidence_not_in_packet", "PASS",
                f"did not fire — all {len(evidence_used)} citation(s) match a packet evidence-pool string",
                f"evidence_used vs _packet_evidence_pool ({len(pool)} strings)", "violation",
            ))

    # 15. goal_not_referenced — gated by acceptance_contract.must_reference_goal
    # (defaults to `not companion`) and a non-empty answer.
    must_goal = contract.get("must_reference_goal")
    if must_goal is None:
        must_goal = not companion
    if not (must_goal and answer):
        reason = (
            f"not applicable — acceptance_contract.must_reference_goal resolves False in "
            f"{acceptance_mode} mode"
            if not must_goal else "not applicable — answer is empty"
        )
        rows.append(_check_row(
            "goal_not_referenced", "SKIP", reason, "acceptance_contract.must_reference_goal", "violation"
        ))
    elif "goal_not_referenced" in violations:
        rows.append(_check_row(
            "goal_not_referenced", "FAIL",
            "answer does not carry enough load-bearing goal tokens (validate._goal_referenced)",
            "answer vs state_digest.goal tokens", "violation",
        ))
    else:
        rows.append(_check_row(
            "goal_not_referenced", "PASS",
            "did not fire — answer references the goal's load-bearing tokens",
            "answer vs state_digest.goal tokens", "violation",
        ))

    # 16. forbidden_content — always evaluated; constraints.forbidden may be
    # empty, in which case the check trivially passes (nothing configured).
    forbidden = (packet.get("constraints") or {}).get("forbidden") or []
    forbidden_hits = _violations_matching(violations, "forbidden")
    if forbidden_hits:
        detail = ", ".join(v.split(":", 1)[1] for v in forbidden_hits if ":" in v)
        rows.append(_check_row(
            "forbidden_content", "FAIL", f"answer contains forbidden term(s): {detail}",
            "answer vs constraints.forbidden", "violation",
        ))
    elif forbidden:
        rows.append(_check_row(
            "forbidden_content", "PASS",
            f"did not fire — none of {len(forbidden)} constraints.forbidden term(s) appear in the answer",
            "answer vs constraints.forbidden", "violation",
        ))
    else:
        rows.append(_check_row(
            "forbidden_content", "PASS",
            "did not fire — constraints.forbidden is empty, nothing configured to match",
            "answer vs constraints.forbidden", "violation",
        ))

    # 17. contradicts_facts — gated by acceptance_contract.must_not_contradict_facts
    # (defaults False; the check never runs unless a contract turns it on).
    must_not_contradict = bool(contract.get("must_not_contradict_facts", False))
    if not must_not_contradict:
        rows.append(_check_row(
            "contradicts_facts", "SKIP",
            "not applicable — acceptance_contract.must_not_contradict_facts is not set to true",
            "acceptance_contract.must_not_contradict_facts", "violation",
        ))
    else:
        contra_hits = _violations_matching(violations, "contradicts_facts")
        if contra_hits:
            detail = ", ".join(v.split(":", 1)[1] for v in contra_hits if ":" in v)
            rows.append(_check_row(
                "contradicts_facts", "FAIL",
                f"answer clause(s) assert a capability the facts forbid: {detail}",
                "answer clauses vs packet.facts contradiction rules", "violation",
            ))
        else:
            rows.append(_check_row(
                "contradicts_facts", "PASS",
                "did not fire — no answer clause asserts a capability the packet facts forbid",
                "answer clauses vs packet.facts contradiction rules", "violation",
            ))

    # 18. unknown_thread_touch — always evaluated; an empty thread_touch list
    # has nothing declared to check.
    if not thread_touch:
        rows.append(_check_row(
            "unknown_thread_touch", "SKIP",
            "not applicable — next_state.thread_touch is empty, nothing declared to check",
            "next_state.thread_touch", "violation",
        ))
    else:
        touch_hits = _violations_matching(violations, "unknown_thread_touch")
        if touch_hits:
            detail = ", ".join(v.split(":", 1)[1] for v in touch_hits if ":" in v)
            rows.append(_check_row(
                "unknown_thread_touch", "FAIL",
                f"{len(touch_hits)} of {len(thread_touch)} declared id(s) matched no known open_thread: "
                f"{detail}",
                ", ".join(thread_touch), "violation",
            ))
        else:
            rows.append(_check_row(
                "unknown_thread_touch", "PASS",
                f"did not fire — all {len(thread_touch)} declared id(s) matched a known open_thread",
                ", ".join(thread_touch), "violation",
            ))

    # 19. authoritative_obligation — only meaningful when authoritative_state
    # resolved an obligation for this turn (companion mode + a narrow state
    # question, authoritative_state.classify_state_question). This check runs
    # *before* validate_candidate in pipeline.py
    # (authoritative_state.check_obligation via enforce_authoritative_candidate),
    # so its status/reason come from the receipt's own authoritative_* fields
    # — set unconditionally by pipeline.py whenever an obligation was
    # resolved — never from receipt["violations"]/["advisories"].
    kind = receipt.get("authoritative_kind")
    if kind is None:
        rows.append(_check_row(
            "authoritative_obligation", "SKIP",
            "not applicable — authoritative_state.resolve_obligation did not resolve an obligation "
            "for this turn (or acceptance_mode is not companion)",
            "receipt.authoritative_kind", "authoritative (outside validate.py)",
        ))
    else:
        auth_fallback = bool(receipt.get("authoritative_fallback"))
        auth_reasons = [str(r) for r in (receipt.get("authoritative_reasons") or [])]
        if auth_fallback:
            detail = ", ".join(auth_reasons) if auth_reasons else "no reason recorded"
            rows.append(_check_row(
                "authoritative_obligation", "FAIL",
                f"obligation kind '{kind}' resolved; authoritative_state.check_obligation rejected "
                f"the model's candidate ({detail}) and the substrate substituted its own fallback answer",
                "answer vs StateObligation.required_substrings/forbidden_substrings",
                "authoritative (outside validate.py)",
            ))
        else:
            rows.append(_check_row(
                "authoritative_obligation", "PASS",
                f"did not fire — obligation kind '{kind}' resolved and the model's candidate preserved "
                "the required claims, so no substrate fallback was substituted",
                "answer vs StateObligation.required_substrings/forbidden_substrings",
                "authoritative (outside validate.py)",
            ))

    return rows


# ---------------------------------------------------------------------------
# Memory repetition — spec §10: needs two or more stored entries; byte share
# alone cannot measure it (one entry always holds ~100% of the list).
# ---------------------------------------------------------------------------


def memory_repetition(recent_turns: list[dict[str, Any]], *, threshold: float = 0.6) -> dict[str, Any]:
    answers = [str(t.get("answer") or "") for t in recent_turns if isinstance(t, dict)]
    best_score, best_i, best_j = 0.0, -1, -1
    for i in range(len(answers)):
        for j in range(i + 1, len(answers)):
            score = jaccard_similarity(answers[i], answers[j])
            if score > best_score:
                best_score, best_i, best_j = score, i, j
    return {
        "pairwise_max": best_score,
        "pair": (best_i, best_j) if best_i >= 0 else None,
        "threshold": threshold,
        "detected": len(answers) >= 2 and best_score >= threshold,
        "entries": len(answers),
    }


# ---------------------------------------------------------------------------
# Attractor clustering — spec §10: cluster at ≥0.6 Jaccard; a stored answer
# is "carried" at ≥0.5 because state._clip_text truncates it on write.
# ---------------------------------------------------------------------------


def cluster_candidates(
    candidates: list[dict[str, Any]], *, cluster_threshold: float = 0.6
) -> dict[str, Any]:
    """Group candidates (each a dict with a "text" key) by symmetric Jaccard.
    Returns the single largest cluster — the session's "recurring answer"."""
    best: dict[str, Any] | None = None
    for seed in candidates:
        members = [
            c
            for c in candidates
            if jaccard_similarity(seed.get("text", ""), c.get("text", "")) >= cluster_threshold
        ]
        if best is None or len(members) > len(best["members"]):
            best = {"seed": seed, "members": members}
    if best is None:
        return {"total": 0, "seed": None, "members": [], "threshold": cluster_threshold}
    return {
        "total": len(candidates),
        "seed": best["seed"],
        "members": best["members"],
        "threshold": cluster_threshold,
    }


def stored_answer_carried(
    recurring_text: str, recent_turns: list[dict[str, Any]], *, threshold: float = 0.5
) -> bool:
    for t in recent_turns:
        if isinstance(t, dict) and jaccard_similarity(recurring_text, str(t.get("answer") or "")) >= threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Stage status + ◇ flag derivation — spec §6.
# ---------------------------------------------------------------------------

_StageStatus = str  # "waiting"|"active"|"completed"|"warning"|"rejected"|"repaired"|"skipped"

# (index, name, target) — target is the real function/class each stage's
# panel attributes as "source of truth", used only to resolve path:line at
# runtime (never hardcoded — spec §6: "regenerate them at runtime ... rather
# than hardcoding drifted values").
_STAGE_TARGETS: tuple[tuple[int, str, Callable[..., Any] | type], ...] = (
    (1, "input", None),  # resolved specially — see stage_defs()
    (2, "state_load", SubstrateState.load),
    (3, "recent_memory", fit_recent_turns),
    (4, "packet_compile", None),  # compile.build_arrival_packet — see stage_defs()
    (5, "edge_budget", _enforce_packet_budget),
    (6, "kernel_request", OllamaClient.run),
    (7, "raw_output", InferenceResult),
    (8, "parse", parse_candidate),
    (9, "validate", validate_candidate),
    (10, "repair", build_repair_plan),
    (11, "decision", assess),
    (12, "persist", accept_candidate),
)


def _source_location(obj: Any) -> tuple[str, int]:
    """Resolve `path:line` for a function/class at runtime. Never hardcoded,
    so a stage panel never claims a line number the current checkout has
    already moved past."""
    try:
        file = inspect.getsourcefile(obj) or inspect.getfile(obj)
        _, line = inspect.getsourcelines(obj)
        rel = str(Path(file).resolve().relative_to(repo_root()))
        return rel, line
    except (TypeError, OSError, ValueError):
        return "unknown", 0


def stage_defs() -> list[dict[str, Any]]:
    """The 12 stages with runtime-resolved source locations (spec §6 table).

    Stage 01 (INPUT) and 04 (PACKET COMPILE) are resolved from imports done
    lazily here to avoid a module-load-time dependency on conditioned_kernel
    ``cli`` from this module's top level.
    """
    from conditioned_kernel.cli import _cmd_chat
    from conditioned_kernel.compile import build_arrival_packet

    resolved: list[tuple[int, str, Any]] = []
    for index, name, target in _STAGE_TARGETS:
        if index == 1:
            target = _cmd_chat
        elif index == 4:
            target = build_arrival_packet
        resolved.append((index, name, target))

    out: list[dict[str, Any]] = []
    for index, name, target in resolved:
        path, line = _source_location(target)
        qualname = getattr(target, "__qualname__", getattr(target, "__name__", str(target)))
        out.append(
            {
                "index": index,
                "name": name,
                "source_module": path,
                "source_function": qualname,
                "source_line": line,
            }
        )
    return out


def derive_stage_status(
    index: int,
    *,
    final_violations: list[str],
    final_advisories: list[str],
    pass_count: int,
    final_decision: str,
    applied_updates: list[str],
) -> _StageStatus:
    """spec §6: "Status derivation: stages 01–08 completed on a finished
    turn; 09 = bad if violations, warn if advisories only, else ok; 10 = fix
    if more than one pass else skip; 11 = fix if repaired-and-accepted, ok if
    accepted first pass, bad if rejected; 12 = ok if anything was applied,
    warn if only logs were written." bad→rejected, ok→completed, warn→
    warning, fix→repaired, skip→skipped (spec §6 status vocabulary)."""
    if 1 <= index <= 8:
        return "completed"
    if index == 9:
        if final_violations:
            return "rejected"
        if final_advisories:
            return "warning"
        return "completed"
    if index == 10:
        return "repaired" if pass_count > 1 else "skipped"
    if index == 11:
        if final_decision == "accept":
            return "repaired" if pass_count > 1 else "completed"
        return "rejected"
    if index == 12:
        return "completed" if applied_updates else "warning"
    raise ValueError(f"unknown stage index: {index}")


def derive_stage_flag(
    index: int,
    *,
    memory_repetition_detected: bool,
    user_share_pct: float,
    budget_dropped_facts: bool,
    final_violations: list[str],
    final_advisories: list[str],
    final_decision: str,
) -> bool:
    """spec §6: "◇ flag appears on 03 when memory repetition is detected, 04
    when the user's share is under 3%, 05 when the budget dropped facts, 09
    on any violation or advisory, 11 on rejection." """
    if index == 3:
        return memory_repetition_detected
    if index == 4:
        return user_share_pct < 3.0
    if index == 5:
        return budget_dropped_facts
    if index == 9:
        return bool(final_violations) or bool(final_advisories)
    if index == 11:
        return final_decision != "accept"
    return False


# ---------------------------------------------------------------------------
# Decision label — spec §7 stage 11 vocabulary.
# ---------------------------------------------------------------------------


def derive_decision_label(decision: str | None, *, pass_count: int, execution_status: str | None) -> str:
    if decision == "accept":
        return "REPAIRED AND ACCEPTED" if pass_count > 1 else "ACCEPTED"
    if decision == "reject":
        return "REJECTED"
    if decision == "error":
        if execution_status in ("timeout", "transport_error"):
            return "TRANSPORT ERROR"
        return "GENERATION ERROR"
    return str(decision or "unknown").upper()


# ---------------------------------------------------------------------------
# Observation derivation — spec §5, in the order the README states.
# ---------------------------------------------------------------------------


def derive_observations(
    *,
    context_share_rows: list[dict[str, Any]],
    user_input_bytes: int,
    stale_response_repeat: bool,
    budget_dropped_facts: list[str],
    memory_rep: dict[str, Any],
    carried_forward_pct: float,
    total_model_input_bytes: int,
) -> list[dict[str, str]]:
    """Pinned observation banners, computed in spec §5's stated order:
    substrate-dominated input, stale-response attractor, budget-dropped
    state, high recent-context repetition, prior answer carried forward.
    Each entry appears only when its own condition is met. The caller (a
    UI layer) pins at most two plus a "+N more" row; this function does not
    truncate."""
    out: list[dict[str, str]] = []

    by_id = {r["source_id"]: r for r in context_share_rows}
    user_row = by_id.get("current_user_input")
    if user_row is not None and user_row.get("share_pct", 0) < 3:
        durable = by_id.get("durable_state")
        system_row = by_id.get("system_instructions")
        combined = (durable["share_pct"] if durable else 0) + (system_row["share_pct"] if system_row else 0)
        out.append(
            {
                "label": "Substrate dominated input",
                "detail": (
                    f"Your {user_input_bytes} bytes of text became a {user_row['bytes']}-byte "
                    f"user_input field — {user_row['share_pct']:.2f}% of the "
                    f"{total_model_input_bytes} bytes that reached the kernel. Durable state and "
                    f"system instructions together are {combined:.1f}%."
                ),
            }
        )

    if stale_response_repeat:
        out.append(
            {
                "label": "Stale-response attractor",
                "detail": (
                    "validate.is_substantial_repeat matched the candidate against "
                    "recent_turns[-1] and rejected it as the same linguistic groove."
                ),
            }
        )

    if budget_dropped_facts:
        out.append(
            {
                "label": "Budget dropped state",
                "detail": (
                    f"{len(budget_dropped_facts)} of the packet's fact slots were cut by "
                    "edge.enforce_packet_budget: " + " · ".join(budget_dropped_facts)
                ),
            }
        )

    if memory_rep.get("detected"):
        i, j = memory_rep["pair"]
        out.append(
            {
                "label": "High recent-context repetition",
                "detail": (
                    f"recent_turns[{i}] and recent_turns[{j}] share "
                    f"{round(memory_rep['pairwise_max'] * 100)}% of their tokens — dialogue "
                    "memory is holding the same language twice. Descriptive only; no "
                    "validation rule measures this."
                ),
            }
        )

    if carried_forward_pct >= 0.6 and not stale_response_repeat:
        out.append(
            {
                "label": "Prior answer carried forward",
                "detail": (
                    f"{round(carried_forward_pct * 100)}% of a prior stored answer's tokens "
                    "reappear in this candidate, but recent_turns[-1] is a different turn — so "
                    "validate.prior_accepted_answer never compared them and "
                    "stale_response_repeat did not fire."
                ),
            }
        )

    return out


def derive_advisory_observation(advisories: list[str]) -> dict[str, str] | None:
    """Panel-only observation — spec §5: "never pinned." Callers append this
    after `derive_observations`'s pinned-eligible list, never mix it in."""
    if not advisories:
        return None
    return {
        "label": "Advisory not enforced",
        "detail": (
            ", ".join(advisories)
            + " — in companion mode this is recorded and ignored. In measurement mode the "
            "same finding is a hard reject."
        ),
    }


__all__ = [
    "tokenize",
    "jaccard_similarity",
    "bytes_len",
    "context_share_bytes",
    "verify_packet_bytes",
    "evidence_pool",
    "labeled_evidence_pool",
    "citation_audit",
    "derive_checks",
    "memory_repetition",
    "cluster_candidates",
    "stored_answer_carried",
    "stage_defs",
    "derive_stage_status",
    "derive_stage_flag",
    "derive_decision_label",
    "derive_observations",
    "derive_advisory_observation",
    "TEMPLATE_ECHO_MARKERS",
]
