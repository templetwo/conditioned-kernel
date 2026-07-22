"""Unified scoring for all experiment conditions (post M1 audit).

One function path for bare / budget_matched / ck_strict.
No hardcoded accept=False for controls.
Does not use model self-reported confidence.
"""

from __future__ import annotations

import re
from typing import Any

from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import (
    is_goal_echo,
    is_responsive,
    validate_candidate,
)


def probe_key_hits(answer: str, probe: dict[str, Any] | None) -> dict[str, Any]:
    """Score against per-probe answer keys (mechanical)."""
    if not probe:
        return {
            "key_ok": True,
            "key_score": 1.0,
            "key_violations": [],
            "has_answer_key": False,
        }
    key = probe.get("answer_key") or {}
    if not key:
        return {
            "key_ok": True,
            "key_score": 1.0,
            "key_violations": [],
            "has_answer_key": False,
        }

    al = (answer or "").lower()
    viol: list[str] = []

    must_any = key.get("must_mention_any") or []
    # list of groups: each group is a list of alternatives; all groups must hit
    if must_any and isinstance(must_any[0], str):
        # flat list → one group
        must_any = [must_any]
    for i, group in enumerate(must_any):
        if not any(str(x).lower() in al for x in group):
            viol.append(f"missing_must_mention_group_{i}")

    must_not = key.get("must_not_mention_any") or []
    for x in must_not:
        if str(x).lower() in al:
            viol.append(f"forbidden_mention:{x}")

    min_words = int(key.get("min_words") or 0)
    if min_words and len((answer or "").split()) < min_words:
        viol.append(f"too_short:{min_words}")

    ok = len(viol) == 0
    return {
        "key_ok": ok,
        "key_score": 1.0 if ok else 0.0,
        "key_violations": viol,
        "has_answer_key": True,
    }


def score_output(
    raw_text: str,
    *,
    packet: dict[str, Any],
    probe: dict[str, Any] | None = None,
    passes: list[dict[str, Any]] | None = None,
    decision: str | None = None,
) -> dict[str, Any]:
    """Score one model output under a shared packet + optional probe key.

    Applied identically whether the row came from bare, budget_matched, or ck.
    """
    raw_text = raw_text or ""
    candidate = parse_candidate(raw_text, packet_id=str(packet.get("packet_id") or "score"))
    # If free text without JSON, still hold answer as the raw text for content metrics
    if not candidate.get("parse_ok") and raw_text.strip():
        candidate = dict(candidate)
        candidate["answer"] = raw_text.strip()
        candidate["evidence_used"] = candidate.get("evidence_used") or []
        candidate["next_state"] = candidate.get("next_state") or {}

    receipt = validate_candidate(candidate, packet)
    answer = str(candidate.get("answer") or "").strip()
    goal = str((packet.get("state_digest") or {}).get("goal") or "")
    user_input = str(packet.get("user_input") or (probe or {}).get("prompt") or "")

    parse_ok = bool(candidate.get("parse_ok"))
    schema_ok = bool(receipt.get("valid_schema")) and parse_ok
    # Only count full schema if required sections present after parse
    if parse_ok:
        schema_ok = (
            bool(answer)
            and isinstance(candidate.get("evidence_used"), list)
            and isinstance(candidate.get("next_state"), dict)
            and bool(receipt.get("valid_schema"))
        )

    state_faithful = bool(receipt.get("state_faithful"))
    goal_echo = bool(goal and is_goal_echo(answer, goal))
    responsive = bool(user_input and is_responsive(answer, user_input))
    goal_ref = "goal_not_referenced" not in (receipt.get("violations") or []) and not goal_echo

    keys = probe_key_hits(answer, probe)

    # Accept: validator clean AND probe key ok (when key exists)
    validator_accept = (
        bool(receipt.get("valid_schema"))
        and bool(receipt.get("state_faithful"))
        and not (receipt.get("violations") or [])
    )
    accept = validator_accept and keys["key_ok"]

    # Optional external decision (CK pipeline) — still require key_ok for accept metric
    if decision is not None:
        accept = (decision == "accept") and keys["key_ok"] and not goal_echo

    n_pass = max(1, len(passes or []))
    first_viol = list((passes or [{}])[0].get("violations") or []) if passes else list(
        receipt.get("violations") or []
    )
    repaired = bool(passes) and n_pass > 1 and accept
    rescue = repaired

    # Structural: parse, schema, accept, not goal_echo — each once
    structural = (
        (1.0 if parse_ok else 0.0)
        + (1.0 if schema_ok else 0.0)
        + (1.0 if accept else 0.0)
        + (1.0 if (answer and not goal_echo) else 0.0)
    ) / 4.0

    # Semantic: responsive + key + state_faithful + not goal_echo
    semantic = (
        (1.0 if responsive else 0.0)
        + (1.0 if keys["key_score"] else 0.0)
        + (1.0 if state_faithful and not goal_echo else 0.0)
        + (1.0 if goal_ref else 0.0)
    ) / 4.0

    return {
        "parse_ok": parse_ok,
        "schema_ok": schema_ok,
        "state_faithful": state_faithful,
        "accept": accept,
        "goal_referenced": goal_ref,
        "goal_echo": goal_echo,
        "responsive": responsive,
        "key_ok": keys["key_ok"],
        "key_score": keys["key_score"],
        "key_violations": keys["key_violations"],
        "word_count": receipt.get("word_count") or len(answer.split()),
        "repaired": repaired,
        "rescue": rescue,
        "passes": n_pass,
        "violations": list(receipt.get("violations") or []),
        "first_pass_violations": first_viol,
        "structural_score": structural,
        "semantic_score": semantic,
        "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
        "answer": answer[:500],
    }


# Back-compat wrappers (delegate to unified scorer)


def score_free_text(
    text: str,
    *,
    goal: str,
    facts: list[str] | None = None,
    max_words: int = 120,
    user_input: str = "",
    probe: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = packet or {
        "packet_id": "score_free",
        "user_input": user_input or (probe or {}).get("prompt") or "",
        "state_digest": {"goal": goal},
        "facts": facts or [],
        "open_threads": [],
        "constraints": {"max_words": max_words, "forbidden": []},
        "acceptance_contract": {
            "required_sections": ["answer", "evidence_used", "next_state"],
            "must_reference_goal": True,
            "must_not_contradict_facts": True,
            "evidence_must_be_from_packet": True,
        },
    }
    if user_input and not pkt.get("user_input"):
        pkt = dict(pkt)
        pkt["user_input"] = user_input
    return score_output(text, packet=pkt, probe=probe)


def score_ck_result(
    *,
    ok: bool,
    decision: str,
    answer: str,
    packet: dict[str, Any],
    candidate: dict[str, Any],
    receipt: dict[str, Any],
    passes: list[dict[str, Any]] | None = None,
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = answer
    if candidate.get("raw_text"):
        raw = str(candidate.get("raw_text"))
    elif candidate.get("parse_ok"):
        import json

        raw = json.dumps(
            {
                "answer": candidate.get("answer"),
                "evidence_used": candidate.get("evidence_used"),
                "next_state": candidate.get("next_state"),
            }
        )
    return score_output(
        raw,
        packet=packet,
        probe=probe,
        passes=passes,
        decision=decision if ok or decision else decision,
    )


def score_ck_raw_against_packet(
    raw: str,
    packet: dict[str, Any],
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return score_output(raw, packet=packet, probe=probe)


def row_is_valid_measurement(row: dict[str, Any]) -> bool:
    """A row counts only if the model's answer was actually observed.

    A timeout is not a score of zero. Zero means the model completed and
    earned nothing; a timeout means no measurement exists. Averaging them
    together destroys the estimand -- Qwen3.5 timed out on every row and still
    produced a headline of +0.125, built from rows that never saw an output.
    """
    if row.get("error"):
        return False
    if row.get("decision") == "error":
        return False
    return True


def aggregate_condition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "valid_n": 0, "invalid_n": 0, "valid": False}

    invalid = [r for r in rows if not row_is_valid_measurement(r)]
    rows_all, rows = rows, [r for r in rows if row_is_valid_measurement(r)]
    if not rows:
        reasons = sorted(
            {str(r.get("error") or r.get("decision") or "unknown")[:80] for r in invalid}
        )
        return {
            "n": len(rows_all),
            "valid_n": 0,
            "invalid_n": len(invalid),
            "valid": False,
            "failure_reasons": reasons,
        }
    keys = (
        "structural_score",
        "semantic_score",
        "parse_ok",
        "schema_ok",
        "accept",
        "goal_referenced",
        "goal_echo",
        "responsive",
        "key_ok",
        "repaired",
        "rescue",
    )
    out: dict[str, Any] = {
        "n": len(rows_all),
        "valid_n": len(rows),
        "invalid_n": len(invalid),
        "valid": True,
    }
    if invalid:
        out["failure_reasons"] = sorted(
            {str(r.get("error") or r.get("decision") or "unknown")[:80] for r in invalid}
        )
    for k in keys:
        vals = [r["scores"].get(k) for r in rows if "scores" in r and k in r["scores"]]
        if not vals:
            continue
        if isinstance(vals[0], bool):
            out[k] = sum(1 for v in vals if v) / len(vals)
        else:
            out[k] = sum(float(v) for v in vals) / len(vals)
    # Distinct answers (anti-degeneracy signal)
    answers = [str((r.get("scores") or {}).get("answer") or r.get("raw") or "") for r in rows]
    uniq = {re.sub(r"\s+", " ", a.strip().lower()) for a in answers if a.strip()}
    out["distinct_answers"] = len(uniq)
    return out


def substrate_gain(ck_agg: dict[str, Any], control_agg: dict[str, Any]) -> dict[str, Any]:
    """Delta CK − control. Prefer budget_matched as headline control.

    Fails closed. If either side has no valid measurements, no composite is
    emitted: `composite` is None and `valid` is False. A missing measurement
    must never be reported as a gain of zero -- Qwen3.5 timed out on every row
    and still produced +0.125 before this guard existed.
    """
    for name, agg in (("ck", ck_agg), ("control", control_agg)):
        if agg.get("valid") is False or agg.get("valid_n") == 0:
            return {
                "composite": None,
                "valid": False,
                "failure_reason": f"{name} has no valid measurements",
                "failure_detail": agg.get("failure_reasons"),
                "ck_valid_n": ck_agg.get("valid_n"),
                "control_valid_n": control_agg.get("valid_n"),
            }

    def g(key: str) -> float:
        return float(ck_agg.get(key) or 0.0) - float(control_agg.get(key) or 0.0)

    return {
        "valid": True,
        "delta_structural": g("structural_score"),
        "delta_semantic": g("semantic_score"),
        "delta_parse_ok": g("parse_ok"),
        "delta_accept": g("accept"),
        "delta_responsive": g("responsive"),
        "delta_key_ok": g("key_ok"),
        "delta_goal_referenced": g("goal_referenced"),
        "composite": (g("structural_score") + g("semantic_score")) / 2.0,
    }
