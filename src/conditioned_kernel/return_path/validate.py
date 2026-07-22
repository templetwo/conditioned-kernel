"""Deterministic validation against the arrival packet contract.

v0 faithfulness is closed-set and mechanical — not open NLI.
"""

from __future__ import annotations

import re
from typing import Any

from conditioned_kernel.ids import receipt_id, utc_now_iso


def _packet_evidence_pool(packet: dict[str, Any]) -> set[str]:
    pool: set[str] = set()
    for fact in packet.get("facts") or []:
        pool.add(str(fact).strip().lower())
    for t in packet.get("open_threads") or []:
        if isinstance(t, dict):
            if t.get("id"):
                pool.add(str(t["id"]).strip().lower())
            if t.get("title"):
                pool.add(str(t["title"]).strip().lower())
        else:
            pool.add(str(t).strip().lower())
    digest = packet.get("state_digest") or {}
    if digest.get("goal"):
        pool.add(str(digest["goal"]).strip().lower())
    return {p for p in pool if p}


def _goal_referenced(answer: str, packet: dict[str, Any]) -> bool:
    goal = str((packet.get("state_digest") or {}).get("goal") or "").strip()
    if not goal:
        return True
    answer_l = answer.lower()
    # Token overlap on significant words
    tokens = [w for w in re.findall(r"[a-z0-9]{4,}", goal.lower()) if w not in {"with", "from", "that", "this"}]
    if not tokens:
        return "goal" in answer_l
    hits = sum(1 for t in tokens if t in answer_l)
    return hits >= max(1, min(3, len(tokens) // 4)) or "goal" in answer_l


def _evidence_ok(evidence: list[str], pool: set[str]) -> tuple[bool, list[str]]:
    if not evidence:
        return False, ["evidence_used_empty"]
    bad: list[str] = []
    for item in evidence:
        s = item.strip().lower()
        if not s:
            bad.append("empty_evidence_item")
            continue
        # Allow substring match either direction (model may truncate)
        if not any(s in p or p in s for p in pool):
            bad.append(f"evidence_not_in_packet:{item[:80]}")
    return len(bad) == 0, bad


def _forbidden_hits(answer: str, packet: dict[str, Any]) -> list[str]:
    forbidden = (packet.get("constraints") or {}).get("forbidden") or []
    hits: list[str] = []
    al = answer.lower()
    for item in forbidden:
        s = str(item).lower()
        if s and s in al:
            hits.append(f"forbidden:{item}")
    return hits


def validate_candidate(
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    violations: list[str] = []
    valid_schema = True
    state_faithful = True

    if not candidate.get("parse_ok"):
        valid_schema = False
        violations.append(f"parse_failed:{candidate.get('parse_error') or 'unknown'}")

    answer = (candidate.get("answer") or "").strip()
    if not answer:
        valid_schema = False
        violations.append("missing_answer")

    required = (packet.get("acceptance_contract") or {}).get("required_sections") or [
        "answer",
        "evidence_used",
        "next_state",
    ]
    for section in required:
        if section == "answer" and not answer:
            violations.append("required_section:answer")
            valid_schema = False
        if section == "evidence_used" and not isinstance(candidate.get("evidence_used"), list):
            violations.append("required_section:evidence_used")
            valid_schema = False
        if section == "next_state" and not isinstance(candidate.get("next_state"), dict):
            violations.append("required_section:next_state")
            valid_schema = False

    max_words = int((packet.get("constraints") or {}).get("max_words") or 180)
    word_count = len(answer.split())
    if word_count > max_words:
        violations.append(f"max_words_exceeded:{word_count}>{max_words}")
        # length is soft-schema; still counts as validation fail for repair
        valid_schema = False

    pool = _packet_evidence_pool(packet)
    ok_e, e_bad = _evidence_ok(list(candidate.get("evidence_used") or []), pool)
    if not ok_e:
        state_faithful = False
        violations.extend(e_bad)

    if (packet.get("acceptance_contract") or {}).get("must_reference_goal", True):
        if not _goal_referenced(answer, packet):
            state_faithful = False
            violations.append("goal_not_referenced")

    forb = _forbidden_hits(answer, packet)
    if forb:
        state_faithful = False
        violations.extend(forb)

    # Thread touches must exist if provided
    ns = candidate.get("next_state") or {}
    touches = ns.get("thread_touch") or []
    known_ids = {
        str(t.get("id")).lower()
        for t in (packet.get("open_threads") or [])
        if isinstance(t, dict) and t.get("id")
    }
    if isinstance(touches, list):
        for tid in touches:
            if str(tid).lower() not in known_ids and str(tid).strip():
                # also allow title match
                titles = {
                    str(t.get("title", "")).lower()
                    for t in (packet.get("open_threads") or [])
                    if isinstance(t, dict)
                }
                if str(tid).lower() not in titles:
                    state_faithful = False
                    violations.append(f"unknown_thread_touch:{tid}")

    decision_ready = valid_schema and state_faithful and not violations
    repairable = not decision_ready  # one repair pass always allowed if invalid

    receipt = {
        "receipt_id": receipt_id(),
        "candidate_id": candidate.get("candidate_id"),
        "packet_id": packet.get("packet_id"),
        "created_at": utc_now_iso(),
        "valid_schema": valid_schema,
        "state_faithful": state_faithful,
        "violations": violations,
        "repairable": repairable and candidate.get("pass_index", 0) == 0,
        "decision": "pending",
        "word_count": word_count,
    }
    return receipt
