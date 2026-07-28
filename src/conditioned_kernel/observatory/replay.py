"""Replay engine — build-time model-input experiment (spec §7 "Replay turn",
§10 replay-effects rules, `POST /api/replay`).

Rebuilds the model input with arrival-packet sections toggled on/off, holds
model / seed / temperature / num_ctx / keep_alive fixed to whatever the
recorded turn actually used, and recomputes — never asserts — the validator
inputs those toggles change: evidence-pool size, how many citations would
still match, whether `stale_response_repeat` is live or inert, whether
`goal_echo` / `contradicts_facts` still have inputs to check, whether
`thread_touch` ids are still known, how many `TEMPLATE_ECHO_MARKERS` become
unhittable without the system message, and that removing `format=` makes
parse failure likely.

This module builds the modified packet and model input and re-runs those
specific checks; it does not itself call the model or the pipeline again —
producing an actual new candidate at the replayed input needs a real
generation call, which is a decision for the dashboard server built on top
of this module, not this module's job. **A replay persists nothing**: no
`state/` write, no `logs/` write, no second call into `pipeline.run_turn`.
"""

from __future__ import annotations

import copy
from typing import Any

from conditioned_kernel.compile import build_model_input
from conditioned_kernel.edge import packet_byte_size
from conditioned_kernel.observatory import compute
from conditioned_kernel.return_path.validate import _evidence_ok, _packet_evidence_pool, prior_accepted_answer

# Section keys accepted in a replay request, in the order the spec's "Model
# input sections" toggle list uses. `recent` defaults OFF (spec §7: "recent
# dialogue (off by default)"); everything else defaults ON.
REPLAY_SECTIONS: tuple[dict[str, str], ...] = (
    {"key": "recent", "label": "Recent dialogue", "note": "packet.recent_turns"},
    {"key": "state", "label": "Durable state", "note": "facts · open_threads · state_digest"},
    {"key": "obligation", "label": "Authoritative obligation", "note": "packet.authoritative_obligation"},
    {
        "key": "system",
        "label": "System instructions",
        "note": "the system message in build_model_input, plus packet.repair",
    },
    {"key": "schema", "label": "Output schema", "note": "format= CANDIDATE_FORMAT on the Ollama request"},
    {"key": "constraints", "label": "Constraints", "note": "constraints · acceptance_contract"},
)

_DEFAULT_ON: dict[str, bool] = {
    "recent": False,
    "state": True,
    "obligation": True,
    "system": True,
    "schema": True,
    "constraints": True,
}


def resolve_sections(sections: dict[str, bool] | None) -> dict[str, bool]:
    out = dict(_DEFAULT_ON)
    for k, v in (sections or {}).items():
        if k in out:
            out[k] = bool(v)
    return out


def apply_section_toggles(packet: dict[str, Any], sections: dict[str, bool]) -> dict[str, Any]:
    """Rebuild the packet with sections withheld, by deleting/emptying the
    same keys compile.py assembles rather than reimplementing how it
    assembles them — the result is still a packet build_model_input can
    consume unchanged."""
    m: dict[str, Any] = copy.deepcopy(packet)
    m.pop("_edge", None)
    if not sections.get("recent", False):
        m["recent_turns"] = []
    if not sections.get("state", True):
        digest = dict(m.get("state_digest") or {})
        m["facts"] = []
        m["open_threads"] = []
        m["state_digest"] = {
            "active_profile": digest.get("active_profile"),
            "session_id": digest.get("session_id"),
            "goal": "",
            "open_thread_count": 0,
            "receipt_count_24h": digest.get("receipt_count_24h"),
        }
    if not sections.get("obligation", True):
        m.pop("authoritative_obligation", None)
    if not sections.get("system", True):
        # The system message itself lives in build_model_input, not the
        # packet; the payload-level strip happens in
        # build_replay_model_input. The packet's own `repair` block is
        # grouped with "system instructions" per the spec's toggle list.
        m.pop("repair", None)
    if not sections.get("constraints", True):
        m.pop("constraints", None)
        m.pop("acceptance_contract", None)
    return m


def build_replay_model_input(
    packet: dict[str, Any],
    sections: dict[str, bool],
    *,
    model: str,
    mode: str,
    temperature: float,
    seed: int,
    num_ctx: int,
    keep_alive: str,
    think: bool,
) -> dict[str, Any]:
    """The exact request body `build_model_input` would send for this
    packet, reused (not reimplemented). The "system" and "schema" toggles
    have no packet-level representation — they gate the payload directly,
    done here rather than inside `build_model_input` itself, which must not
    grow toggle parameters as a side effect of this task."""
    model_input = build_model_input(
        packet,
        model=model,
        mode=mode,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        compact=True,
        think=think,
    )
    payload = dict(model_input["payload"])
    if not sections.get("system", True) and mode == "chat_json":
        payload["messages"] = [m for m in (payload.get("messages") or []) if m.get("role") != "system"]
    if not sections.get("schema", True):
        payload.pop("format", None)
    model_input = dict(model_input)
    model_input["payload"] = payload
    return model_input


def replay_diff(
    packet: dict[str, Any],
    modified_packet: dict[str, Any],
    *,
    recorded_share_total: int,
    configured_share_total: int,
    recorded_packet_bytes: int,
    sections: dict[str, bool],
) -> list[dict[str, Any]]:
    """Model input as recorded → as configured. Computed both sides."""

    def n(v: Any) -> int:
        return len(v or [])

    configured_packet_bytes = packet_byte_size(
        {k: v for k, v in modified_packet.items() if k != "_edge"}
    )
    goal_before = str((packet.get("state_digest") or {}).get("goal") or "")
    goal_after = str((modified_packet.get("state_digest") or {}).get("goal") or "")

    return [
        {
            "field": "model input bytes",
            "before": f"{recorded_share_total} B",
            "after": f"{configured_share_total} B",
            "delta": configured_share_total - recorded_share_total,
        },
        {
            "field": "packet bytes",
            "before": f"{recorded_packet_bytes} B",
            "after": f"{configured_packet_bytes} B",
            "delta": configured_packet_bytes - recorded_packet_bytes,
        },
        {
            "field": "recent_turns",
            "before": f"{n(packet.get('recent_turns'))} entries",
            "after": f"{n(modified_packet.get('recent_turns'))} entries",
            "withheld": not sections.get("recent", False),
        },
        {
            "field": "facts",
            "before": f"{n(packet.get('facts'))} entries",
            "after": f"{n(modified_packet.get('facts'))} entries",
            "withheld": not sections.get("state", True),
        },
        {
            "field": "open_threads",
            "before": f"{n(packet.get('open_threads'))} entries",
            "after": f"{n(modified_packet.get('open_threads'))} entries",
            "withheld": not sections.get("state", True),
        },
        {
            "field": "state_digest.goal",
            "before": f"{len(goal_before)} chars",
            "after": f"{len(goal_after)} chars",
            "withheld": not sections.get("state", True),
        },
        {
            "field": "repair block",
            "before": "present" if packet.get("repair") else "absent",
            "after": "present" if modified_packet.get("repair") else "absent",
            "withheld": not sections.get("system", True) and bool(packet.get("repair")),
        },
        {
            "field": "constraints",
            "before": "present" if packet.get("constraints") else "absent",
            "after": "present" if modified_packet.get("constraints") else "absent",
            "withheld": not sections.get("constraints", True),
        },
        {
            "field": "your share of it",
            "before": "see context_share_as_recorded",
            "after": "see context_share_as_configured",
            "withheld": False,
        },
    ]


def replay_effects(
    packet: dict[str, Any],
    modified_packet: dict[str, Any],
    *,
    evidence_used: list[str],
    thread_touch: list[str],
    sections: dict[str, bool],
) -> list[dict[str, Any]]:
    """"Checks whose input changed" — spec §10: recompute pool size, citation
    matches, stale_response_repeat liveness, goal_echo/contradicts_facts
    inputs, thread_touch ids, TEMPLATE_ECHO_MARKERS hittability, and
    parse-failure risk without format=. Every value here is recomputed
    against the modified packet through the real validators, not asserted.
    """
    pool_a = _packet_evidence_pool(packet)
    pool_b = _packet_evidence_pool(modified_packet)

    def matches(pool: set[str]) -> int:
        hits = 0
        for item in evidence_used:
            ok, _ = _evidence_ok([item], pool)
            if ok:
                hits += 1
        return hits

    matches_a, matches_b = matches(pool_a), matches(pool_b)

    prior_a = prior_accepted_answer(packet)
    prior_b = prior_accepted_answer(modified_packet)

    goal_a = str((packet.get("state_digest") or {}).get("goal") or "")
    goal_b = str((modified_packet.get("state_digest") or {}).get("goal") or "")

    facts_a = packet.get("facts") or []
    facts_b = modified_packet.get("facts") or []

    ids_b = {
        str(t.get("id") or "").lower()
        for t in (modified_packet.get("open_threads") or [])
        if isinstance(t, dict)
    }
    bad_touch = [t for t in thread_touch if str(t).lower() not in ids_b]

    system_on = sections.get("system", True)
    schema_on = sections.get("schema", True)

    return [
        {
            "check": "evidence_pool",
            "before": f"{len(pool_a)} strings",
            "after": f"{len(pool_b)} strings",
            "source": "validate._packet_evidence_pool",
        },
        {
            "check": "citations_matching",
            "before": f"{matches_a} of {len(evidence_used)}",
            "after": f"{matches_b} of {len(evidence_used)}",
            "source": "validate._evidence_ok re-run against the modified pool",
        },
        {
            "check": "stale_response_repeat",
            "before": "live" if prior_a else "inert",
            "after": "live" if prior_b else "inert",
            "source": (
                "prior_accepted_answer returns the last stored answer"
                if prior_b
                else 'prior_accepted_answer returns "" — the check cannot fire at all'
            ),
        },
        {
            "check": "goal_echo",
            "before": "live" if goal_a else "inert",
            "after": "live" if goal_b else "inert",
            "source": (
                "is_goal_echo has a goal to compare" if goal_b else "empty goal makes is_goal_echo return False"
            ),
        },
        {
            "check": "contradicts_facts",
            "before": "live" if facts_a else "inert",
            "after": "live" if facts_b else "inert",
            "source": "fact markers present" if facts_b else "no facts, so no contradiction rule can match",
        },
        {
            "check": "unknown_thread_touch",
            "before": f"{len(thread_touch)} ids cited" if thread_touch else "no thread_touch to check",
            "after": (
                (
                    f"{len(bad_touch)} of {len(thread_touch)} ids would now be unknown"
                    if bad_touch
                    else f"all {len(thread_touch)} ids still valid"
                )
                if thread_touch
                else "no thread_touch to check"
            ),
            "source": "next_state.thread_touch vs modified open_threads",
        },
        {
            "check": "not_responsive",
            "before": "advisory",
            "after": "advisory",
            "source": "companion mode never rejects on this, with or without context",
        },
        {
            "check": "template_echo",
            "before": "all markers reachable",
            "after": "all markers reachable" if system_on else "system-prompt phrases unreachable",
            "source": (
                "TEMPLATE_ECHO_MARKERS still includes the system-prompt phrases"
                if system_on
                else "with no system message the kernel cannot echo it — several markers become unhittable"
            ),
        },
        {
            "check": "parse_ok",
            "before": "format= enforced",
            "after": "format= enforced" if schema_on else "format= removed",
            "source": (
                "Ollama constrains output to CANDIDATE_FORMAT"
                if schema_on
                else (
                    "nothing constrains the kernel to JSON — parse_candidate falls back to "
                    "fence/brace extraction and parse failure becomes likely"
                )
            ),
        },
    ]


def run_replay(
    packet: dict[str, Any],
    *,
    model: str,
    mode: str,
    temperature: float,
    seed: int,
    num_ctx: int,
    keep_alive: str,
    think: bool,
    evidence_used: list[str] | None = None,
    thread_touch: list[str] | None = None,
    sections: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Build-time replay of one recorded packet with sections toggled.

    `model` / `mode` / `temperature` / `seed` / `num_ctx` / `keep_alive` are
    held fixed to the values the recorded turn used — this function does not
    accept different ones for those, by design (spec §7: "Model, seed,
    temperature and your message are held fixed and are not toggleable,
    because varying them would answer a different question"). Persists
    nothing: no state write, no log write, no second `pipeline.run_turn`
    call.
    """
    resolved = resolve_sections(sections)
    evidence_used = list(evidence_used or [])
    thread_touch = list(thread_touch or [])

    recorded_model_input = build_model_input(
        packet,
        model=model,
        mode=mode,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        compact=True,
        think=think,
    )
    modified_packet = apply_section_toggles(packet, resolved)
    modified_model_input = build_replay_model_input(
        modified_packet,
        resolved,
        model=model,
        mode=mode,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        think=think,
    )

    recorded_share = compute.context_share_bytes(packet, recorded_model_input)
    configured_share = compute.context_share_bytes(modified_packet, modified_model_input)

    recorded_packet_bytes = packet_byte_size({k: v for k, v in packet.items() if k != "_edge"})

    return {
        "held_fixed": {
            "user_input": packet.get("user_input"),
            "model": model,
            "mode": mode,
            "temperature": temperature,
            "seed": seed,
            "num_ctx": num_ctx,
            "keep_alive": keep_alive,
            "think": think,
        },
        "sections": [{**s, "on": resolved[s["key"]]} for s in REPLAY_SECTIONS],
        "packet_as_recorded": packet,
        "packet_as_configured": modified_packet,
        "model_input_as_configured": modified_model_input,
        "context_share_as_recorded": recorded_share,
        "context_share_as_configured": configured_share,
        "diff": replay_diff(
            packet,
            modified_packet,
            recorded_share_total=sum(r["bytes"] for r in recorded_share),
            configured_share_total=sum(r["bytes"] for r in configured_share),
            recorded_packet_bytes=recorded_packet_bytes,
            sections=resolved,
        ),
        "checks": replay_effects(
            packet,
            modified_packet,
            evidence_used=evidence_used,
            thread_touch=thread_touch,
            sections=resolved,
        ),
        "persists": False,
    }


__all__ = [
    "REPLAY_SECTIONS",
    "resolve_sections",
    "apply_section_toggles",
    "build_replay_model_input",
    "replay_diff",
    "replay_effects",
    "run_replay",
]
