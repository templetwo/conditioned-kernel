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


# Clause-level denial/prohibition cues. Word-bounded so "no" does not fire on
# "now"/"nothing". Used only to decide polarity of a contradiction marker.
_NEGATION_CUE_RE = re.compile(
    r"\b(?:no|not|never|none|neither|nor|cannot|can't|cant|don't|dont|doesn't|doesnt|"
    r"won't|wont|isn't|isnt|aren't|arent|without|forbidden|prohibited|disallowed|"
    r"denied|blocked|banned|excluded|disabled|refuse|refuses|unsupported)\b"
    r"|out of scope|off[- ]limits|not allowed"
)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str, min_len: int = 4) -> list[str]:
    return [w for w in re.findall(rf"[a-z0-9]{{{min_len},}}", s.lower()) if w not in _GOAL_STOP]


def _packet_evidence_pool(packet: dict[str, Any]) -> set[str]:
    """Evidence pool for the turn.

    Companion mode: prefer `evidence_pool_selected` (from contributions
    actually placed in this turn's field). Do not validate against a hidden
    full project report the model was not meant to see.
    Measurement mode: full facts / threads / recent as before.
    """
    pool: set[str] = set()
    contract = packet.get("acceptance_contract") or {}
    companion = str(contract.get("acceptance_mode") or "") == "companion"
    selected = packet.get("evidence_pool_selected")
    # Companion: selected list is authoritative even when empty (quiet turn).
    if companion and isinstance(selected, list):
        for item in selected:
            pool.add(str(item).strip().lower())
        for claim in ((packet.get("authoritative_obligation") or {}).get("claims") or []):
            pool.add(str(claim).strip().lower())
        # Selected facts still present in packet.facts for this turn
        for fact in packet.get("facts") or []:
            pool.add(str(fact).strip().lower())
        return {p for p in pool if p}

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
    for turn in packet.get("recent_turns") or []:
        if isinstance(turn, dict):
            if turn.get("user"):
                pool.add(str(turn["user"]).strip().lower())
            if turn.get("answer"):
                pool.add(str(turn["answer"]).strip().lower())
        else:
            pool.add(str(turn).strip().lower())
    digest = packet.get("state_digest") or {}
    if digest.get("goal"):
        pool.add(str(digest["goal"]).strip().lower())
    if digest.get("design_intent"):
        pool.add(str(digest["design_intent"]).strip().lower())
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


def is_intent_echo(answer: str, design_intent: str) -> bool:
    """True if answer is a near-copy of the design-intent string."""
    return is_goal_echo(answer, design_intent)


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


# Instruction / repair-template bleed. Kept module-level so accept can refuse
# to append poisoned text even if a path ever accepted past validation.
TEMPLATE_ECHO_MARKERS: tuple[str, ...] = (
    # Legacy repair / measurement placeholders
    "(short reply that mentions",
    "string_from_facts",
    "copy a fact",
    "STRING_FROM_FACTS",
    "answer here",
    # Companion system-prompt phrases (compile.py) — 0.5b often echoes these.
    # Prefer multi-word instruction fragments over short colloquial phrases.
    "short helpful reply grounded in the packet",
    "treat it as prior dialogue",
    "treat it as prior dialogue and stay consistent",
    "substrate can ground",
    "prefer exact strings from facts",
    "return only valid json",
    "local conditioned-kernel transducer",
    "never invent thread ids",
    "may be [] if unsure",
)


def is_template_echo_text(text: str) -> bool:
    """True if text looks like system/repair instruction bleed."""
    if not text:
        return False
    low = text.lower()
    return any(m.lower() in low for m in TEMPLATE_ECHO_MARKERS)


def is_substantial_repeat(new_text: str, prior_text: str) -> bool:
    """True when new answer is essentially the same linguistic groove as prior."""
    n = _norm_ws(new_text).strip(" .\"'")
    p = _norm_ws(prior_text).strip(" .\"'")
    if not n or not p:
        return False
    if n == p:
        return True
    # Long prior answer re-emitted as prefix/body of the new one
    if len(p) >= 48 and p[:80] in n:
        return True
    if len(n) >= 48 and n[:80] in p:
        return True
    nt = set(_tokens(n, min_len=4))
    pt = set(_tokens(p, min_len=4))
    if not pt or not nt:
        return False
    overlap = len(nt & pt) / len(pt)
    novel = len(nt - pt)
    # High reuse of prior content with little new signal
    if overlap >= 0.85 and novel <= 3:
        return True
    if overlap >= 0.92 and novel <= 6:
        return True
    return False


def prior_accepted_answer(packet: dict[str, Any]) -> str:
    """Most recent accepted assistant answer (control plane).

    Prefer `prior_accepted_answer_control` so the stale-response guard works
    even when that turn was withheld from the selected dialogue field.
    """
    control = str(packet.get("prior_accepted_answer_control") or "").strip()
    if control:
        return control
    turns = packet.get("recent_turns") or []
    if not isinstance(turns, list) or not turns:
        return ""
    last = turns[-1]
    if isinstance(last, dict):
        return str(last.get("answer") or "").strip()
    return ""


def user_prompt_changed(packet: dict[str, Any], user_input: str) -> bool:
    turns = packet.get("recent_turns") or []
    if not isinstance(turns, list) or not turns:
        return True
    last = turns[-1]
    if not isinstance(last, dict):
        return True
    prior_u = _norm_ws(str(last.get("user") or ""))
    cur = _norm_ws(user_input)
    return bool(cur) and cur != prior_u


def substrate_supply_evidence(
    answer: str,
    packet: dict[str, Any],
    *,
    max_items: int = 2,
) -> list[str]:
    """Studio path: substrate owns grounding when the model does not cite.

    The model supplies language; the substrate attaches packet-local facts.
    Prefers facts that lexically overlap the answer; otherwise first fact(s).
    """
    facts = [str(f).strip() for f in (packet.get("facts") or []) if str(f).strip()]
    goal = str((packet.get("state_digest") or {}).get("goal") or "").strip()
    if not facts and goal:
        facts = [goal]
    if not facts:
        return ["This system is fully local."]

    ans = (answer or "").lower()
    ranked: list[tuple[int, str]] = []
    for f in facts:
        toks = [t for t in re.findall(r"[a-z0-9]{4,}", f.lower()) if len(t) >= 4]
        hits = sum(1 for t in toks if t in ans)
        ranked.append((hits, f))
    ranked.sort(key=lambda x: (-x[0], -len(x[1])))
    chosen = [f for h, f in ranked if h > 0][:max_items]
    if not chosen:
        chosen = [facts[0]]
    return chosen


def apply_companion_grounding(
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    """Mutate a copy of candidate for companion acceptance (product path).

    Empty or unusable evidence_used is filled from the packet. Does not invent
    facts outside the arrival packet. Measurement mode never calls this.
    """
    out = dict(candidate)
    evidence = list(out.get("evidence_used") or [])
    usable = [str(e).strip() for e in evidence if str(e).strip() and len(str(e).strip()) >= 12]
    if usable:
        out["evidence_used"] = usable
        out["evidence_source"] = out.get("evidence_source") or "model"
        return out
    supplied = substrate_supply_evidence(str(out.get("answer") or ""), packet)
    out["evidence_used"] = supplied
    out["evidence_source"] = "substrate_supplied"
    return out


def _forbidden_hits(answer: str, packet: dict[str, Any]) -> list[str]:
    forbidden = (packet.get("constraints") or {}).get("forbidden") or []
    hits: list[str] = []
    al = answer.lower()
    for item in forbidden:
        s = str(item).lower()
        if s and s in al:
            hits.append(f"forbidden:{item}")
    return hits


def _clauses(text: str) -> list[str]:
    """Split on sentence/clause terminators only.

    Deliberately NOT split on ' and '/','. Splitting there breaks denials that
    carry the negation once for a conjoined list ("cloud APIs and sensors are
    out of scope"), which would strand the bare topic term in its own clause
    and re-create the false positive this function exists to avoid.
    """
    return [c for c in re.split(r"[.;!?\n]+", (text or "").lower()) if c.strip()]


def _is_negated(clause: str) -> bool:
    """True if the clause denies/prohibits rather than asserts.

    Clause-scoped, not answer-scoped: a negation in one sentence must not
    excuse an assertion in the next.
    """
    return bool(_NEGATION_CUE_RE.search(clause))


def _fact_contradictions(answer: str, packet: dict[str, Any]) -> list[str]:
    """Closed mechanical contradiction against packet facts (not open NLI).

    Polarity-aware. A marker only counts as a contradiction when the clause
    containing it ASSERTS the capability. Mentioning a forbidden capability in
    order to deny it ("cloud APIs are out of scope") is agreement with the
    facts, not contradiction — and is the only way to answer a question that
    asks about that capability. Matching on the bare topic term made the
    constraint probe unanswerable: `not_responsive` required the term, this
    check forbade it.

    Known residual: double negation ("cloud APIs are not forbidden") reads as
    denial and is not flagged. Accepted deliberately — closing it needs real
    parsing, and the repo rule is mechanical checks, not NLI.
    """
    if not (packet.get("acceptance_contract") or {}).get("must_not_contradict_facts", False):
        return []
    facts_blob = " ".join(str(f).lower() for f in (packet.get("facts") or []))
    hits: list[str] = []
    for clause in _clauses(answer):
        if _is_negated(clause):
            continue
        for fact_markers, contra_markers in _FACT_CONTRADICTION_RULES:
            if not any(m in facts_blob for m in fact_markers):
                continue
            for c in contra_markers:
                if c in clause:
                    hits.append(f"contradicts_facts:{c}")
    return hits


def validate_candidate(
    candidate: dict[str, Any],
    packet: dict[str, Any],
) -> dict[str, Any]:
    violations: list[str] = []
    valid_schema = True
    state_faithful = True

    contract = packet.get("acceptance_contract") or {}
    # measurement (default): Laboratory experiment contract — model must cite.
    # companion: Studio product path — substrate may supply evidence.
    acceptance_mode = str(contract.get("acceptance_mode") or "measurement")
    companion = acceptance_mode == "companion"

    work = dict(candidate)
    if companion:
        work = apply_companion_grounding(work, packet)
        # Align citations to this turn's selected evidence pool only.
        pool_items = [
            str(x).strip()
            for x in (
                packet.get("evidence_pool_selected")
                or packet.get("facts")
                or []
            )
            if str(x).strip()
        ]
        cleaned: list[str] = []
        for e in list(work.get("evidence_used") or []):
            raw_e = str(e).strip()
            el = raw_e.lower()
            if len(raw_e) < 12:
                continue  # drop bookkeeping-noise / short tokens
            if any(el in p.lower() or p.lower() in el for p in pool_items):
                cleaned.append(raw_e)
        if not cleaned and pool_items:
            # Prefer a pool line long enough to satisfy evidence checks
            for p in pool_items:
                if len(p) >= 12:
                    cleaned = [p]
                    work["evidence_source"] = "substrate_supplied"
                    break
        work["evidence_used"] = cleaned
        # Reflect grounding back onto the caller's candidate so accept/logs see it.
        candidate["evidence_used"] = list(cleaned)
        if work.get("evidence_source"):
            candidate["evidence_source"] = work["evidence_source"]

    user_input = str(packet.get("user_input") or "")
    goal = str((packet.get("state_digest") or {}).get("goal") or "")
    design_intent = str((packet.get("state_digest") or {}).get("design_intent") or "")

    if not work.get("parse_ok"):
        valid_schema = False
        violations.append(f"parse_failed:{work.get('parse_error') or 'unknown'}")

    answer = (work.get("answer") or "").strip()
    if not answer:
        valid_schema = False
        violations.append("missing_answer")

    # Reject repair-template and system-prompt echoes (0.5b often splices
    # instruction text into the answer; that must not enter recent_turns).
    ans_l = answer.lower()
    for marker in TEMPLATE_ECHO_MARKERS:
        if marker.lower() in ans_l or marker in answer:
            valid_schema = False
            violations.append("template_echo")
            break
    for item in work.get("evidence_used") or []:
        if str(item) in {"STRING_FROM_FACTS", "(copy a fact)", "STRING"}:
            state_faithful = False
            violations.append("template_echo_evidence")
            break

    # Anti-degeneracy: goal echo is never an answer.
    # Substrate authoritative fallbacks intentionally restate the goal claim.
    if (
        answer
        and goal
        and is_goal_echo(answer, goal)
        and not work.get("authoritative_fallback")
    ):
        state_faithful = False
        violations.append("goal_echo")

    # Same anti-paste for design intent. Fallback restates the owned sentence.
    if (
        answer
        and design_intent
        and is_intent_echo(answer, design_intent)
        and not work.get("authoritative_fallback")
    ):
        state_faithful = False
        violations.append("intent_echo")

    # Responsiveness:
    # - measurement: hard reject (Laboratory contract)
    # - companion: advisory only — small models often answer without echo-tokens
    # - authoritative_fallback: already claim-checked; skip
    advisories: list[str] = []
    if (
        answer
        and user_input
        and not is_responsive(answer, user_input)
        and not work.get("authoritative_fallback")
    ):
        if companion:
            advisories.append("not_responsive")
        else:
            state_faithful = False
            violations.append("not_responsive")

    # Studio: stale-response attractor — repeating the last accepted answer
    # while the user moved on is a hard structural failure (repair then reject).
    if companion and answer and not work.get("authoritative_fallback"):
        prior = prior_accepted_answer(packet)
        if (
            prior
            and user_prompt_changed(packet, user_input)
            and is_substantial_repeat(answer, prior)
        ):
            state_faithful = False
            violations.append("stale_response_repeat")

    required = contract.get("required_sections") or [
        "answer",
        "evidence_used",
        "next_state",
    ]
    for section in required:
        if section == "answer" and not answer:
            violations.append("required_section:answer")
            valid_schema = False
        if section == "evidence_used" and not isinstance(work.get("evidence_used"), list):
            violations.append("required_section:evidence_used")
            valid_schema = False
        if section == "next_state" and not isinstance(work.get("next_state"), dict):
            violations.append("required_section:next_state")
            valid_schema = False

    max_words = int((packet.get("constraints") or {}).get("max_words") or 180)
    word_count = len(answer.split()) if answer else 0
    if word_count > max_words:
        violations.append(f"max_words_exceeded:{word_count}>{max_words}")
        valid_schema = False

    pool = _packet_evidence_pool(packet)
    evidence_list = list(work.get("evidence_used") or [])
    # Companion quiet field: empty selected pool + empty evidence is valid.
    if companion and not pool and not evidence_list:
        ok_e, e_bad = True, []
    else:
        ok_e, e_bad = _evidence_ok(evidence_list, pool)
    if not ok_e:
        state_faithful = False
        violations.extend(e_bad)

    # Companion: goal mention optional (0.5b often answers without thesis keywords).
    # Measurement: still requires load-bearing goal tokens.
    must_goal = contract.get("must_reference_goal")
    if must_goal is None:
        must_goal = not companion
    if must_goal:
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
    ns = work.get("next_state") or {}
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
                # Companion: unknown touches are filtered (thread may be withheld
                # from this turn's field). Measurement: hard fail.
                if companion:
                    advisories.append(f"thread_touch_filtered:{s[:60]}")
                else:
                    state_faithful = False
                    violations.append(f"unknown_thread_touch:{s[:60]}")

    decision_ready = valid_schema and state_faithful and not violations
    repairable = not decision_ready

    return {
        "receipt_id": receipt_id(),
        "candidate_id": work.get("candidate_id"),
        "packet_id": packet.get("packet_id"),
        "created_at": utc_now_iso(),
        "valid_schema": valid_schema,
        "state_faithful": state_faithful,
        "violations": violations,
        "advisories": advisories,
        "repairable": repairable and work.get("pass_index", 0) == 0,
        "decision": "pending",
        "word_count": word_count,
        "acceptance_mode": acceptance_mode,
        "evidence_source": work.get("evidence_source") or "model",
    }
