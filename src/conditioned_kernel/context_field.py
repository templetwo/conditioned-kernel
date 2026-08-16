"""Typed context contributions and companion-field selection.

Studio structural cut: modules emit typed contributions; the substrate
selects a turn-specific inference field. Measurement mode does not use
this selection path (full deterministic fact set preserved in compile).

State may govern a turn without appearing as prose in that turn.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

from conditioned_kernel.edge import EdgeProfile
from conditioned_kernel.state import SubstrateState

Kind = Literal[
    "current_input",
    "recent_dialogue",
    "durable_fact",
    "goal",
    "design_intent",
    "person",
    "runtime",
    "constraint",
    "instruction",
    "schema",
    "thread",
]

Authority = Literal["informational", "authoritative", "instructional"]

Intent = Literal[
    "social",
    "purpose",
    "person",
    "runtime",
    "edge",
    "policy",
    "threads",
    "dialogue_followup",
    "open",
]


@dataclass(frozen=True)
class ContextContribution:
    contribution_id: str
    source_module: str
    source_key: str
    kind: Kind
    content: str
    authority: Authority
    topic_tags: tuple[str, ...]
    priority: int
    max_bytes: int
    always_include: bool = False

    def clipped(self) -> "ContextContribution":
        text = (self.content or "").strip()
        if len(text.encode("utf-8")) <= self.max_bytes:
            return self
        # Clip by characters as a byte budget approximation for display
        limit = max(16, self.max_bytes // 2)
        clipped = text[: limit - 1].rstrip() + "…"
        return ContextContribution(
            contribution_id=self.contribution_id,
            source_module=self.source_module,
            source_key=self.source_key,
            kind=self.kind,
            content=clipped,
            authority=self.authority,
            topic_tags=self.topic_tags,
            priority=self.priority,
            max_bytes=self.max_bytes,
            always_include=self.always_include,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["topic_tags"] = list(self.topic_tags)
        d["bytes"] = len((self.content or "").encode("utf-8"))
        return d


@dataclass(frozen=True)
class SelectionRecord:
    contribution_id: str
    selected: bool
    reason: str
    contribution: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contribution_id": self.contribution_id,
            "selected": self.selected,
            "reason": self.reason,
            "contribution": self.contribution,
        }


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str, min_len: int = 4) -> set[str]:
    return set(re.findall(rf"[a-z0-9]{{{min_len},}}", (s or "").lower()))


# Presence / affect is a structural class, not a prompt lookup table.
# Session-specific greets (e.g. "suuppp") are covered by short-form + elongated
# "sup" patterns; sentence-length experiential lines are covered by affect
# content, not by listing prior dashboard prompts. Bare first-person is NOT
# a class — it over-captures ordinary system reports (see tests).
_PRESENCE_GREETING = re.compile(
    r"\b(hi|hello|hey|sup+|suup+|yo|thanks|thank you|bye|goodbye|goodby|"
    r"are you there|you there|how are you)\b"
)
# "ok"/"okay"/"cool" only read as presence when they carry the whole short
# utterance. Line-start position alone does not separate them: "ok" opens
# both "ok" and "ok the manifest is ratified now". Length does.
_SHORT_ACK = frozenset({"ok", "okay", "cool"})
_STRIP_PUNCT = ".,!?;:'\""
_AFFECT_CONTENT = re.compile(
    r"\b("
    r"miss|sad|lonely|tired|exhausted|drained|stressed|anxious|afraid|scared|"
    r"angry|upset|hurt|grieving|heartbroken|overwhelmed|depressed|hopeless|"
    r"numb|empty|worried|nervous|frustrated|grateful|thankful|proud|relieved|"
    r"peaceful|burnt|burned|worn|fed up|"
    # Appreciative/awe register. The list above is heavy on grief and
    # exhaustion and was blind to delight, so warmth met a project dump.
    r"wow+|whoa+|awesome|awwsome|amazing|remarkable|incredible|breathtaking|"
    r"breathetaking|beautiful|love (it|this|that)|i feel like|sit with (you|this|it)|"
    r"hard day|rough (day|night|shift|week)|long day|"
    r"burnt out|burned out|worn out|"
    r"love you|hate (this|that|it|ai|myself)"
    r")\b"
)
# Some affect words double as ordinary systems vocabulary: a cache "miss",
# an "empty" queue, a "drained" retry budget, a test that "hurt" the run.
# The veto fires only when EVERY affect hit in the line is one of these AND
# a system noun co-occurs — so "the queue is empty and im exhausted" still
# reads as affect on the strength of "exhausted".
_AMBIGUOUS_AFFECT_WORDS = frozenset({"miss", "empty", "drained", "hurt", "worn", "tired"})
_SYSTEM_NOUN = re.compile(
    r"\b(cache|queue|budget|run|test|build|session|dashboard|retry|thread|"
    r"commit|branch|pipeline|deploy|server|log|node|config|manifest|matrix|"
    r"restart)\b"
)
# Verb-initial terse directives ("merge", "check the commits", "build it",
# "approved") are instructions to act, not ambient presence. Checked against
# words[0] only, so a line that merely mentions the verb later is untouched.
_TERSE_DIRECTIVE_VERBS = frozenset(
    {
        "merge", "do", "go", "continue", "check", "build", "audit", "approved",
        "armed", "run", "deploy", "apply", "confirm", "approve", "arm", "stop",
        "execute", "revert", "retry", "commit", "push", "sync", "pull", "ship",
        "restart", "resume", "pause", "proceed", "take", "lets", "let's",
    }
)
# A gratitude or greeting particle stays presence even in a long line —
# unless the line also carries an action. "thank you very much for your time"
# is presence; "thank you now call the stack and log the moment" is an order.
_DIRECTIVE_ANYWHERE = _TERSE_DIRECTIVE_VERBS | {
    "call", "log", "add", "publish", "send", "update", "switch", "breakdown",
    "record", "write", "fix", "make", "put", "set", "install", "fetch",
}
_TASK_OR_INQUIRY = re.compile(
    r"\b("
    r"write|code|implement|fix|debug|explain|summarize|list|define|generate|"
    r"create|show me|tell me about|help me (with|to)|"
    r"how (do|does|to|can|would|should)|what (is|are|was|were|do|does|did|should|would)|"
    r"which|why (is|are|do|does|did|would|should)|when (is|are|do|does|did)|"
    r"where (is|are|do|does|did)|who (is|are|was|were)|"
    r"calculate|compute|script|function|loop|program"
    r")\b"
)
_TASKY_WANT = re.compile(
    r"\b(i (need|want|would like)|can you|could you|please)\b"
)
_TASK_OBJECT = re.compile(
    r"\b(code|script|function|loop|file|program|snippet|example|command|"
    r"help (me )?(with|to)|you to)\b"
)


def _is_presence_checkin(q: str) -> bool:
    return bool(
        re.search(
            r"\b(how are you|you there|are you (there|ok|okay)|right\?|you know\?)\b",
            q,
        )
    )


def _has_wh_inquiry(words: list[str]) -> bool:
    """True for WH-shaped tokens including contractions (what's, how's)."""
    for w in words:
        base = w.split("'")[0]
        if base in {"what", "which", "who", "whom", "whose", "when", "where", "why", "how"}:
            return True
    return False


def _is_task_or_inquiry(q: str, words: list[str]) -> bool:
    """True when the line is asking the system to do/explain something.

    Presence check-ins that look like questions ("how are you") stay social.
    """
    if _is_presence_checkin(q):
        return False
    if _TASK_OR_INQUIRY.search(q):
        return True
    if _has_wh_inquiry(words) and not _is_presence_checkin(q):
        # "so what's next", "how does that look…" are generative, not affect.
        return True
    if q.endswith("?") and not _is_presence_checkin(q):
        # Open questions are generative, not presence-affect.
        return True
    if _TASKY_WANT.search(q) and _TASK_OBJECT.search(q):
        return True
    # Imperative openers common in companion use
    if words and words[0] in {
        "write",
        "code",
        "implement",
        "fix",
        "debug",
        "explain",
        "summarize",
        "list",
        "define",
        "generate",
        "create",
        "show",
        "make",
    }:
        return True
    return False


def _is_presence_or_affect(q: str, words: list[str]) -> bool:
    """Structural presence/affect — generalizes past short greetings.

    Classes (any one is enough, provided the line is not a task/inquiry):
      1. greeting / check-in / thanks / goodbye
      2. affect content (experiential predicates, situation-of-day)
      3. very short non-question non-memory lines (ambient presence)
      4. light social particles without system inquiry

    Bare first-person (i/me/my) is deliberately NOT a class by itself —
    it over-captures ordinary system reports (\"my session keeps losing
    the thread state\"). First-person affect is covered when the line also
    carries affect content (\"i miss my grandmother\", \"i'm exhausted\").
    """
    if _is_task_or_inquiry(q, words):
        return False
    # A greeting particle only carries the turn when it IS the turn. "thanks"
    # is presence; "thank you now call the stack and log the moment" is a
    # directive wearing a greeting, and withholding state there makes the
    # companion go quiet on an instruction.
    if _PRESENCE_GREETING.search(q) and not (
        len(words) > 5 and _DIRECTIVE_ANYWHERE.intersection(words)
    ):
        return True
    first = words[0].strip(_STRIP_PUNCT) if words else ""
    if first in _SHORT_ACK and len(words) <= 2:
        return True
    hits = [m.group(1) for m in _AFFECT_CONTENT.finditer(q)]
    if hits:
        # Vetoed only if every hit is ambiguous and the line names a system noun.
        if not (all(h in _AMBIGUOUS_AFFECT_WORDS for h in hits) and _SYSTEM_NOUN.search(q)):
            return True
    if (
        len(words) <= 3
        and not q.endswith("?")
        and "what" not in words
        and "remember" not in words
        and "codeword" not in words
        and first not in _TERSE_DIRECTIVE_VERBS
    ):
        return True
    # Light social particles without system inquiry (kept general).
    if re.search(r"\b(man |really|dont|don't)\b", q) and len(words) <= 10:
        return True
    return False


def detect_intents(user_input: str) -> frozenset[Intent]:
    """General intent tags for selection — not a prompt lookup table."""
    q = _norm(user_input)
    if not q:
        return frozenset({"social"})

    intents: set[Intent] = set()
    words = q.split()

    # Purpose / what is this system
    if re.search(
        r"\b(what (does|is) (this|the) (system|project|kernel)|what do you do|"
        r"what is conditioned|what makes (this|it) different|purpose|design intent|"
        r"what are we (building|trying)|how (does|do) (this|you) work)\b",
        q,
    ):
        intents.add("purpose")

    if re.search(r"\b(goal|thesis|substrate gain)\b", q) and re.search(
        r"\b(what|which|current|our)\b", q
    ):
        intents.add("purpose")

    # Person / operator (name, who am I, facts about the human)
    if re.search(
        r"\b(my name|who am i|about me|know about me|who am i to you|"
        r"one fact you know)\b",
        q,
    ):
        intents.add("person")

    # Runtime / model
    if re.search(
        r"\b(what model|which model|active model|model (is|are) (this|you)|"
        r"profile|thinking|think false|runtime)\b",
        q,
    ):
        intents.add("runtime")

    # Edge / hardware
    if re.search(
        r"\b(jetson|orin|edge target|edge device|board|hardware|nano 8|"
        r"which board|running on|what device|which device)\b",
        q,
    ):
        intents.add("edge")

    # Policy
    if re.search(r"\b(cloud|sensors?|local[- ]only|tools? allowed|fully local)\b", q):
        intents.add("policy")

    # Threads
    if re.search(r"\b(open threads?|current threads?|thread_)\b", q):
        intents.add("threads")

    # Social / presence / affect (no system inquiry). System intents win:
    # "i feel like this system isn't doing much — what does this kernel do?"
    # must stay purpose, not collapse to social-only.
    system_intents = intents.intersection(
        {"purpose", "person", "runtime", "edge", "policy", "threads"}
    )
    if not system_intents and _is_presence_or_affect(q, words):
        intents.add("social")

    # Follow-up continuity (short reaction after dialogue exists)
    if len(words) <= 6 and re.search(
        r"\b(and|also|then|why|how|dont|don't|really|more|again|that|"
        r"this|what about|go on|continue)\b",
        q,
    ):
        intents.add("dialogue_followup")

    if not intents:
        intents.add("open")

    return frozenset(intents)


def collect_contributions(
    state: SubstrateState,
    user_input: str,
    *,
    profile: EdgeProfile | None = None,
    model: str | None = None,
) -> list[ContextContribution]:
    """Emit typed contributions from substrate state (available set)."""
    out: list[ContextContribution] = []
    flags = state.current.get("flags") or {}
    edge = str(flags.get("edge_target") or "jetson_orin_nano_8gb")
    goal = str(state.current.get("goal") or "").strip()
    design_intent = str(state.current.get("design_intent") or "").strip()
    active_profile = str(state.current.get("active_profile") or "orin_nano_8gb")
    use_model = model or (profile.model if profile else "qwen3.5:0.8b")
    think = bool(profile.think) if profile is not None else False
    cloud = bool(flags.get("cloud", False))
    sensors = bool(flags.get("sensors", False))
    tools = bool(flags.get("tools", False))
    max_repair = int(flags.get("max_repair_passes") or (profile.max_repair if profile else 1))

    out.append(
        ContextContribution(
            contribution_id="input.current",
            source_module="cli",
            source_key="user_input",
            kind="current_input",
            content=str(user_input or "").strip(),
            authority="authoritative",
            topic_tags=("input",),
            priority=0,
            max_bytes=800,
            always_include=True,
        )
    )

    name = state.operator_name()
    if name:
        facts = state.operator_facts()
        fact_bit = ("; " + "; ".join(facts)) if facts else ""
        out.append(
            ContextContribution(
                contribution_id="state.operator",
                source_module="state",
                source_key="current.operator",
                kind="person",
                content=f"Operator: {name}{fact_bit}.",
                authority="authoritative",
                topic_tags=("person", "operator", "identity"),
                priority=12,
                max_bytes=240,
            )
        )

    if design_intent:
        out.append(
            ContextContribution(
                contribution_id="state.design_intent",
                source_module="state",
                source_key="current.design_intent",
                kind="design_intent",
                content=f"Design intent: {design_intent}",
                authority="informational",
                topic_tags=("purpose", "intent", "design", "project"),
                priority=15,
                max_bytes=420,
            )
        )

    if goal:
        out.append(
            ContextContribution(
                contribution_id="state.goal",
                source_module="state",
                source_key="current.goal",
                kind="goal",
                content=f"Project purpose: {goal}",
                authority="informational",
                topic_tags=("purpose", "goal", "project"),
                priority=20,
                max_bytes=320,
            )
        )

    out.append(
        ContextContribution(
            contribution_id="state.identity",
            source_module="state",
            source_key="identity.transducer",
            kind="durable_fact",
            content=(
                "Conditioned Kernel: the model is a replaceable linguistic transducer; "
                "continuity and constraints live in the local substrate around it."
            ),
            authority="informational",
            topic_tags=("purpose", "identity", "project"),
            priority=25,
            max_bytes=280,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.policy.local",
            source_module="state",
            source_key="flags.cloud",
            kind="constraint",
            content=(
                "Operation is fully local-only; cloud services are not allowed."
                if not cloud
                else "Cloud services are enabled in this configuration."
            ),
            authority="authoritative",
            topic_tags=("policy", "cloud", "local"),
            priority=30,
            max_bytes=160,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.policy.sensors",
            source_module="state",
            source_key="flags.sensors",
            kind="constraint",
            content=(
                "Sensors are out of scope for v0."
                if not sensors
                else "Sensors are enabled."
            ),
            authority="informational",
            topic_tags=("policy", "sensors"),
            priority=40,
            max_bytes=120,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.policy.tools",
            source_module="state",
            source_key="flags.tools",
            kind="constraint",
            content=(
                "Autonomous tools are out of scope for v0."
                if not tools
                else "Tools are enabled."
            ),
            authority="informational",
            topic_tags=("policy", "tools"),
            priority=45,
            max_bytes=120,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.runtime.model",
            source_module="edge",
            source_key="profile.model",
            kind="runtime",
            content=f"Active model: {use_model}.",
            authority="authoritative",
            topic_tags=("runtime", "model"),
            priority=15,
            max_bytes=120,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.runtime.profile",
            source_module="edge",
            source_key="profile.profile_id",
            kind="runtime",
            content=f"Active edge profile: {active_profile} (think={think}).",
            authority="informational",
            topic_tags=("runtime", "profile"),
            priority=18,
            max_bytes=140,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.edge.target",
            source_module="state",
            source_key="flags.edge_target",
            kind="runtime",
            content=(
                f"Edge target: {edge} (one model at a time)."
                if flags.get("one_model_only", True)
                else f"Edge target: {edge}."
            ),
            authority="informational",
            topic_tags=("edge", "hardware", "jetson", "orin"),
            priority=22,
            max_bytes=160,
        )
    )

    out.append(
        ContextContribution(
            contribution_id="state.runtime.repair_budget",
            source_module="state",
            source_key="flags.max_repair_passes",
            kind="constraint",
            content=f"One repair pass is allowed (max={max_repair}).",
            authority="informational",
            topic_tags=("repair", "runtime", "experiment"),
            priority=50,
            max_bytes=100,
        )
    )

    for t in state.open_threads():
        tid = str(t.get("id") or "")
        title = str(t.get("title") or "")
        if not tid and not title:
            continue
        out.append(
            ContextContribution(
                contribution_id=f"state.thread.{tid or 'unknown'}",
                source_module="state",
                source_key=f"threads[{tid}]",
                kind="thread",
                content=f"Open thread {tid}: {title}".strip(),
                authority="informational",
                topic_tags=("threads", "experiment", tid.lower()),
                priority=55,
                max_bytes=200,
            )
        )

    # Recent dialogue as individual contributions (storage remains a ring)
    recent = list(state.recent_turns() or [])
    for i, turn in enumerate(recent):
        if not isinstance(turn, dict):
            continue
        u = str(turn.get("user") or "").strip()
        a = str(turn.get("answer") or "").strip()
        if not u and not a:
            continue
        body = f"User: {u}\nAssistant: {a}".strip()
        out.append(
            ContextContribution(
                contribution_id=f"dialogue.turn_{i}",
                source_module="state",
                source_key=f"recent_turns[{i}]",
                kind="recent_dialogue",
                content=body,
                authority="informational",
                topic_tags=("dialogue",) + tuple(sorted(_tokens(u + " " + a, 5))[:6]),
                priority=10 + (len(recent) - i),  # newer slightly higher
                max_bytes=400,
            )
        )

    return out


def _tags_match(contrib: ContextContribution, intents: frozenset[Intent]) -> bool:
    tags = set(contrib.topic_tags)
    if "purpose" in intents and tags & {
        "purpose",
        "goal",
        "project",
        "identity",
        "intent",
        "design",
    }:
        return True
    if "person" in intents and tags & {"person", "operator", "identity"}:
        return True
    if "runtime" in intents and tags & {"runtime", "model", "profile"}:
        return True
    if "edge" in intents and tags & {"edge", "hardware", "jetson", "orin"}:
        return True
    if "policy" in intents and tags & {"policy", "cloud", "local", "sensors", "tools"}:
        return True
    if "threads" in intents and tags & {"threads", "experiment"}:
        return True
    return False


def _is_boilerplate_assistant(text: str) -> bool:
    """Detect recirculated project-status narration in prior assistant answers."""
    t = _norm(text)
    hits = 0
    for phrase in (
        "fully local",
        "replaceable linguistic transducer",
        "jetson orin",
        "edge target",
        "substrate gain",
        "sensors are out of scope",
        "one repair pass",
        "conditioned-kernel",
    ):
        if phrase in t:
            hits += 1
    return hits >= 3


def select_contributions(
    available: Sequence[ContextContribution],
    user_input: str,
    *,
    max_selected_bytes: int = 1800,
) -> tuple[list[ContextContribution], list[SelectionRecord]]:
    """Select a turn-specific companion field from available contributions."""
    intents = detect_intents(user_input)
    records: list[SelectionRecord] = []
    selected: list[ContextContribution] = []

    # Dedup near-identical assistant boilerplate in dialogue contributions
    seen_assistant: list[str] = []

    def try_select(c: ContextContribution, reason: str) -> None:
        nonlocal selected
        clipped = c.clipped()
        cost = len(clipped.content.encode("utf-8"))
        used = sum(len(x.content.encode("utf-8")) for x in selected)
        if used + cost > max_selected_bytes and not c.always_include:
            records.append(
                SelectionRecord(
                    contribution_id=c.contribution_id,
                    selected=False,
                    reason=f"omitted_byte_budget:{reason}",
                    contribution=clipped.to_dict(),
                )
            )
            return
        selected.append(clipped)
        records.append(
            SelectionRecord(
                contribution_id=c.contribution_id,
                selected=True,
                reason=reason,
                contribution=clipped.to_dict(),
            )
        )

    # Always: current input (tracked; also placed as final model block)
    for c in available:
        if c.kind == "current_input":
            try_select(c, "always_current_input")

    social_only = intents <= frozenset({"social", "dialogue_followup"}) or intents == frozenset(
        {"social"}
    )
    openish = "open" in intents and not intents.intersection(
        {"purpose", "runtime", "edge", "policy", "threads"}
    )

    for c in available:
        if c.kind == "current_input":
            continue

        if c.kind == "recent_dialogue":
            dialogue = [x for x in available if x.kind == "recent_dialogue"]
            latest_id = (
                max(dialogue, key=lambda x: x.priority).contribution_id if dialogue else ""
            )
            is_latest = c.contribution_id == latest_id

            asst = ""
            if "Assistant:" in c.content:
                asst = c.content.split("Assistant:", 1)[-1].strip()
            if asst and any(_norm(asst) == _norm(p) or _norm(asst)[:60] == _norm(p)[:60] for p in seen_assistant):
                records.append(
                    SelectionRecord(
                        contribution_id=c.contribution_id,
                        selected=False,
                        reason="omitted_duplicate_assistant_boilerplate",
                        contribution=c.clipped().to_dict(),
                    )
                )
                continue
            if asst and _is_boilerplate_assistant(asst) and not (
                "purpose" in intents or "dialogue_followup" in intents
            ):
                # Don't recirculate status monologue into unrelated turns
                if not is_latest or social_only or openish:
                    records.append(
                        SelectionRecord(
                            contribution_id=c.contribution_id,
                            selected=False,
                            reason="omitted_stale_assistant_boilerplate",
                            contribution=c.clipped().to_dict(),
                        )
                    )
                    continue

            if "dialogue_followup" in intents and is_latest:
                try_select(c, "selected_followup_recent_turn")
                if asst:
                    seen_assistant.append(asst)
                continue

            # Relevance: overlap with user tokens
            ut = _tokens(user_input, 4)
            ct = _tokens(c.content, 4)
            overlap = len(ut & ct)
            if overlap >= 2 and not social_only:
                try_select(c, f"selected_dialogue_relevance_overlap={overlap}")
                if asst:
                    seen_assistant.append(asst)
                continue

            if is_latest and not social_only and "open" in intents:
                try_select(c, "selected_latest_dialogue_open_turn")
                if asst:
                    seen_assistant.append(asst)
                continue

            records.append(
                SelectionRecord(
                    contribution_id=c.contribution_id,
                    selected=False,
                    reason="omitted_dialogue_not_relevant",
                    contribution=c.clipped().to_dict(),
                )
            )
            continue

        # Social / presence: withhold project narration
        if social_only:
            records.append(
                SelectionRecord(
                    contribution_id=c.contribution_id,
                    selected=False,
                    reason="omitted_social_turn_withhold_project_state",
                    contribution=c.clipped().to_dict(),
                )
            )
            continue

        # Tag match against intents
        if _tags_match(c, intents):
            # Avoid experimental threads unless threads intent
            if c.kind == "thread" and "threads" not in intents:
                records.append(
                    SelectionRecord(
                        contribution_id=c.contribution_id,
                        selected=False,
                        reason="omitted_thread_not_requested",
                        contribution=c.clipped().to_dict(),
                    )
                )
                continue
            if c.contribution_id.endswith("repair_budget") and "runtime" not in intents:
                records.append(
                    SelectionRecord(
                        contribution_id=c.contribution_id,
                        selected=False,
                        reason="omitted_repair_budget_not_relevant",
                        contribution=c.clipped().to_dict(),
                    )
                )
                continue
            try_select(c, f"selected_intent_match:{','.join(sorted(intents))}")
            continue

        # Open generative: only minimal identity, not full hardware report
        if openish or "open" in intents:
            if c.contribution_id in {"state.identity"} and "purpose" not in intents:
                # still withhold unless purpose — open chat stays quiet
                records.append(
                    SelectionRecord(
                        contribution_id=c.contribution_id,
                        selected=False,
                        reason="omitted_open_turn_quiet_substrate",
                        contribution=c.clipped().to_dict(),
                    )
                )
                continue

        records.append(
            SelectionRecord(
                contribution_id=c.contribution_id,
                selected=False,
                reason="omitted_not_selected_for_turn",
                contribution=c.clipped().to_dict(),
            )
        )

    # Stable order: by priority then id
    selected.sort(key=lambda c: (c.priority, c.contribution_id))
    return selected, records


def build_context_field_record(
    available: Sequence[ContextContribution],
    selected: Sequence[ContextContribution],
    records: Sequence[SelectionRecord],
) -> dict[str, Any]:
    """Dashboard-facing selection map.

    Compact by design: full `available` content is not re-embedded (byte budget).
    Selected contributions include content; omitted rows are id/kind/reason only.
    """
    selected_ids = {c.contribution_id for c in selected}
    omitted_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    for r in records:
        base = {
            "contribution_id": r.contribution_id,
            "selected": r.selected,
            "reason": r.reason,
        }
        contrib = r.contribution if isinstance(r.contribution, dict) else {}
        base["kind"] = contrib.get("kind")
        base["source_module"] = contrib.get("source_module")
        base["source_key"] = contrib.get("source_key")
        base["authority"] = contrib.get("authority")
        if r.selected:
            base["content"] = contrib.get("content")
            base["bytes"] = contrib.get("bytes")
        selection_rows.append(base)
        if not r.selected:
            omitted_rows.append(base)
    return {
        "schema": "ck.context_field.v1",
        "available_count": len(available),
        "selected_count": len(selected),
        "omitted_count": len(omitted_rows),
        # available: ids only (full inventory without re-narrating content)
        "available": [
            {
                "contribution_id": c.contribution_id,
                "kind": c.kind,
                "source_module": c.source_module,
                "source_key": c.source_key,
                "topic_tags": list(c.topic_tags),
            }
            for c in available
        ],
        "selected": [c.to_dict() for c in selected],
        "omitted": omitted_rows,
        "selection_records": selection_rows,
        "selected_ids": sorted(selected_ids),
    }


def selected_facts(selected: Sequence[ContextContribution]) -> list[str]:
    """Prose lines for packet.facts from selected non-dialogue contributions."""
    lines: list[str] = []
    for c in selected:
        if c.kind in {
            "durable_fact",
            "goal",
            "design_intent",
            "person",
            "runtime",
            "constraint",
        }:
            lines.append(c.content)
        elif c.kind == "thread":
            lines.append(c.content)
    return lines


def selected_recent_turns(selected: Sequence[ContextContribution]) -> list[dict[str, str]]:
    """Rebuild recent_turns list from selected dialogue contributions."""
    turns: list[dict[str, str]] = []
    for c in selected:
        if c.kind != "recent_dialogue":
            continue
        user = ""
        answer = ""
        if "User:" in c.content:
            parts = c.content.split("Assistant:", 1)
            user = parts[0].replace("User:", "", 1).strip()
            if len(parts) > 1:
                answer = parts[1].strip()
        else:
            answer = c.content
        turns.append({"user": user, "answer": answer})
    return turns


def selected_open_threads(selected: Sequence[ContextContribution]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for c in selected:
        if c.kind != "thread":
            continue
        # "Open thread tid: title"
        m = re.match(r"Open thread ([^:]+):\s*(.*)$", c.content)
        if m:
            out.append({"id": m.group(1).strip(), "title": m.group(2).strip()})
        else:
            out.append({"id": c.source_key, "title": c.content})
    return out


def evidence_pool_from_selected(selected: Sequence[ContextContribution]) -> list[str]:
    """Evidence strings the companion validator may accept for this turn."""
    pool: list[str] = []
    for c in selected:
        if c.kind in {
            "durable_fact",
            "goal",
            "design_intent",
            "person",
            "runtime",
            "constraint",
            "thread",
        }:
            pool.append(c.content)
        if c.kind == "recent_dialogue":
            if "User:" in c.content:
                u = c.content.split("Assistant:", 1)[0].replace("User:", "", 1).strip()
                if u:
                    pool.append(u)
            if "Assistant:" in c.content:
                a = c.content.split("Assistant:", 1)[-1].strip()
                if a:
                    pool.append(a)
    return pool


def companion_system_text(*, social: bool) -> str:
    if social:
        return (
            "You are a local conversational presence for Conditioned Kernel. "
            "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
            "answer: a brief natural reply to the current human message. "
            "evidence_used: [] unless the context block supplies lines to cite. "
            "next_state.thread_touch: []. "
            "Do not invent project status, hardware specs, or prior goals. "
            "No files, URLs, tools, or cloud."
        )
    return (
        "You are a local Conditioned Kernel companion. "
        "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
        "answer: short helpful reply to the current human message. "
        "Use only the Selected context block when grounding claims. "
        "evidence_used: copy strings from Selected context or []. "
        "next_state.thread_touch: real open thread ids from context or []. "
        "Do not invent hardware, goals, or policies not present in Selected context. "
        "No files, URLs, tools, or cloud."
    )
