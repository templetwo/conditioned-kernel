"""Studio Flow mode: the living-field turn path.

This REPLACES the acceptance-court metaphor for the living conversational
path (`ck chat --mode flow`). The old path was:

    field -> model candidate -> validation court -> repair appeal -> accept/reject

Flow is:

    field before -> model speaks through field -> output reaches Anthony ->
    substrate observes what traveled -> field integrates and shifts -> next turn

Central requirement: the substrate should shift beneath and through the
model's speech. It should not become increasingly skilled at preventing the
model from speaking. Concretely, that means:

  * No candidate JSON schema, no `evidence_used` bookkeeping -- the kernel is
    asked for ordinary language and its `format`-free reply is what travels.
  * No accept/reject branch in the speech path -- every nonempty generation
    reaches the terminal. Only a genuine transport failure or an observed
    empty answer gets a plain, honest terminal message instead of silence.
  * Repetition, contradiction, project-language dominance, low
    responsiveness, and authoritative-topic disclosure are recorded as
    dashboard OBSERVATIONS on the `FlowTrace` -- never rejection reasons,
    never blocking, never mutating what was said.
  * Durable-state mutation (the field's own salience/momentum bookkeeping)
    happens strictly AFTER the exchange, in `integrate_field`, outside the
    conversational output path.

Persistence:
  * The field itself lives in `state/flow_field.json`, a file this module
    owns exclusively -- never `current.json` / `threads.json`. Those two
    stay companion/measurement state and this module never opens them for
    writing (see `state.py`'s `SubstrateState`, used here strictly
    read-only).
  * Each turn's `FlowTrace` is written to
    `<logs_dir>/dashboard/flow_turns/<turn_id>.json`, a sibling of (never
    the same store as) the companion/measurement dashboard's
    `dashboard/turns/` directory, so the observatory can serve it without
    the two turn/trace namespaces colliding.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Literal

from conditioned_kernel.authoritative_state import (
    StateObligation,
    check_obligation,
    resolve_obligation,
)
from conditioned_kernel.context_field import (
    ContextContribution,
    _is_boilerplate_assistant,
    _tags_match,
    collect_contributions,
    detect_intents,
)
from conditioned_kernel.edge import EdgeProfile, load_profile
from conditioned_kernel.generate import OllamaClient
from conditioned_kernel.ids import make_id, short_token, utc_now_iso
from conditioned_kernel.paths import default_logs_dir, default_state_dir
from conditioned_kernel.return_path.validate import _fact_contradictions, is_responsive
from conditioned_kernel.state import SubstrateState

FLOW_FIELD_SCHEMA = "ck.flow_field.v1"
FLOW_TRACE_SCHEMA = "ck.flow_trace.v1"
FLOW_FIELD_FILENAME = "flow_field.json"

ElementKind = Literal["topic", "canonical", "thread"]
ElementSource = Literal["human", "model", "canonical", "carried"]

# ---------------------------------------------------------------------------
# Tunables -- a small number of active field elements with salience,
# momentum, and decay (spec point 3). Every constant here exists to keep the
# field bounded and to make the decay/strengthen rules explicit, not to
# gate what the model is allowed to say.
# ---------------------------------------------------------------------------

MAX_ELEMENTS = 24                  # bounded carry across the whole field
MAX_LIVE_ELEMENTS_PER_TURN = 6     # "a small number of active field elements"
DEFAULT_FIELD_BYTE_BUDGET = 1400   # bounds carried elements only, never the current message
SALIENCE_FLOOR = 0.05
THREAD_SALIENCE_FLOOR = SALIENCE_FLOOR * 0.4  # unresolved threads get a lower eviction floor

DECAY_UNUSED_SELECTED = 0.55   # traveled into the prompt but nothing continued it
DECAY_UNUSED_DORMANT = 0.97    # not even selected this turn -- gentle fade
DECAY_THREAD_DORMANT = 0.99    # threads fade slower still (bounded carry, unresolved)
SOFTEN_FACTOR = 0.4            # extra decay for content repeated near-verbatim across turns
MOMENTUM_STEP = 0.18
MOMENTUM_DECAY = 0.5

NEW_TOPIC_SALIENCE = 0.5
NEW_CANONICAL_SALIENCE = 0.5
PROVISIONAL_CANONICAL_SALIENCE = NEW_CANONICAL_SALIENCE * 0.7  # before it has actually traveled
THREAD_CARRY_SALIENCE = 0.22

CONTINUATION_JACCARD = 0.12     # "genuinely continued" threshold
DUPLICATE_TOPIC_JACCARD = 0.55  # merge into an existing topic rather than duplicate it
REPEAT_VERBATIM_JACCARD = 0.6   # "repeated across turns" / stale-groove threshold

RECENT_REPLIES_KEPT = 3

FLOW_EMPTY_MESSAGE = "(the kernel had nothing to say this turn)"
FLOW_TRANSPORT_MESSAGE = "(could not reach the kernel this turn: {error})"

FLOW_SYSTEM_PROMPT = (
    "You are speaking directly with a person inside Conditioned Kernel's Flow mode. "
    "Answer in ordinary, natural language: plain prose, not JSON, not a list of "
    "citations, not a report. A short paragraph is usually enough. Speak as "
    "yourself, continuing the conversation; do not narrate what you are doing or "
    "describe your own process. Anything under 'Field context' below is context "
    "you may draw on if it is actually useful to what the person just said -- it "
    "is not a script to recite."
)


# ---------------------------------------------------------------------------
# Symmetric token similarity -- same formula as
# observatory.compute.jaccard_similarity (|A∩B| / |A∪B| over 4+-char
# lowercase tokens). Duplicated as a small pure function rather than
# imported: `ck chat --mode flow` is a core CLI path and should not pull in
# the dashboard package's import graph (return_path.accept/assess/parse/
# repair) for one formula. Keep this identical to compute.py's version.
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")


def _tokenize(text: str | None) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: str | None, b: str | None) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 0.0
    union = len(ta | tb)
    return (len(ta & tb) / union) if union else 0.0


def _atomic_write_json(path: Path, data: Any) -> None:
    """Same tempfile + fsync + os.replace convention as state.py's
    module-level helper, copied here so this module never imports from
    (or adds methods to) `SubstrateState` -- flow_field.json and the
    per-turn flow trace files are this module's own files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def flow_field_path(state_dir: Path) -> Path:
    return Path(state_dir) / FLOW_FIELD_FILENAME


def flow_trace_path(logs_dir: Path, turn_id: str) -> Path:
    return Path(logs_dir) / "dashboard" / "flow_turns" / f"{turn_id}.json"


def clear_flow_field(state_dir: Path) -> None:
    """`ck chat --mode flow --new-session`: remove flow_field.json only.

    Never touches current.json / threads.json -- those are companion /
    measurement state and out of bounds for this module.
    """
    path = flow_field_path(state_dir)
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# FlowElement / FlowField -- the living field itself.
# ---------------------------------------------------------------------------


@dataclass
class FlowElement:
    element_id: str
    kind: ElementKind
    content: str
    source: ElementSource
    salience: float
    momentum: float = 0.0
    topic_tags: tuple[str, ...] = ()
    created_at: str = ""
    last_active_at: str = ""
    turns_seen: int = 0
    repeat_streak: int = 0

    def score(self) -> float:
        return self.salience + self.momentum

    def bytes_len(self) -> int:
        return len((self.content or "").encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "kind": self.kind,
            "content": self.content,
            "source": self.source,
            "salience": round(self.salience, 4),
            "momentum": round(self.momentum, 4),
            "topic_tags": list(self.topic_tags),
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "turns_seen": self.turns_seen,
            "repeat_streak": self.repeat_streak,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowElement":
        return cls(
            element_id=str(d.get("element_id") or ""),
            kind=d.get("kind") or "topic",
            content=str(d.get("content") or ""),
            source=d.get("source") or "human",
            salience=float(d.get("salience") or 0.0),
            momentum=float(d.get("momentum") or 0.0),
            topic_tags=tuple(d.get("topic_tags") or ()),
            created_at=str(d.get("created_at") or ""),
            last_active_at=str(d.get("last_active_at") or ""),
            turns_seen=int(d.get("turns_seen") or 0),
            repeat_streak=int(d.get("repeat_streak") or 0),
        )


@dataclass
class FlowField:
    session_id: str
    elements: list[FlowElement] = dc_field(default_factory=list)
    recent_replies: list[str] = dc_field(default_factory=list)
    turn_count: int = 0
    updated_at: str = ""

    @classmethod
    def fresh(cls, session_id: str) -> "FlowField":
        return cls(session_id=session_id, updated_at=utc_now_iso())

    @classmethod
    def load(cls, path: Path, *, session_id: str) -> "FlowField":
        if not path.exists():
            return cls.fresh(session_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls.fresh(session_id)
        if not isinstance(data, dict):
            return cls.fresh(session_id)
        elements = [
            FlowElement.from_dict(e)
            for e in (data.get("elements") or [])
            if isinstance(e, dict)
        ]
        return cls(
            session_id=str(data.get("session_id") or session_id),
            elements=elements,
            recent_replies=[str(r) for r in (data.get("recent_replies") or [])],
            turn_count=int(data.get("turn_count") or 0),
            updated_at=str(data.get("updated_at") or ""),
        )

    def find(self, element_id: str) -> FlowElement | None:
        for e in self.elements:
            if e.element_id == element_id:
                return e
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FLOW_FIELD_SCHEMA,
            "session_id": self.session_id,
            "elements": [e.to_dict() for e in self.elements],
            "recent_replies": list(self.recent_replies),
            "turn_count": self.turn_count,
            "updated_at": self.updated_at,
        }

    def save(self, path: Path) -> None:
        self.updated_at = utc_now_iso()
        _atomic_write_json(path, self.to_dict())


# ---------------------------------------------------------------------------
# compose_field -- FIELD BEFORE. Current human message is always primary;
# a small number of live elements travel alongside it within a byte budget.
# Canonical durable state enters only when relevant to THIS message (reuses
# context_field.detect_intents / _tags_match -- never unconditionally).
# ---------------------------------------------------------------------------


@dataclass
class FieldBefore:
    current_message: str
    intents: tuple[str, ...]
    selected: list[dict[str, Any]]
    relevant_canonical: list[dict[str, Any]]
    candidate_pool_size: int
    live_element_count: int
    byte_budget: int
    selected_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_message": self.current_message,
            "intents": list(self.intents),
            "selected": self.selected,
            "relevant_canonical": self.relevant_canonical,
            "candidate_pool_size": self.candidate_pool_size,
            "live_element_count": self.live_element_count,
            "byte_budget": self.byte_budget,
            "selected_bytes": self.selected_bytes,
        }


def _canonical_contributions(
    state: SubstrateState, *, profile: EdgeProfile | None, model: str | None
) -> list[ContextContribution]:
    """Durable substrate state as candidate field content (goal / identity /
    runtime / policy). `user_input=""` is safe: none of these contribution
    kinds depend on it (only the `current_input` contribution does, and
    that kind is excluded here -- Flow gives the current message primacy
    directly, never through a contribution)."""
    available = collect_contributions(state, "", profile=profile, model=model)
    return [
        c
        for c in available
        if c.kind
        in {"goal", "design_intent", "person", "durable_fact", "runtime", "constraint"}
    ]


def _thread_contributions(
    state: SubstrateState, *, profile: EdgeProfile | None, model: str | None
) -> list[ContextContribution]:
    available = collect_contributions(state, "", profile=profile, model=model)
    return [c for c in available if c.kind == "thread"]


def compose_field(
    flow_field: FlowField,
    current_message: str,
    state: SubstrateState,
    *,
    profile: EdgeProfile | None = None,
    model: str | None = None,
    byte_budget: int = DEFAULT_FIELD_BYTE_BUDGET,
    max_live: int = MAX_LIVE_ELEMENTS_PER_TURN,
) -> FieldBefore:
    intents = detect_intents(current_message)
    canonical_avail = _canonical_contributions(state, profile=profile, model=model)
    thread_avail = _thread_contributions(state, profile=profile, model=model)
    relevant_canonical = [c for c in canonical_avail if _tags_match(c, intents)]

    tracked_ids = {e.element_id for e in flow_field.elements}
    candidates: list[FlowElement] = list(flow_field.elements)

    # Canonical state only becomes a field candidate when relevant to this
    # message -- provisional until integrate() decides it actually traveled.
    for c in relevant_canonical:
        eid = f"canonical:{c.contribution_id}"
        if eid in tracked_ids:
            continue
        candidates.append(
            FlowElement(
                element_id=eid,
                kind="canonical",
                content=c.content,
                source="canonical",
                salience=PROVISIONAL_CANONICAL_SALIENCE,
                topic_tags=c.topic_tags,
                created_at=utc_now_iso(),
            )
        )
        tracked_ids.add(eid)

    # Open threads: carried at low salience so they can win a slot when the
    # field is otherwise quiet, without being forced into every prompt.
    for c in thread_avail:
        eid = f"thread:{c.contribution_id}"
        if eid in tracked_ids:
            continue
        candidates.append(
            FlowElement(
                element_id=eid,
                kind="thread",
                content=c.content,
                source="carried",
                salience=THREAD_CARRY_SALIENCE,
                topic_tags=c.topic_tags,
                created_at=utc_now_iso(),
            )
        )
        tracked_ids.add(eid)

    candidates.sort(key=lambda e: (-(e.score()), -(e.turns_seen), e.element_id))

    selected: list[FlowElement] = []
    used_bytes = 0
    for e in candidates:
        if len(selected) >= max_live:
            break
        cost = e.bytes_len()
        if used_bytes + cost > byte_budget:
            continue
        selected.append(e)
        used_bytes += cost

    return FieldBefore(
        current_message=current_message,
        intents=tuple(sorted(intents)),
        selected=[e.to_dict() for e in selected],
        relevant_canonical=[c.to_dict() for c in relevant_canonical],
        candidate_pool_size=len(candidates),
        live_element_count=len(flow_field.elements),
        byte_budget=byte_budget,
        selected_bytes=used_bytes,
    )


# ---------------------------------------------------------------------------
# Prompt: conversational system text + field rendered as prose + the human
# message. No output schema, no evidence requirement (spec point 4).
# ---------------------------------------------------------------------------


def _render_field_prose(field_before: FieldBefore) -> str:
    if not field_before.selected:
        return "(Nothing else is active in the field right now.)"
    prefixes = {"canonical": "Standing context", "thread": "Still open", "topic": "Recently alive"}
    lines = [f"- {prefixes.get(e.get('kind'), 'Context')}: {e.get('content')}" for e in field_before.selected]
    return "\n".join(lines)


def build_flow_model_input(
    field_before: FieldBefore,
    *,
    model: str,
    keep_alive: str,
    think: bool,
    temperature: float,
    seed: int,
    num_ctx: int,
) -> dict[str, Any]:
    """Ollama chat_json payload with no `format` key -- free-text reply.
    Selected field content is prose, never a JSON blob, and the current
    human message is always its own labeled, unburied block."""
    user_content = (
        "## Field context\n"
        f"{_render_field_prose(field_before)}\n\n"
        "## The person just said\n"
        f"{field_before.current_message}\n"
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": FLOW_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "keep_alive": keep_alive,
        "think": bool(think),
        "options": {
            "temperature": temperature,
            "repeat_penalty": 1.1,
            "seed": seed,
            "num_ctx": num_ctx,
        },
    }
    return {"schema_version": "ck.flow.v1", "mode": "chat_json", "model": model, "payload": payload}


# ---------------------------------------------------------------------------
# Observations -- post-hoc, descriptive, never blocking (spec point 6).
# ---------------------------------------------------------------------------


@dataclass
class Observation:
    label: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "detail": self.detail}


def derive_flow_observations(
    *,
    reply: str | None,
    current_message: str,
    field_before: FieldBefore,
    prior_replies: list[str],
    obligation: StateObligation | None,
) -> list[Observation]:
    """Repetition, project-language dominance, low responsiveness,
    contradiction-with-canonical-state, and authoritative-topic disclosure.
    Every one of these is descriptive only -- none of them change
    `displayed_text`, none of them gate persistence."""
    obs: list[Observation] = []
    text = (reply or "").strip()

    if text and prior_replies:
        rep = max(_jaccard(text, p) for p in prior_replies if p.strip())
        if rep >= REPEAT_VERBATIM_JACCARD:
            obs.append(
                Observation(
                    "Repetition",
                    f"This reply shares {round(rep * 100)}% of its tokens with a recent "
                    "one (symmetric Jaccard over 4+-char tokens).",
                )
            )

    if text and _is_boilerplate_assistant(text):
        obs.append(
            Observation(
                "Project-language dominance",
                "The reply leans heavily on recirculated project-status phrasing "
                "rather than language shaped by this turn.",
            )
        )

    if text and current_message.strip() and not is_responsive(text, current_message):
        obs.append(
            Observation(
                "Low responsiveness",
                "validate.is_responsive did not find the reply engaging the current "
                "message's own terms. Signal only -- not enforced in Flow.",
            )
        )

    canonical_facts = [
        e.get("content", "") for e in field_before.selected if e.get("kind") == "canonical"
    ]
    if text and canonical_facts:
        pseudo_packet = {
            "acceptance_contract": {"must_not_contradict_facts": True},
            "facts": canonical_facts,
        }
        contradictions = _fact_contradictions(text, pseudo_packet)
        if contradictions:
            obs.append(
                Observation(
                    "Contradiction with canonical state",
                    "Mechanical check flagged: " + "; ".join(contradictions[:3]),
                )
            )

    if obligation is not None:
        if reply is None:
            detail = (
                f"This turn touched a canonical-state topic ({obligation.kind}) but no "
                "reply was observed -- claim preservation could not be checked."
            )
        else:
            reasons = check_obligation(text, obligation, current_message)
            detail = f"This turn touched a canonical-state topic ({obligation.kind}). " + (
                "The reply appears to preserve the canonical claims."
                if not reasons
                else f"Signal only, unenforced: {', '.join(reasons)}."
            )
        obs.append(Observation("Authoritative-topic disclosure", detail))

    return obs


# ---------------------------------------------------------------------------
# Integration -- happens AFTER the exchange, mutates the field, never the
# reply (spec point 8). Strengthen what continued; create new topics; decay
# unused elements (bounded carry); soften verbatim-repeated boilerplate;
# carry unresolved threads without forcing them into every prompt.
# ---------------------------------------------------------------------------


@dataclass
class IntegrationAction:
    element_id: str
    action: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"element_id": self.element_id, "action": self.action, "detail": self.detail}


def _topic_tags(text: str) -> tuple[str, ...]:
    return tuple(sorted(_tokenize(text))[:6])


def _make_topic_content(text: str, *, max_bytes: int = 220) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    encoded = t.encode("utf-8")
    if len(encoded) <= max_bytes:
        return t
    return encoded[: max_bytes - 1].decode("utf-8", errors="ignore").rstrip() + "…"


def _upsert_topic(
    flow_field: FlowField,
    *,
    content: str,
    source: ElementSource,
    tags: tuple[str, ...],
    now: str,
    actions: list[IntegrationAction],
) -> None:
    for el in flow_field.elements:
        if el.kind != "topic":
            continue
        if _jaccard(el.content, content) >= DUPLICATE_TOPIC_JACCARD:
            el.salience = min(1.0, el.salience + MOMENTUM_STEP)
            el.momentum = min(1.0, el.momentum + MOMENTUM_STEP)
            el.turns_seen += 1
            el.last_active_at = now
            actions.append(IntegrationAction(el.element_id, "strengthened", "topic recurred this turn"))
            return
    eid = f"topic:{source}:{short_token(4)}"
    flow_field.elements.append(
        FlowElement(
            element_id=eid,
            kind="topic",
            content=content,
            source=source,
            salience=NEW_TOPIC_SALIENCE,
            topic_tags=tags,
            created_at=now,
            last_active_at=now,
            turns_seen=1,
        )
    )
    actions.append(IntegrationAction(eid, "created", f"newly introduced topic from the {source} side"))


def integrate_field(
    flow_field: FlowField,
    *,
    field_before: FieldBefore,
    current_message: str,
    reply: str,
) -> list[IntegrationAction]:
    actions: list[IntegrationAction] = []
    now = utc_now_iso()
    selected_ids = {e["element_id"] for e in field_before.selected}

    # 1. Elements that traveled this turn: strengthen, soften, or decay.
    for snap in field_before.selected:
        eid = snap["element_id"]
        el = flow_field.find(eid)
        if el is None:
            continue  # provisional canonical/thread candidate -- handled in step 2/created lazily
        repeated_verbatim = bool(reply) and _jaccard(el.content, reply) >= REPEAT_VERBATIM_JACCARD
        continued = bool(reply) and (
            repeated_verbatim
            or _jaccard(el.content, reply) >= CONTINUATION_JACCARD
            or _jaccard(el.content, current_message) >= CONTINUATION_JACCARD
        )
        if repeated_verbatim and el.repeat_streak >= 1:
            el.salience = max(SALIENCE_FLOOR, el.salience * SOFTEN_FACTOR)
            el.momentum = 0.0
            el.repeat_streak += 1
            el.last_active_at = now
            actions.append(
                IntegrationAction(
                    eid, "softened", "repeated near-verbatim across consecutive turns; extra-decayed"
                )
            )
        elif continued:
            el.salience = min(1.0, el.salience + MOMENTUM_STEP)
            el.momentum = min(1.0, el.momentum + MOMENTUM_STEP)
            el.turns_seen += 1
            el.last_active_at = now
            el.repeat_streak = el.repeat_streak + 1 if repeated_verbatim else 0
            actions.append(IntegrationAction(eid, "strengthened", "content continued into this exchange"))
        else:
            decay = DECAY_THREAD_DORMANT if el.kind == "thread" else DECAY_UNUSED_SELECTED
            el.salience *= decay
            el.momentum *= MOMENTUM_DECAY
            el.repeat_streak = 0
            actions.append(IntegrationAction(eid, "decayed", "traveled into the field but nothing continued it"))

    # 2. Materialize canonical state that was relevant this turn but not yet tracked.
    tracked_ids = {e.element_id for e in flow_field.elements}
    for c in field_before.relevant_canonical:
        eid = f"canonical:{c['contribution_id']}"
        if eid in tracked_ids:
            continue
        flow_field.elements.append(
            FlowElement(
                element_id=eid,
                kind="canonical",
                content=c["content"],
                source="canonical",
                salience=NEW_CANONICAL_SALIENCE,
                topic_tags=tuple(c.get("topic_tags") or ()),
                created_at=now,
                last_active_at=now,
                turns_seen=1,
            )
        )
        tracked_ids.add(eid)
        actions.append(
            IntegrationAction(eid, "created", f"canonical state became relevant this turn ({c.get('source_key')})")
        )

    # 3. Passive decay for elements not even selected this turn (bounded carry).
    for el in flow_field.elements:
        if el.element_id in selected_ids:
            continue
        el.salience *= DECAY_THREAD_DORMANT if el.kind == "thread" else DECAY_UNUSED_DORMANT

    # 4. New topics from what was actually said -- human message, then reply
    #    only if it adds vocabulary beyond restating the message.
    human_topic = _make_topic_content(current_message)
    if human_topic:
        _upsert_topic(
            flow_field, content=human_topic, source="human", tags=_topic_tags(current_message), now=now, actions=actions
        )
    if reply and _jaccard(reply, current_message) < DUPLICATE_TOPIC_JACCARD:
        model_topic = _make_topic_content(reply)
        if model_topic:
            _upsert_topic(flow_field, content=model_topic, source="model", tags=_topic_tags(reply), now=now, actions=actions)

    # 5. Bounded carry: drop below floor, then cap total element count.
    keep: list[FlowElement] = []
    for el in flow_field.elements:
        floor = THREAD_SALIENCE_FLOOR if el.kind == "thread" else SALIENCE_FLOOR
        if el.salience < floor:
            actions.append(IntegrationAction(el.element_id, "dropped", "salience fell below the eviction floor"))
            continue
        keep.append(el)
    flow_field.elements = keep

    if len(flow_field.elements) > MAX_ELEMENTS:
        flow_field.elements.sort(key=lambda e: e.score(), reverse=True)
        for el in flow_field.elements[MAX_ELEMENTS:]:
            actions.append(IntegrationAction(el.element_id, "dropped", "bounded carry: field exceeded max element count"))
        flow_field.elements = flow_field.elements[:MAX_ELEMENTS]

    flow_field.recent_replies = (flow_field.recent_replies + [reply])[-RECENT_REPLIES_KEPT:]
    flow_field.turn_count += 1
    return actions


# ---------------------------------------------------------------------------
# FlowTrace -- turn id, timestamps, field_before, composed prompt, raw
# reply ("what traveled"), observations, integration_actions, field_after.
# JSON-serializable; persisted under a dashboard-compatible location.
# ---------------------------------------------------------------------------


@dataclass
class FlowTrace:
    turn_id: str
    session_id: str
    started_at: str
    completed_at: str
    user_input: str
    field_before: dict[str, Any]
    composed_prompt: dict[str, Any]
    raw_reply: str | None
    reply_status: str
    displayed_text: str
    observations: list[dict[str, Any]]
    integration_actions: list[dict[str, Any]]
    field_after: dict[str, Any]
    runtime_config: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FLOW_TRACE_SCHEMA,
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "user_input": self.user_input,
            "field_before": self.field_before,
            "composed_prompt": self.composed_prompt,
            "raw_reply": self.raw_reply,
            "reply_status": self.reply_status,
            "displayed_text": self.displayed_text,
            "observations": self.observations,
            "integration_actions": self.integration_actions,
            "field_after": self.field_after,
            "runtime_config": self.runtime_config,
            "error": self.error,
        }


@dataclass
class FlowResult:
    ok: bool
    displayed_text: str
    trace: FlowTrace


# ---------------------------------------------------------------------------
# run_flow_turn -- the orchestrator: compose -> generate -> display ->
# observe -> integrate -> persist. No validation court anywhere in here.
# ---------------------------------------------------------------------------


def run_flow_turn(
    user_input: str,
    *,
    model: str | None = None,
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    base_url: str = "http://127.0.0.1:11434",
    temperature: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    profile: EdgeProfile | None = None,
    profile_id: str | None = None,
    client: OllamaClient | None = None,
    dry_reply: str | None = None,
) -> FlowResult:
    """Run one Flow turn. `dry_reply` injects a reply without Ollama
    (offline test / smoke path, mirroring `pipeline.run_turn`'s
    `dry_candidate_text`)."""
    prof = profile or load_profile(profile_id)
    state_dir_p = Path(state_dir) if state_dir else default_state_dir()
    logs_dir_p = Path(logs_dir) if logs_dir else default_logs_dir()
    state = SubstrateState.load(state_dir=state_dir_p, logs_dir=logs_dir_p)
    session_id = str(state.current.get("session_id") or "sess_unknown")

    ff_path = flow_field_path(state_dir_p)
    flow_field = FlowField.load(ff_path, session_id=session_id)

    use_model = model or prof.model
    keep_alive_val = prof.keep_alive if keep_alive is None else keep_alive
    temperature_val = prof.temperature if temperature is None else temperature
    seed_val = prof.seed if seed is None else seed
    num_ctx_val = prof.num_ctx if num_ctx is None else num_ctx

    started = utc_now_iso()
    turn_id = make_id("flow")

    field_before = compose_field(flow_field, user_input, state, profile=prof, model=use_model)
    model_input = build_flow_model_input(
        field_before,
        model=use_model,
        keep_alive=keep_alive_val,
        think=bool(prof.think),
        temperature=temperature_val,
        seed=seed_val,
        num_ctx=num_ctx_val,
    )

    error: str | None = None
    if dry_reply is not None:
        reply: str | None = dry_reply
        reply_status = "dry_run"
    else:
        ollama = client or OllamaClient(base_url=base_url, timeout=prof.timeout_s)
        inference = ollama.run(model_input)
        reply_status = inference.status.value
        error = inference.error
        reply = inference.output if inference.observed else None

    if reply is None:
        displayed = FLOW_TRANSPORT_MESSAGE.format(error=error or reply_status)
        reply_for_trace: str | None = None
    elif not reply.strip():
        displayed = FLOW_EMPTY_MESSAGE
        reply_for_trace = ""
    else:
        displayed = reply.strip()
        reply_for_trace = displayed

    obligation = resolve_obligation(state, user_input, profile=prof, model=use_model)
    observations = derive_flow_observations(
        reply=reply_for_trace,
        current_message=user_input,
        field_before=field_before,
        prior_replies=list(flow_field.recent_replies),
        obligation=obligation,
    )

    integration_actions = integrate_field(
        flow_field,
        field_before=field_before,
        current_message=user_input,
        reply=reply_for_trace or "",
    )
    flow_field.save(ff_path)

    completed = utc_now_iso()
    trace = FlowTrace(
        turn_id=turn_id,
        session_id=session_id,
        started_at=started,
        completed_at=completed,
        user_input=user_input,
        field_before=field_before.to_dict(),
        composed_prompt={
            "system": model_input["payload"]["messages"][0]["content"],
            "user": model_input["payload"]["messages"][1]["content"],
            "model": use_model,
        },
        raw_reply=reply_for_trace,
        reply_status=reply_status,
        displayed_text=displayed,
        observations=[o.to_dict() for o in observations],
        integration_actions=[a.to_dict() for a in integration_actions],
        field_after=flow_field.to_dict(),
        runtime_config={
            "profile_id": prof.profile_id,
            "model": use_model,
            "temperature": temperature_val,
            "seed": seed_val,
            "num_ctx": num_ctx_val,
            "keep_alive": keep_alive_val,
            "think": bool(prof.think),
            "base_url": base_url,
        },
        error=error,
    )
    _atomic_write_json(flow_trace_path(logs_dir_p, turn_id), trace.to_dict())

    return FlowResult(ok=reply_for_trace is not None, displayed_text=displayed, trace=trace)
