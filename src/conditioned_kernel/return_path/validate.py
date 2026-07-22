"""Deterministic validation against the arrival packet contract.

Closed-set / mechanical checks only. Post M1 audit:
- anti goal-echo
- responsiveness to user_input
- real evidence matching (no 1-char substring grease)
- must_not_contradict_facts implemented when declared
"""

from __future__ import annotations

import re
from typing import Any

from conditioned_kernel.ids import receipt_id, utc_now_iso

_GOAL_STOP = frozenset(
    {
        "with",
        "from",
        "that",
        "this",
        "over",
        "under",
        "into",
        "onto",
        "than",
        "then",
        "have",
        "been",
        "were",
        "will",
        "your",
        "their",
        "about",
        "small",
        "local",
        "model",
        "does",
        "what",
        "when",
        "where",
        "which",
        "please",
        "briefly",
        "using",
        "current",
    }
)

# (fact_markers, answer_contradiction_markers)
_FACT_CONTRADICTION_RULES: list[tuple[list[str], list[str]]] = [
    (
        ["fully local", "100% local", "no cloud"],
        [
            "cloud api",
            "cloud apis",
            "calls cloud",
            "call cloud",
            "not local",
            "uses cloud",
            "use cloud",
            "streams to cloud",
        ],
    ),
    (
        ["sensors are out of scope", "sensors out of scope", "no sensors"],
        [
            "use sensors",
            "uses sensors",
            "using sensors",
            "sensor data",
            "microphone",
            "camera",
            "sensors are allowed",
            "sensors enabled",
        ],
    ),
    (
        ["tools are out of scope", "no autonomous tools", "tools out of scope"],
        ["tool_calls", "calls tools", "use tools", "autonomous tool"],
    ),
]


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str, min_len: int = 4) -> list[str]:
    return [w for w in re.findall(rf"[a-z0-9]{{{min_len},}}", s.lower()) if w not in _GOAL_STOP]


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


def is_goal_echo(answer: str, goal: str) -> bool:
    """True if answer is the goal (or near-copy). Pure parroting is not an answer."""
    a = _norm_ws(answer).strip(" .\"'")
    g = _norm_ws(goal).strip(" .\"'")
    if not a or not g:
        return False
    if a == g:
        return True
    if g in a and len(a) <= len(g) + 24:
        return True
    if a in g and len(a) >= max(20, int(0.7 * len(g))):
        return True
    gtoks = set(_tokens(g))
    atoks = set(_tokens(a))
    if not gtoks:
        return False
    overlap = len(gtoks & atoks) / len(gtoks)
    # Nearly all goal tokens and little else
    if overlap >= 0.85 and len(atoks - gtoks) <= 2:
        return True
    return False


def is_responsive(answer: str, user_input: str) -> bool:
    """Answer must engage the question, not only the goal."""
    q = _norm_ws(user_input)
    a = _norm_ws(answer)
    if not q or not a:
        return False
    qtoks = _tokens(q)
    # Drop ultra-generic prompt glue
    qtoks = [
        t
        for t in qtoks
        if t
        not in {
            "state",
            "answer",
            "write",
            "name",
            "cite",
            "sentences",
            "sentence",
            "system",
            "allowed",
            "ignore",
            "schema",
            "free",
            "form",
            "essay",
            "about",
        }
    ]
    if not qtoks:
        return len(a.split()) >= 4
    hits = sum(1 for t in qtoks if t in a)
    need = 1 if len(qtoks) <= 3 else 2
    return hits >= need


def _goal_referenced(answer: str, packet: dict[str, Any]) -> bool:
    """Share load-bearing goal tokens — but goal echo alone is rejected separately."""
    goal = str((packet.get("state_digest") or {}).get("goal") or "").strip()
    if not goal:
        return True
    if is_goal_echo(answer, goal):
        return False  # echo is not valid reference
    tokens = _tokens(goal)
    distinctive = [
        t
        for t in tokens
        if t
        in {
            "demonstrate",
            "conditioned",
            "kernel",
            "substrate",
            "generation",
            "jetson",
            "orin",
            "nano",
            "edge",
            "budgets",
            "bare",
            "gain",
        }
        or len(t) >= 7
    ]
    pool = distinctive or tokens
    if not pool:
        return False
    ans_l = answer.lower()
    hits = sum(1 for t in pool if t in ans_l)
    need = 2 if len(pool) >= 4 else 1
    return hits >= need


def _evidence_ok(evidence: list[str], pool: set[str]) -> tuple[bool, list[str]]:
    """Evidence must be substantial and match a pool string (not 1-char grease)."""
    if not evidence:
        return False, ["evidence_used_empty"]
    bad: list[str] = []
    for item in evidence:
        s = item.strip().lower()
        if len(s) < 12:
            bad.append(f"evidence_too_short:{item[:40]}")
            continue
        # Prefer evidence as substring of a pool entry (copied fact fragment)
        if any(s in p for p in pool):
            continue
        # Or a full pool entry nested in a slightly longer citation
        if any(p in s and len(p) >= 12 for p in pool):
            continue
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


def _fact_contradictions(answer: str, packet: dict[str, Any]) -> list[str]:
    """Closed mechanical contradiction against packet facts (not open NLI)."""
    if not (packet.get("acceptance_contract") or {}).get("must_not_contradict_facts", False):
        return []
    facts_blob = " ".join(str(f).lower() for f in (packet.get("facts") or []))
    al = answer.lower()
    hits: list[str] = []
    for fact_markers, contra_markers in _FACT_CONTRADICTION_RULES:
        if not any(m in facts_blob for m in fact_markers):
            continue
        for c in contra_markers:
            if c in al:
                hits.append(f"contradicts_facts:{c}")
    return hits


def validate_candidate(
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    violations: list[str] = []
    valid_schema = True
    state_faithful = True

    user_input = str(packet.get("user_input") or "")
    goal = str((packet.get("state_digest") or {}).get("goal") or "")

    if not candidate.get("parse_ok"):
        valid_schema = False
        violations.append(f"parse_failed:{candidate.get('parse_error') or 'unknown'}")

    answer = (candidate.get("answer") or "").strip()
    if not answer:
        valid_schema = False
        violations.append("missing_answer")

    # Reject obvious repair-template echoes
    template_markers = (
        "(short reply that mentions",
        "string_from_facts",
        "copy a fact",
        "STRING_FROM_FACTS",
        "answer here",
    )
    ans_l = answer.lower()
    for marker in template_markers:
        if marker.lower() in ans_l or marker in answer:
            valid_schema = False
            violations.append("template_echo")
            break
    for item in candidate.get("evidence_used") or []:
        if str(item) in {"STRING_FROM_FACTS", "(copy a fact)", "STRING"}:
            state_faithful = False
            violations.append("template_echo_evidence")
            break

    # Anti-degeneracy: goal echo is never an answer
    if answer and goal and is_goal_echo(answer, goal):
        state_faithful = False
        violations.append("goal_echo")

    # Responsiveness to the actual user question
    if answer and user_input and not is_responsive(answer, user_input):
        state_faithful = False
        violations.append("not_responsive")

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
    word_count = len(answer.split()) if answer else 0
    if word_count > max_words:
        violations.append(f"max_words_exceeded:{word_count}>{max_words}")
        valid_schema = False

    pool = _packet_evidence_pool(packet)
    ok_e, e_bad = _evidence_ok(list(candidate.get("evidence_used") or []), pool)
    if not ok_e:
        state_faithful = False
        violations.extend(e_bad)

    if (packet.get("acceptance_contract") or {}).get("must_reference_goal", True):
        if answer and not _goal_referenced(answer, packet):
            state_faithful = False
            violations.append("goal_not_referenced")

    forb = _forbidden_hits(answer, packet)
    if forb:
        state_faithful = False
        violations.extend(forb)

    contra = _fact_contradictions(answer, packet)
    if contra:
        state_faithful = False
        violations.extend(contra)

    # Thread touches
    ns = candidate.get("next_state") or {}
    touches = ns.get("thread_touch") or []
    known_ids = {
        str(t.get("id")).lower()
        for t in (packet.get("open_threads") or [])
        if isinstance(t, dict) and t.get("id")
    }
    titles = {
        str(t.get("title", "")).lower()
        for t in (packet.get("open_threads") or [])
        if isinstance(t, dict)
    }
    junk = {
        "",
        "ids used",
        "id",
        "ids",
        "none",
        "null",
        "n/a",
        "na",
        "[]",
        ".",
        "thread_touch",
        "open_threads",
        "string",
    }
    if isinstance(touches, list):
        for tid in touches:
            s = str(tid).strip()
            if s.lower() in junk:
                continue
            sl = s.lower()
            matched = sl in known_ids or sl in titles
            if not matched:
                for kid in known_ids:
                    if kid and kid in sl:
                        matched = True
                        break
            if not matched:
                for title in titles:
                    if title and (title in sl or sl in title):
                        matched = True
                        break
            if not matched:
                state_faithful = False
                violations.append(f"unknown_thread_touch:{s[:60]}")

    decision_ready = valid_schema and state_faithful and not violations
    repairable = not decision_ready

    return {
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
