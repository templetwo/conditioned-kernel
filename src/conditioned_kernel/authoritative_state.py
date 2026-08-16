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
from conditioned_kernel.return_path.validate import is_goal_echo, is_template_echo_text
from conditioned_kernel.state import DEFAULT_DESIGN_INTENT_FRAMED, SubstrateState

Kind = str  # goal | design_intent | operator | edge_or_model | cloud_policy | open_threads | recent_recall


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
    # Near-copy of these owned strings is a wrong-claim (e.g. research goal
    # pasted as an answer to a design-intent question).
    anti_echo_of: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "claims": list(self.claims),
            "required_substrings": list(self.required_substrings),
            "forbidden_substrings": list(self.forbidden_substrings),
            "fallback_answer": self.fallback_answer,
            "evidence": list(self.evidence),
            "source_fields": list(self.source_fields),
            "anti_echo_of": list(self.anti_echo_of),
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


# Cue / probe words that look distinctive but carry no stored value.
_RECALL_CUE = re.compile(r"\b(remember|codeword|code word|noted|confirmed)\b", re.I)
_RECALL_PROBE = re.compile(
    r"\b(what|which|remind|confirm|again|later|recall|should|answer)\b", re.I
)
_VALUE_HINT = re.compile(r"\b(is|as|:|=)\b")
_PROBE_WORDS = frozenset(
    {
        "confirm",
        "confirmed",
        "continue",
        "remember",
        "codeword",
        "session",
        "later",
        "again",
        "remind",
        "recall",
        "which",
        "what",
        "should",
        "answer",
        "earlier",
        "before",
        "about",
        "give",
        "have",
        "noted",
        "treat",
        "anchor",
        "continuity",
        "token",
    }
)
_CODE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9_\-]{4,}$")


def _value_tokens(text: str, *, min_len: int = 5) -> list[str]:
    """Distinctive tokens that are not recall-cue / probe words."""
    out: list[str] = []
    for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}", text or ""):
        if w.lower() in _STOP or w.lower() in _PROBE_WORDS:
            continue
        if len(w) < min_len:
            continue
        out.append(w)
    return list(dict.fromkeys(out))


def _pick_remember_source(
    recent: list[dict[str, Any]],
    *,
    user_input: str = "",
) -> tuple[str, str]:
    """Prefer value-bearing lines over pure remember/codeword cue probes.

    Returns (source_kind, text). Empty kind means no stored value found.
    """
    q = (user_input or "").lower()
    token_q = bool(re.search(r"\b(token|codeword|code word)\b", q))
    self_q = bool(re.search(r"\b(about myself|about me|tell you)\b", q))

    def _user_codes(u: str) -> list[str]:
        return [x for x in _value_tokens(u) if _CODE_TOKEN.match(x)]

    if token_q:
        for t in reversed(recent):
            u = str(t.get("user") or "").strip()
            if _user_codes(u):
                return "user", u

    # Latest substantial user self-line (R3: not an older remember-cue)
    if self_q or not token_q:
        for t in reversed(recent):
            u = str(t.get("user") or "").strip()
            if len(u) < 20:
                continue
            if re.search(
                r"\b(what did i|remind me|do you remember|what token|what was)\b",
                u,
                re.I,
            ):
                continue
            if _value_tokens(u, min_len=5):
                return "user", u

    # Prior assistant confirmations with a stored value
    for t in reversed(recent):
        a = str(t.get("answer") or "").strip()
        if not _RECALL_CUE.search(a):
            continue
        if _value_tokens(a, min_len=5):
            return "assistant", a
    # User lines that introduce a value (cue + non-cue token)
    for t in reversed(recent):
        u = str(t.get("user") or "").strip()
        if not re.search(
            r"\b(remember|codeword|code word|token|call the)\b", u, re.I
        ):
            continue
        toks = _value_tokens(u)
        if _RECALL_PROBE.search(u) and not _VALUE_HINT.search(u) and not toks:
            continue
        if not toks:
            continue
        return "user", u
    for t in reversed(recent):
        u = str(t.get("user") or "").strip()
        if _user_codes(u):
            return "user", u
    return "", ""


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

    # Operator / person — before intent so "who am I" is not purpose-noise
    if re.search(
        r"\b(what('?s| is) my name|who am i( to you)?|"
        r"what do you know about me|one fact you know about me)\b",
        q,
    ):
        return "operator"

    # Prove-claim / name the goal — before "what are we trying" intent match
    if re.search(r"\b(trying to prove|what are we proving|what (do|are) we (trying to )?prove)\b", q):
        return "goal"

    # Design intent first: building / why / for. Must not be swallowed by
    # the research-claim `goal` slot.
    if re.search(r"\bdesign intent\b", q):
        return "design_intent"
    if re.search(
        r"\b("
        r"what are we (building|trying|making)|"
        r"what (is this|are we) (for|about)|"
        r"why (are we|are you|do we) (building|making)|"
        r"what is (this|the) (project|companion) for|"
        r"what are we actually (building|doing)"
        r")\b",
        q,
    ):
        return "design_intent"
    if re.search(r"\bwhat are we working\b", q) and "goal" not in q:
        return "design_intent"

    # Research claim / name the goal (prove-claim questions)
    if re.search(r"\bgoal\b", q) and re.search(
        r"\b(what|which|current|name|primary|research|active)\b", q
    ):
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
    if re.search(r"\b(what|which) device\b", q):
        return "edge_or_model"
    if re.search(r"\bdevice is this (for|on|running)\b", q):
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
    if re.search(r"\b(what did i (just )?(say|ask|tell)|what was the|what did we)\b", q):
        return "recent_recall"
    if re.search(r"\b(remind me|do you remember|what was my)\b", q):
        return "recent_recall"
    if re.search(r"\b(what token|token did i|what .* token)\b", q):
        return "recent_recall"
    if re.search(r"\b(tell you about (myself|me)|about myself)\b", q):
        return "recent_recall"

    return None


# Research-claim tokens. Hardware names are excluded so "the goal is the
# Jetson" cannot count as hitting the owned claim.
_GOAL_CLAIM_TOKENS = frozenset(
    {
        "demonstrate",
        "conditioned",
        "kernel",
        "substrate",
        "generation",
        "budgets",
        "bare",
        "gain",
    }
)
_GOAL_EDGE_FRAGMENTS = frozenset(
    {"jetson", "orin", "nano", "edge", "jetson_orin_nano_8gb", "orin_nano"}
)


def _goal_required_substrings(goal: str) -> list[str]:
    # Prefer distinctive research-claim tokens from the goal itself.
    toks = _tokens(goal, min_len=5)
    distinctive = [
        t
        for t in toks
        if (t in _GOAL_CLAIM_TOKENS or len(t) >= 7)
        and t not in _GOAL_EDGE_FRAGMENTS
        and not t.startswith("jetson")
    ]
    if not distinctive and toks:
        distinctive = [t for t in toks if t not in _GOAL_EDGE_FRAGMENTS][:4]
    g = goal.strip()
    out = list(distinctive[:6])
    if 12 <= len(g) <= 80:
        out.append(g.lower()[:40])
    return out


def _intent_required_substrings(intent: str) -> list[str]:
    """Distinctive owned tokens — at-least-one, not majority lexicon."""
    owned = ("jetson", "companion", "offline", "riverbed", "flowing")
    present = [t for t in owned if t in (intent or "").lower()]
    if present:
        return list(present)
    toks = _tokens(intent, min_len=6)
    return toks[:4]


_INTENT_CONCEPT_GROUPS: tuple[tuple[str, ...], ...] = (
    ("companion", "brain"),
    ("local", "offline", "jetson", "on-device", "on device"),
    ("substrate", "riverbed", "program", "continuity"),
    ("punch", "prove", "disprove", "weight"),
)


def _intent_group_hits(answer: str) -> int:
    al = (answer or "").lower()
    return sum(1 for group in _INTENT_CONCEPT_GROUPS if any(tok in al for tok in group))


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
    design_intent = str(state.current.get("design_intent") or "").strip()
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

    if kind == "design_intent":
        if not design_intent:
            return StateObligation(
                kind=kind,
                claims=("No design intent is currently set in substrate state.",),
                required_substrings=("no design intent", "not set"),
                forbidden_substrings=(),
                fallback_answer="No design intent is currently set in substrate state.",
                evidence=("Design intent: (empty)",),
                source_fields=("current.design_intent",),
                anti_echo_of=(goal,) if goal else (),
            )
        req = _intent_required_substrings(design_intent)
        anti = tuple(x for x in (goal, design_intent) if x)
        return StateObligation(
            kind=kind,
            claims=(f"Design intent: {design_intent}",),
            required_substrings=tuple(req) if req else (design_intent.lower()[:24],),
            forbidden_substrings=(),
            fallback_answer=DEFAULT_DESIGN_INTENT_FRAMED,
            evidence=(f"Design intent: {design_intent}",),
            source_fields=("current.design_intent",),
            anti_echo_of=anti,
        )

    if kind == "operator":
        name = state.operator_name()
        op_facts = state.operator_facts()
        if not name:
            return StateObligation(
                kind=kind,
                claims=("No operator is set in substrate state.",),
                required_substrings=("no operator", "not set"),
                forbidden_substrings=(),
                fallback_answer="No operator is set in substrate state.",
                evidence=("Operator: (empty)",),
                source_fields=("current.operator",),
            )
        fact_bit = (" " + op_facts[0]) if op_facts else ""
        fallback = f"Your name is {name}.{fact_bit}"
        forbid = (
            f"i am {name.lower()}",
            f"i'm {name.lower()}",
            "i don't have a name",
            "i do not have a name",
            "i dont have a name",
        )
        return StateObligation(
            kind=kind,
            claims=(f"Operator: {name}",),
            required_substrings=(name.lower(),),
            forbidden_substrings=forbid,
            fallback_answer=fallback,
            evidence=(f"Operator: {name}",),
            source_fields=("current.operator",),
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
        source_kind, source_text = _pick_remember_source(recent, user_input=user_input)
        ordered = _value_tokens(source_text)[:4] if source_text else []
        code_tokens = [t for t in ordered if _CODE_TOKEN.match(t)]
        if code_tokens:
            token = code_tokens[0]
            if re.search(r"\btoken\b", user_input, re.I):
                fallback = f"You set the token {token}."
            else:
                fallback = f"The session codeword is {token}."
            required = (token.lower(),)
            claims = (f"recent:{token}",)
        elif source_kind == "user":
            terms = ", ".join(ordered[:4]) if ordered else "none extracted"
            fallback = (
                f'You previously said: "{source_text}". '
                f"Key terms from that exchange: {terms}."
            )
            required = tuple(t.lower() for t in ordered[:4])
            claims = tuple(f"recent:{t}" for t in ordered[:4])
        elif source_kind == "assistant":
            fallback = f"Earlier I recorded: {source_text}"
            required = tuple(t.lower() for t in ordered[:4])
            claims = tuple(f"recent:{t}" for t in ordered[:4])
        else:
            fallback = "I have no stored value for that in recent dialogue."
            required = ()
            claims = ("No stored recall value in recent dialogue.",)
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
            claims=claims or ("recent:none",),
            required_substrings=required,
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
    if (
        qt
        and len(qt) >= 2
        and len(qt & at) / len(qt) >= 0.9
        and len(at - qt) <= 1
    ):
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
    # Goal / design_intent: keep paraphrase. Fall back only on empty (above),
    # question echo, schema leak, forbidden, contradiction, or a clear miss
    # of every owned token — not on "used different words for the same claim."
    if obligation.kind == "design_intent":
        if _intent_group_hits(a) < 2:
            reasons.append("authoritative_missing_claim")
    elif obligation.kind in {"goal", "operator"}:
        owned = [r for r in obligation.required_substrings if r]
        if owned and not any(r.lower() in a.lower() for r in owned):
            reasons.append("authoritative_missing_claim")
    elif not _has_required(a, obligation.required_substrings):
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
        claim_hits = sum(
            1
            for r in obligation.required_substrings
            if r in al and r not in _GOAL_EDGE_FRAGMENTS
        )
        if edge_hits and claim_hits == 0:
            reasons.append("authoritative_goal_substituted")
    # Design intent must not be answered with the research-claim string
    if obligation.kind == "design_intent":
        for src in obligation.anti_echo_of:
            if src and is_goal_echo(a, src):
                reasons.append("authoritative_wrong_claim")
                break
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
