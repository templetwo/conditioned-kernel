"""Deterministic scoring for bare vs conditioned-kernel conditions.

Splits structural recovery from semantic (closed-set) faithfulness.
Does not use model self-reported confidence.
"""

from __future__ import annotations

import re
from typing import Any

from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.validate import validate_candidate


def score_free_text(
    text: str,
    *,
    goal: str,
    facts: list[str] | None = None,
    max_words: int = 120,
) -> dict[str, Any]:
    """Score a bare / non-schema response with mechanical proxies."""
    text = (text or "").strip()
    words = len(text.split()) if text else 0
    goal_l = goal.lower()
    ans_l = text.lower()
    goal_tokens = [
        w
        for w in re.findall(r"[a-z0-9]{5,}", goal_l)
        if w not in {"about", "under", "their", "would", "could", "should"}
    ]
    goal_hits = sum(1 for t in goal_tokens if t in ans_l)
    goal_ref = goal_hits >= min(2, max(1, len(goal_tokens) // 5)) if goal_tokens else False

    fact_hits = 0
    for f in facts or []:
        # token overlap with fact
        ft = [w for w in re.findall(r"[a-z0-9]{5,}", f.lower())]
        if ft and sum(1 for t in ft if t in ans_l) >= min(2, len(ft)):
            fact_hits += 1

    # Try opportunistic JSON parse (bare models sometimes emit JSON)
    cand = parse_candidate(text, packet_id="score_bare")
    parse_ok = bool(cand.get("parse_ok"))

    return {
        "parse_ok": parse_ok,
        "schema_ok": False,  # bare is not under schema contract
        "accept": False,
        "goal_referenced": goal_ref,
        "fact_overlap_count": fact_hits,
        "word_count": words,
        "within_word_budget": words <= max_words if words else False,
        "has_content": bool(text),
        "repaired": False,
        "passes": 1,
        "structural_score": (1.0 if parse_ok else 0.0) * 0.25
        + (1.0 if text else 0.0) * 0.25
        + (1.0 if words and words <= max_words else 0.0) * 0.25
        + (1.0 if goal_ref else 0.0) * 0.25,
        "semantic_score": (1.0 if goal_ref else 0.0) * 0.6
        + min(1.0, fact_hits / 2.0) * 0.4,
    }


def score_ck_result(
    *,
    ok: bool,
    decision: str,
    answer: str,
    packet: dict[str, Any],
    candidate: dict[str, Any],
    receipt: dict[str, Any],
    passes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score a Conditioned Kernel turn from receipts (ground truth for structure)."""
    passes = passes or []
    n_pass = max(1, len(passes))
    first_viol = (passes[0].get("violations") if passes else []) or []
    repaired = n_pass > 1 and decision == "accept"
    rescue = repaired  # first failed, later accepted

    valid_schema = bool(receipt.get("valid_schema")) if receipt else False
    state_faithful = bool(receipt.get("state_faithful")) if receipt else False
    parse_ok = bool(candidate.get("parse_ok")) if candidate else False

    structural = (
        (1.0 if parse_ok else 0.0)
        + (1.0 if valid_schema else 0.0)
        + (1.0 if decision == "accept" else 0.0)
        + (1.0 if (not first_viol or rescue or decision == "accept") else 0.0)
    ) / 4.0

    semantic = (
        (1.0 if state_faithful else 0.0)
        + (1.0 if decision == "accept" else 0.0)
    ) / 2.0

    return {
        "parse_ok": parse_ok,
        "schema_ok": valid_schema,
        "state_faithful": state_faithful,
        "accept": decision == "accept" and ok,
        "goal_referenced": "goal_not_referenced" not in (receipt.get("violations") or []),
        "word_count": receipt.get("word_count") or len((answer or "").split()),
        "repaired": repaired,
        "rescue": rescue,
        "passes": n_pass,
        "violations": list(receipt.get("violations") or []),
        "first_pass_violations": list(first_viol),
        "structural_score": structural,
        "semantic_score": semantic,
        "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
    }


def score_ck_raw_against_packet(raw: str, packet: dict[str, Any]) -> dict[str, Any]:
    """Score raw model text as if validated once (no repair loop)."""
    cand = parse_candidate(raw, packet_id=str(packet.get("packet_id") or "x"))
    receipt = validate_candidate(cand, packet)
    ok = bool(receipt.get("valid_schema")) and bool(receipt.get("state_faithful")) and not receipt.get(
        "violations"
    )
    return score_ck_result(
        ok=ok,
        decision="accept" if ok else "reject",
        answer=str(cand.get("answer") or ""),
        packet=packet,
        candidate=cand,
        receipt=receipt,
        passes=[{"violations": receipt.get("violations") or []}],
    )


def aggregate_condition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean scores across probe rows for one condition."""
    if not rows:
        return {"n": 0}
    keys = ("structural_score", "semantic_score", "parse_ok", "accept", "goal_referenced", "repaired", "rescue")
    out: dict[str, Any] = {"n": len(rows)}
    for k in keys:
        vals = [r["scores"].get(k) for r in rows if "scores" in r and k in r["scores"]]
        if not vals:
            continue
        if isinstance(vals[0], bool):
            out[k] = sum(1 for v in vals if v) / len(vals)
        else:
            out[k] = sum(float(v) for v in vals) / len(vals)
    return out


def substrate_gain(ck_agg: dict[str, Any], bare_agg: dict[str, Any]) -> dict[str, float]:
    """Delta CK − bare on normalized scores (positive = substrate helped)."""

    def g(key: str) -> float:
        return float(ck_agg.get(key) or 0.0) - float(bare_agg.get(key) or 0.0)

    return {
        "delta_structural": g("structural_score"),
        "delta_semantic": g("semantic_score"),
        "delta_parse_ok": g("parse_ok"),
        "delta_accept": g("accept"),
        "delta_goal_referenced": g("goal_referenced"),
        "composite": (g("structural_score") + g("semantic_score")) / 2.0,
    }
