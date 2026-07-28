"""Compile substrate state + user input into an arrival packet and model payload."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from conditioned_kernel.context_field import (
    build_context_field_record,
    collect_contributions,
    companion_system_text,
    detect_intents,
    evidence_pool_from_selected,
    select_contributions,
    selected_facts,
    selected_open_threads,
    selected_recent_turns,
)
from conditioned_kernel.edge import EdgeProfile, enforce_packet_budget, load_profile
from conditioned_kernel.ids import packet_id, utc_now_iso
from conditioned_kernel.state import (
    RECENT_TURNS_MAX_BYTES,
    SubstrateState,
    fit_recent_turns,
)

Mode = Literal["chat_json", "generate_raw"]

# Per-build fields excluded from the serialized model input so that identical
# state + input produce an identical prompt (reproducibility criterion).
_VOLATILE_PACKET_FIELDS = frozenset(
    {
        "packet_id",
        "created_at",
        "context_field",  # observability; not model tokens as a blob
        "evidence_pool_selected",
        "intents",
        # Control-plane only (stale-response guard); never model tokens
        "prior_accepted_answer_control",
    }
)

# Candidate schema for Ollama format= (subset of JSON Schema)
CANDIDATE_FORMAT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "evidence_used": {
            "type": "array",
            "items": {"type": "string"},
        },
        "next_state": {
            "type": "object",
            "properties": {
                "thread_touch": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "proposed_note": {"type": "string"},
            },
        },
    },
    "required": ["answer", "evidence_used", "next_state"],
}


def _digest(state: SubstrateState) -> dict[str, Any]:
    open_threads = state.open_threads()
    return {
        "goal": state.current.get("goal", ""),
        "active_profile": state.current.get("active_profile", "ck_v0"),
        "open_thread_count": len(open_threads),
        "receipt_count_24h": state.current.get("receipt_count_24h", 0),
        "session_id": state.current.get("session_id", "sess_unknown"),
    }


def build_arrival_packet(
    state: SubstrateState,
    user_input: str,
    *,
    max_words: int | None = None,
    repair_annotations: list[str] | None = None,
    repair_plan: dict[str, Any] | None = None,
    profile: EdgeProfile | None = None,
    enforce_budget: bool = True,
    acceptance_mode: str = "companion",
    authoritative_obligation: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Build arrival packet.

    acceptance_mode:
      companion   — typed contribution selection (quiet substrate).
      measurement — full deterministic fact set (Laboratory, unchanged).
    """
    prof = profile or load_profile()
    words = max_words if max_words is not None else prof.max_answer_words
    mode = acceptance_mode if acceptance_mode in ("companion", "measurement") else "companion"
    companion = mode == "companion"
    use_model = model or prof.model

    if companion:
        available = collect_contributions(
            state, user_input, profile=prof, model=use_model
        )
        selected, records = select_contributions(available, user_input)
        field = build_context_field_record(available, selected, records)
        facts = selected_facts(selected)
        recent = selected_recent_turns(selected)
        open_threads = selected_open_threads(selected)
        intents = sorted(detect_intents(user_input))
        evidence_pool = evidence_pool_from_selected(selected)
        if authoritative_obligation:
            for claim in list(authoritative_obligation.get("claims") or [])[:4]:
                line = f"[must preserve] {claim}"
                if line not in facts:
                    facts.append(line)
                if claim not in evidence_pool:
                    evidence_pool.append(claim)
    else:
        # Measurement: full deterministic state narration (legacy Laboratory)
        open_threads_full = state.open_threads()
        facts = list(state.fact_list())
        recent = fit_recent_turns(
            state.recent_turns(),
            max_bytes=RECENT_TURNS_MAX_BYTES,
        )
        open_threads = [
            {"id": t.get("id"), "title": t.get("title")} for t in open_threads_full
        ]
        field = {
            "schema": "ck.context_field.v1",
            "mode": "measurement_full",
            "available_count": len(facts),
            "selected_count": len(facts),
            "omitted_count": 0,
            "available": [],
            "selected": [],
            "omitted": [],
            "selection_records": [],
            "selected_ids": [],
        }
        intents = ["measurement"]
        evidence_pool = list(facts)

    # Durable last assistant answer for stale-response control (may be
    # withheld from the selected dialogue field).
    prior_answer = ""
    rt_full = list(state.recent_turns() or [])
    if rt_full and isinstance(rt_full[-1], dict):
        prior_answer = str(rt_full[-1].get("answer") or "").strip()

    packet: dict[str, Any] = {
        "packet_id": packet_id(),
        "created_at": utc_now_iso(),
        "session_id": state.current.get("session_id", "sess_unknown"),
        "user_input": user_input,
        "state_digest": _digest(state),
        "facts": facts,
        "open_threads": open_threads,
        "recent_turns": recent,
        "intents": intents,
        "context_field": field,
        "evidence_pool_selected": evidence_pool,
        "prior_accepted_answer_control": prior_answer,
        "constraints": {
            "max_words": words,
            "must_return_json": True,
            "must_cite_state_fields": not companion,
            "forbidden": [
                "tool_calls",
                "invented_files",
                "cloud references",
                "http://",
                "https://",
            ],
        },
        "acceptance_contract": {
            "acceptance_mode": mode,
            "required_sections": ["answer", "evidence_used", "next_state"],
            "must_reference_goal": not companion,
            "must_not_contradict_facts": True,
            "evidence_must_be_from_packet": True,
        },
    }
    if companion and authoritative_obligation:
        packet["authoritative_obligation"] = dict(authoritative_obligation)
    if repair_plan:
        packet["repair"] = {
            "pass_index": 1,
            "instruction": str(repair_plan.get("instruction") or "")[:220],
            "hints": [str(h)[:140] for h in (repair_plan.get("hints") or [])[:4]],
            "allowed_thread_ids": list(repair_plan.get("allowed_thread_ids") or [])[:6],
            "allowed_evidence_samples": [
                str(x)[:120] for x in (repair_plan.get("allowed_evidence_samples") or [])[:3]
            ],
            "goal_snippet": str(repair_plan.get("goal_snippet") or "")[:160],
            "example_json": repair_plan.get("example_json") or {},
        }
    elif repair_annotations:
        clipped = [str(v)[:100] for v in repair_annotations[:6]]
        packet["repair"] = {
            "pass_index": 1,
            "violations": clipped,
            "instruction": (
                "Prior JSON failed validation. Return corrected JSON only. "
                "Answer the current human message. Use only Selected context."
            ),
        }
    if enforce_budget:
        # Observability records are not inference tokens; exclude from edge budget.
        cf = packet.pop("context_field", None)
        ep = packet.pop("evidence_pool_selected", None)
        intents = packet.pop("intents", None)
        packet = enforce_packet_budget(packet, prof, strict=True)
        if cf is not None:
            packet["context_field"] = cf
        if ep is not None:
            packet["evidence_pool_selected"] = ep
        if intents is not None:
            packet["intents"] = intents
    return packet


def packet_hash(packet: dict[str, Any]) -> str:
    raw = json.dumps(packet, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_model_input(
    packet: dict[str, Any],
    *,
    model: str,
    mode: Mode = "chat_json",
    temperature: float = 0.3,
    seed: int = 42,
    num_ctx: int = 2048,
    keep_alive: str = "2m",
    compact: bool = True,
    think: bool = False,
) -> dict[str, Any]:
    """Build Ollama payload.

    Companion mode: selected context first, current human message last as a
    distinct labeled block (never buried inside a large state object).
    Measurement mode: compact Packet JSON (Laboratory reproducibility).
    """
    contract = packet.get("acceptance_contract") or {}
    companion = str(contract.get("acceptance_mode") or "") == "companion"
    intents = set(packet.get("intents") or [])
    social = companion and ("social" in intents) and not intents.intersection(
        {"purpose", "runtime", "edge", "policy", "threads", "measurement"}
    )

    if companion:
        system = companion_system_text(social=social)
        # Selected context without burying user_input
        ctx_lines: list[str] = []
        for fact in packet.get("facts") or []:
            ctx_lines.append(f"- {fact}")
        for t in packet.get("open_threads") or []:
            if isinstance(t, dict):
                ctx_lines.append(f"- thread {t.get('id')}: {t.get('title')}")
        for turn in packet.get("recent_turns") or []:
            if isinstance(turn, dict):
                u = str(turn.get("user") or "").strip()
                a = str(turn.get("answer") or "").strip()
                if u or a:
                    ctx_lines.append(f"- prior: user={u!s} | assistant={a!s}")
        if packet.get("authoritative_obligation"):
            claims = (packet.get("authoritative_obligation") or {}).get("claims") or []
            for c in claims[:4]:
                ctx_lines.append(f"- [must preserve] {c}")
        if packet.get("repair"):
            repair = packet["repair"]
            ctx_lines.append(
                f"- repair: {repair.get('instruction') or ''} "
                f"hints={repair.get('hints') or []}"
            )

        context_block = "\n".join(ctx_lines) if ctx_lines else "(no selected substrate prose)"
        user_content = (
            "## Selected context\n"
            f"{context_block}\n\n"
            "## Current human message\n"
            f"{packet.get('user_input') or ''}\n"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "format": CANDIDATE_FORMAT,
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
        if mode == "generate_raw":
            payload = {
                "model": model,
                "prompt": f"{system}\n\n{user_content}\nRespond with JSON only.",
                "raw": True,
                "stream": False,
                "format": CANDIDATE_FORMAT,
                "keep_alive": keep_alive,
                "think": bool(think),
                "options": {
                    "temperature": temperature,
                    "repeat_penalty": 1.1,
                    "seed": seed,
                    "num_ctx": num_ctx,
                },
            }
    else:
        # Measurement / Laboratory: packet is the prompt surface
        model_packet = {
            k: v
            for k, v in packet.items()
            if not str(k).startswith("_") and k not in _VOLATILE_PACKET_FIELDS
        }
        if compact:
            serialized = json.dumps(model_packet, ensure_ascii=False, separators=(",", ":"))
        else:
            serialized = json.dumps(model_packet, ensure_ascii=False, indent=2)
        system = (
            "Local conditioned-kernel transducer. "
            "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
            "answer: short helpful reply grounded in the packet. "
            "If recent_turns is present, treat it as prior dialogue and stay consistent. "
            "evidence_used: prefer exact strings from facts/open_threads/recent_turns; "
            "may be [] if unsure (substrate can ground). "
            "next_state.thread_touch: real open_threads ids or []. "
            "Never invent thread ids. No files, URLs, tools, or cloud."
        )
        options = {
            "temperature": temperature,
            "repeat_penalty": 1.1,
            "seed": seed,
            "num_ctx": num_ctx,
        }
        if mode == "chat_json":
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": "Packet:\n" + serialized},
                ],
                "format": CANDIDATE_FORMAT,
                "stream": False,
                "keep_alive": keep_alive,
                "think": bool(think),
                "options": options,
            }
        else:
            prompt = (
                f"{system}\n\n"
                f"ARRIVAL_PACKET:\n{serialized}\n\n"
                "Respond with JSON only."
            )
            payload = {
                "model": model,
                "prompt": prompt,
                "raw": True,
                "stream": False,
                "format": CANDIDATE_FORMAT,
                "keep_alive": keep_alive,
                "think": bool(think),
                "options": options,
            }

    return {
        "schema_version": "ck.v0",
        "mode": mode if mode in ("chat_json", "generate_raw") else "chat_json",
        "model": model,
        "payload": payload,
        "packet_id": packet["packet_id"],
        "packet_hash": packet_hash(packet),
        "edge_profile": (packet.get("_edge") or {}).get("profile_id"),
        "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
        "think": bool(think),
        "companion_field": companion,
    }


def compile_turn(
    state: SubstrateState,
    user_input: str,
    *,
    model: str | None = None,
    mode: Mode | None = None,
    repair_annotations: list[str] | None = None,
    repair_plan: dict[str, Any] | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    profile: EdgeProfile | None = None,
    profile_id: str | None = None,
    acceptance_mode: str = "companion",
    authoritative_obligation: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prof = profile or load_profile(profile_id)
    packet = build_arrival_packet(
        state,
        user_input,
        repair_annotations=repair_annotations,
        repair_plan=repair_plan,
        profile=prof,
        enforce_budget=True,
        acceptance_mode=acceptance_mode,
        authoritative_obligation=authoritative_obligation,
        model=model or prof.model,
    )
    model_input = build_model_input(
        packet,
        model=model or prof.model,
        mode=mode or prof.mode,  # type: ignore[arg-type]
        temperature=prof.temperature if temperature is None else temperature,
        seed=prof.seed if seed is None else seed,
        num_ctx=prof.num_ctx if num_ctx is None else num_ctx,
        keep_alive=prof.keep_alive if keep_alive is None else keep_alive,
        compact=True,
        think=bool(prof.think),
    )
    return packet, model_input
