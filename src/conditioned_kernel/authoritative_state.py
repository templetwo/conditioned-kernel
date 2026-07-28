"""Authoritative-state answers: substrate owns a narrow class of cognition.

Studio only. Measurement mode never calls this module.

For recognized state questions the substrate resolves canonical claims from
filesystem state / recent dialogue. The model may phrase them; if it fails
(question echo, schema leak, reversed fact), the substrate renders the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from conditioned_kernel.edge import EdgeProfile
from conditioned_kernel.ids import candidate_id, utc_now_iso
from conditioned_kernel.return_path.validate import is_template_echo_text
from conditioned_kernel.state import SubstrateState

Kind = str  # goal | edge_or_model | cloud_policy | open_threads | recent_recall


@dataclass(frozen=True)
class StateObligation:
    """Canonical answer data the candidate must preserve."""

    kind: Kind
    claims: tuple[str, ...]  # human-readable required claims
    required_substrings: tuple[str, ...]  # must appear (case-insensitive)
    forbidden_substrings: tuple[str, ...]  # must not appear as assertions
    fallback_answer: str
    evidence: tuple[str, ...]
    source_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "claims": list(self.claims),
            "required_substrings": list(self.required_substrings),
            "forbidden_substrings": list(self.forbidden_substrings),
            "fallback_answer": self.fallback_answer,
            "evidence": list(self.evidence),
            "source_fields": list(self.source_fields),
        }


_STOP = frozenset(
    {
        "what",
        "which",
        "where",
        "when",
        "with",
        "that",
        "this",
        "from",
        "have",
        "been",
        "were",
        "will",
        "your",
        "their",
        "about",
        "please",
        "working",
        "toward",
        "towards",
        "current",
        "using",
        "model",
        "edge",
        "target",
        "board",
        "allowed",
        "cloud",
        "services",
        "open",
        "threads",
        "thread",
        "codeword",
        "remember",
        "recall",
        "earlier",
        "before",
        "again",
        "tell",
        "said",
        "say",
        "just",
        "were",
        "we",
        "are",
        "the",
        "and",
        "for",
        "did",
        "you",
        "me",
        "my",
        "our",
        "goal",
        "running",
        "run",
        "local",
        "only",
        "true",
        "false",
        "yes",
        "not",
    }
)

_SCHEMA_LEAK = (
    "evidence_used",
    "next_state",
    "state_digest",
    "acceptance_contract",
    "packet_id",
    "open_threads",
    "required_sections",
    "continuity_assertions",
    "short helpful reply grounded",
    "treat it as prior dialogue",
    "return only valid json",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str, min_len: int = 4) -> list[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9][a-z0-9_\-]{" + str(min_len - 1) + r",}", (s or "").lower())
        if t not in _STOP
    ]


def classify_state_question(user_input: str) -> Kind | None:
    """Narrow keyword classifier. Returns None for open-generative turns."""
    q = _norm(user_input)
    if not q:
        return None

    # Cloud / local policy
    if re.search(r"\bcloud\b", q) and re.search(
        r"\b(allow|allowed|permit|permitted|ok|okay|enable|enabled|use|using|services?)\b",
        q,
    ):
        return "cloud_policy"
    if re.search(r"\b(fully local|local[- ]only|local operation)\b", q) and re.search(
        r"\b(are we|is this|do we|allowed|only)\b", q
    ):
        return "cloud_policy"

    # Goal (ask about the goal — not every sentence containing "goal")
    if re.search(r"\bgoal\b", q) and re.search(
        r"\b(what|which|current)\b", q
    ):
        return "goal"
    if re.search(r"\b(what are we (trying|building|working)|design intent)\b", q):
        return "goal"

    # Edge target / model / board — require interrogative intent, not mere mention
    if re.search(
        r"\b(which|what)\b.+\b(model|profile|board|edge target|edge device)\b", q
    ) or re.search(
        r"\b(model|profile|board|edge target)\b.+\b(using|active|default|running)\b", q
    ):
        return "edge_or_model"
    if re.search(r"\b(which board|what board|edge target|edge device)\b", q):
        return "edge_or_model"
    if re.search(r"\b(running it on|run it on|which .+ running)\b", q):
        return "edge_or_model"

    # Open threads
    if re.search(r"\b(open threads?|current threads?|active threads?)\b", q):
        return "open_threads"
    if re.search(r"\bthreads?\b", q) and re.search(r"\b(what|which|list|current|open)\b", q):
        return "open_threads"

    # Recent dialogue recall — not "remember X" store imperatives
    if re.search(r"\b(codeword|code word|passphrase|secret word)\b", q):
        if re.search(r"\b(what|which|remind|recall|was|were|again)\b", q):
            return "recent_recall"
        return None  # e.g. "Remember the codeword FALCON-9-DELTA."
    if re.search(r"\b(what did i (say|ask|tell)|what was the|what did we)\b", q):
        return "recent_recall"
    if re.search(r"\b(remind me|do you remember|what was my)\b", q):
        return "recent_recall"

    return None


def _goal_required_substrings(goal: str) -> list[str]:
    # Prefer distinctive multi-char tokens from the goal itself.
    toks = _tokens(goal, min_len=5)
    distinctive = [
        t
        for t in toks
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
            "local",
            "model",
        }
        or len(t) >= 7
    ]
    if not distinctive and toks:
        distinctive = toks[:4]
    # Also require a short contiguous snippet of the goal when short enough
    g = goal.strip()
    out = list(distinctive[:6])
    if 12 <= len(g) <= 80:
        out.append(g.lower()[:40])
    return out


def resolve_obligation(
    state: SubstrateState,
    user_input: str,
    *,
    profile: EdgeProfile | None = None,
    model: str | None = None,
) -> StateObligation | None:
    kind = classify_state_question(user_input)
    if kind is None:
        return None

    flags = state.current.get("flags") or {}
    goal = str(state.current.get("goal") or "").strip()
    edge = str(flags.get("edge_target") or "jetson_orin_nano_8gb")
    active_profile = str(state.current.get("active_profile") or "orin_nano_8gb")
    use_model = model or (profile.model if profile else "qwen3.5:0.8b")
    cloud = bool(flags.get("cloud", False))
    open_threads = state.open_threads()
    recent = state.recent_turns()

    if kind == "goal":
        if not goal:
            return StateObligation(
                kind=kind,
                claims=("No goal is currently set in substrate state.",),
                required_substrings=("no goal", "not set"),
                forbidden_substrings=(),
                fallback_answer="No goal is currently set in substrate state.",
                evidence=("Current goal: (empty)",),
                source_fields=("current.goal",),
            )
        req = _goal_required_substrings(goal)
        # Must not substitute edge target alone as the goal.
        return StateObligation(
            kind=kind,
            claims=(f"Current goal: {goal}",),
            required_substrings=tuple(req) if req else (goal.lower()[:24],),
            forbidden_substrings=(),
            fallback_answer=f"The current goal is: {goal}",
            evidence=(f"Current goal: {goal}",),
            source_fields=("current.goal",),
        )

    if kind == "edge_or_model":
        claims = (
            f"Edge target: {edge}",
            f"Active model: {use_model}",
            f"Active profile: {active_profile}",
        )
        req = [edge.lower(), use_model.lower()]
        # Also accept orin / jetson fragments
        for frag in ("orin", "jetson", "nano"):
            if frag in edge.lower():
                req.append(frag)
        # Evidence must be packet-pool strings (fact_list shapes).
        edge_fact = (
            f"Edge target: {edge} (one model at a time)."
            if flags.get("one_model_only", True)
            else f"Edge target: {edge}."
        )
        profile_fact = f"Active profile: {active_profile}."
        return StateObligation(
            kind=kind,
            claims=claims,
            required_substrings=tuple(dict.fromkeys(req)),  # dedupe preserve order
            forbidden_substrings=(),
            fallback_answer=(
                f"We are using edge target {edge} with model {use_model} "
                f"(profile {active_profile})."
            ),
            evidence=(edge_fact, profile_fact),
            source_fields=("flags.edge_target", "profile.model", "active_profile"),
        )

    if kind == "cloud_policy":
        if cloud:
            return StateObligation(
                kind=kind,
                claims=("Cloud services are enabled in this substrate configuration.",),
                required_substrings=("cloud", "enabled"),
                forbidden_substrings=("fully local", "cloud services are not allowed"),
                fallback_answer="Cloud services are enabled in this substrate configuration.",
                evidence=("Cloud: enabled",),
                source_fields=("flags.cloud",),
            )
        return StateObligation(
            kind=kind,
            claims=(
                "Cloud services are not allowed.",
                "Operation is fully local-only.",
            ),
            required_substrings=("local",),
            forbidden_substrings=(
                "cloud services are allowed",
                "cloud is allowed",
                "cloud apis are allowed",
                "yes, cloud",
                "uses cloud",
                "use cloud",
                "enabled cloud",
                "cloud enabled",
            ),
            fallback_answer=(
                "No. Cloud services are not allowed; this system operates fully local-only."
            ),
            evidence=(
                "Operation is fully local-only; cloud services are not allowed.",
            ),
            source_fields=("flags.cloud",),
        )

    if kind == "open_threads":
        if not open_threads:
            return StateObligation(
                kind=kind,
                claims=("There are no open threads.",),
                required_substrings=("no open",),
                forbidden_substrings=(),
                fallback_answer="There are currently no open threads.",
                evidence=("open_thread_count: 0",),
                source_fields=("threads",),
            )
        lines = []
        req: list[str] = []
        for t in open_threads:
            tid = str(t.get("id") or "")
            title = str(t.get("title") or "")
            lines.append(f"{tid}: {title}".strip(": "))
            if tid:
                req.append(tid.lower())
        body = "; ".join(lines)
        # Evidence: thread ids are in the packet open_threads pool.
        return StateObligation(
            kind=kind,
            claims=tuple(lines),
            required_substrings=tuple(req[:6]),
            forbidden_substrings=(),
            fallback_answer=f"Current open threads: {body}",
            evidence=tuple(req[:4]) if req else tuple(lines[:2]),
            source_fields=("threads",),
        )

    if kind == "recent_recall":
        if not recent:
            return StateObligation(
                kind=kind,
                claims=("No recent dialogue is stored in this session.",),
                required_substrings=("no recent", "no dialogue"),
                forbidden_substrings=(),
                fallback_answer=(
                    "I have no recent dialogue turns stored in this session yet."
                ),
                evidence=("recent_turns: []",),
                source_fields=("recent_turns",),
            )
        # Distinctive tokens from prior user lines (dialogue-only facts)
        req_tokens: list[str] = []
        snippets: list[str] = []
        for t in recent:
            u = str(t.get("user") or "")
            a = str(t.get("answer") or "")
            if u:
                snippets.append(f"you: {u}")
            # Prefer long alphanumeric tokens (codewords)
            for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}", u + " " + a):
                if w.lower() not in _STOP and len(w) >= 5:
                    req_tokens.append(w)
        # Prefer last user message's distinctive tokens first
        last_user = str(recent[-1].get("user") or "")
        last_toks = [
            w
            for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}", last_user)
            if w.lower() not in _STOP and len(w) >= 5
        ]
        ordered = list(dict.fromkeys(last_toks + list(reversed(req_tokens))))
        # Keep a few strongest
        ordered = ordered[:8]
        if not ordered:
            ordered = ["recent"]
            fallback = "Recent dialogue: " + " | ".join(snippets[-3:])
        else:
            # Prefer quoting the most recent user line that looks like a remember cue
            remember_line = ""
            for t in reversed(recent):
                u = str(t.get("user") or "")
                if re.search(r"\b(remember|codeword|code word)\b", u, re.I):
                    remember_line = u
                    break
            if remember_line:
                fallback = (
                    f"From earlier in this session: {remember_line} "
                    f"(key terms: {', '.join(ordered[:4])})."
                )
            else:
                fallback = (
                    "From recent dialogue in this session: "
                    + " | ".join(snippets[-3:])
                    + f" Key terms: {', '.join(ordered[:4])}."
                )
        # Evidence from recent turn text (in packet pool) or local fact.
        ev: list[str] = []
        for t in recent[-3:]:
            u = str(t.get("user") or "").strip()
            a = str(t.get("answer") or "").strip()
            if u:
                ev.append(u)
            elif a:
                ev.append(a)
        if not ev:
            ev = ["This system is fully local."]
        return StateObligation(
            kind=kind,
            claims=tuple(f"recent:{t}" for t in ordered[:4]),
            required_substrings=tuple(t.lower() for t in ordered[:4]),
            forbidden_substrings=(),
            fallback_answer=fallback,
            evidence=tuple(ev[:4]),
            source_fields=("recent_turns",),
        )

    return None


def _is_question_echo(answer: str, user_input: str) -> bool:
    a = _norm(answer).strip(" .\"'?")
    q = _norm(user_input).strip(" .\"'?")
    if not a or not q:
        return False
    if a == q:
        return True
    if q in a and len(a) <= len(q) + 16:
        return True
    if a in q and len(a) >= max(12, int(0.75 * len(q))):
        return True
    # High token overlap with little new content
    qt = set(_tokens(q, min_len=4))
    at = set(_tokens(a, min_len=4))
    if qt and len(qt & at) / len(qt) >= 0.9 and len(at - qt) <= 1:
        return True
    return False


def _has_schema_leak(answer: str) -> bool:
    al = answer.lower()
    return any(m in al for m in _SCHEMA_LEAK)


def _has_required(answer: str, required: Sequence[str]) -> bool:
    if not required:
        return True
    al = answer.lower()
    # Need at least one strong hit for short req lists; majority for longer
    hits = sum(1 for r in required if r and r.lower() in al)
    if len(required) <= 2:
        return hits >= 1
    need = max(1, (len(required) + 1) // 2)
    return hits >= need


def _has_forbidden(answer: str, forbidden: Sequence[str]) -> list[str]:
    al = answer.lower()
    return [f for f in forbidden if f and f.lower() in al]


def check_obligation(answer: str, obligation: StateObligation, user_input: str) -> list[str]:
    """Return violation codes if answer fails to preserve canonical claims."""
    reasons: list[str] = []
    a = (answer or "").strip()
    if not a:
        reasons.append("authoritative_empty_answer")
        return reasons
    if _is_question_echo(a, user_input):
        reasons.append("authoritative_question_echo")
    if _has_schema_leak(a) or is_template_echo_text(a):
        reasons.append("authoritative_schema_leak")
    if not _has_required(a, obligation.required_substrings):
        reasons.append("authoritative_missing_claim")
    bad = _has_forbidden(a, obligation.forbidden_substrings)
    if bad:
        reasons.append("authoritative_forbidden_claim")
    # Goal must not be replaced by edge target alone
    if obligation.kind == "goal":
        al = a.lower()
        edge_hits = sum(
            1 for frag in ("jetson_orin_nano_8gb", "orin_nano", "edge target") if frag in al
        )
        claim_hits = sum(1 for r in obligation.required_substrings if r in al)
        if edge_hits and claim_hits == 0:
            reasons.append("authoritative_goal_substituted")
    return reasons


def render_fallback_candidate(
    obligation: StateObligation,
    *,
    packet_id: str,
    pass_index: int = 0,
    reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Substrate-authored candidate when the model fails the obligation."""
    return {
        "candidate_id": candidate_id(),
        "packet_id": packet_id,
        "pass_index": pass_index,
        "status": "substrate_authoritative",
        "raw_text": "",
        "parsed_at": utc_now_iso(),
        "parse_ok": True,
        "answer": obligation.fallback_answer,
        "evidence_used": list(obligation.evidence),
        "evidence_source": "substrate_authoritative",
        "next_state": {},
        "self_report": {},
        "parse_error": None,
        "authoritative_kind": obligation.kind,
        "authoritative_fallback": True,
        "authoritative_reasons": list(reasons or []),
    }


def enforce_authoritative_candidate(
    candidate: dict[str, Any],
    obligation: StateObligation,
    *,
    user_input: str,
    packet_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Keep model phrasing if claims preserved; else replace with fallback."""
    answer = str(candidate.get("answer") or "")
    reasons = check_obligation(answer, obligation, user_input)
    if not candidate.get("parse_ok"):
        reasons = list(dict.fromkeys([*reasons, "authoritative_parse_failed"]))
    if reasons:
        fb = render_fallback_candidate(
            obligation,
            packet_id=packet_id,
            pass_index=int(candidate.get("pass_index") or 0),
            reasons=reasons,
        )
        return fb, reasons
    out = dict(candidate)
    # Ensure packet-local evidence is present for companion accept path
    if not out.get("evidence_used"):
        out["evidence_used"] = list(obligation.evidence)
        out["evidence_source"] = "substrate_authoritative_evidence"
    out["authoritative_kind"] = obligation.kind
    out["authoritative_fallback"] = False
    out["authoritative_reasons"] = []
    return out, []
