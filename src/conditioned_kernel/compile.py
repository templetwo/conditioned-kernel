"""Compile substrate state + user input into an arrival packet and model payload."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

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
_VOLATILE_PACKET_FIELDS = frozenset({"packet_id", "created_at"})

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
) -> dict[str, Any]:
    """Build arrival packet.

    acceptance_mode:
      companion   — product path (ck ask / ck chat). Substrate may supply evidence.
      measurement — Laboratory experiment contract. Model must cite packet facts.
    """
    prof = profile or load_profile()
    words = max_words if max_words is not None else prof.max_answer_words
    open_threads = state.open_threads()
    # Byte-capped prior dialogue (Studio first-flow). Oldest dropped first.
    recent = fit_recent_turns(
        state.recent_turns(),
        max_bytes=RECENT_TURNS_MAX_BYTES,
    )
    mode = acceptance_mode if acceptance_mode in ("companion", "measurement") else "companion"
    companion = mode == "companion"
    facts = list(state.fact_list())
    # Authoritative claims are answer obligations, not soft suggestions.
    if companion and authoritative_obligation:
        for claim in list(authoritative_obligation.get("claims") or [])[:4]:
            facts.append(f"[must preserve] {claim}")
    packet: dict[str, Any] = {
        "packet_id": packet_id(),
        "created_at": utc_now_iso(),
        "session_id": state.current.get("session_id", "sess_unknown"),
        "user_input": user_input,
        "state_digest": _digest(state),
        "facts": facts,
        "open_threads": [
            {"id": t.get("id"), "title": t.get("title")} for t in open_threads
        ],
        "recent_turns": recent,
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
            # Companion: goal keyword citation optional (small models).
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
        # Keep repair payload short — edge tokens are scarce
        clipped = [str(v)[:100] for v in repair_annotations[:6]]
        packet["repair"] = {
            "pass_index": 1,
            "violations": clipped,
            "instruction": (
                "Prior JSON failed validation. Return corrected JSON only. "
                "Copy evidence from facts/open_threads. Cite the goal in answer."
            ),
        }
    if enforce_budget:
        packet = enforce_packet_budget(packet, prof, strict=True)
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
    # Compact JSON saves context tokens on edge devices.
    # Volatile fields are stripped from the MODEL INPUT only: packet_id and
    # created_at change on every build, so leaving them in the serialized
    # prompt makes generation non-reproducible even at fixed temperature and
    # seed — the prompt itself differs run to run. They stay on the packet for
    # receipts and logging; the model has no use for them.
    model_packet = {
        k: v
        for k, v in packet.items()
        if not str(k).startswith("_") and k not in _VOLATILE_PACKET_FIELDS
    }
    if compact:
        serialized = json.dumps(model_packet, ensure_ascii=False, separators=(",", ":"))
    else:
        serialized = json.dumps(model_packet, ensure_ascii=False, indent=2)
    # Companion prompts stay short for edge ctx; measurement is stricter.
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
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "Packet:\n" + serialized,
                },
            ],
            "format": CANDIDATE_FORMAT,
            "stream": False,
            "keep_alive": keep_alive,
            # Ollama API: disable reasoning channel (not prompt-only).
            "think": bool(think),
            "options": options,
        }
    else:
        # generate_raw: packet is the prompt surface; no chat template assumed.
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
        "mode": mode,
        "model": model,
        "payload": payload,
        "packet_id": packet["packet_id"],
        "packet_hash": packet_hash(packet),
        "edge_profile": (packet.get("_edge") or {}).get("profile_id"),
        "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
        "think": bool(think),
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
