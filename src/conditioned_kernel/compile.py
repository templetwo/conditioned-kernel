"""Compile substrate state + user input into an arrival packet and model payload."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from conditioned_kernel.edge import EdgeProfile, enforce_packet_budget, load_profile
from conditioned_kernel.ids import packet_id, utc_now_iso
from conditioned_kernel.state import SubstrateState

Mode = Literal["chat_json", "generate_raw"]

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
    profile: EdgeProfile | None = None,
    enforce_budget: bool = True,
) -> dict[str, Any]:
    prof = profile or load_profile()
    words = max_words if max_words is not None else prof.max_answer_words
    open_threads = state.open_threads()
    packet: dict[str, Any] = {
        "packet_id": packet_id(),
        "created_at": utc_now_iso(),
        "session_id": state.current.get("session_id", "sess_unknown"),
        "user_input": user_input,
        "state_digest": _digest(state),
        "facts": state.fact_list(),
        "open_threads": [
            {"id": t.get("id"), "title": t.get("title")} for t in open_threads
        ],
        "constraints": {
            "max_words": words,
            "must_return_json": True,
            "must_cite_state_fields": True,
            "forbidden": [
                "tool_calls",
                "invented_files",
                "cloud references",
                "http://",
                "https://",
            ],
        },
        "acceptance_contract": {
            "required_sections": ["answer", "evidence_used", "next_state"],
            "must_reference_goal": True,
            "must_not_contradict_facts": True,
            "evidence_must_be_from_packet": True,
        },
    }
    if repair_annotations:
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
) -> dict[str, Any]:
    # Compact JSON saves context tokens on edge devices
    if compact:
        model_packet = {k: v for k, v in packet.items() if not str(k).startswith("_")}
        serialized = json.dumps(model_packet, ensure_ascii=False, separators=(",", ":"))
    else:
        serialized = json.dumps(packet, ensure_ascii=False, indent=2)
    system = (
        "Local conditioned-kernel transducer. "
        "Return ONLY valid JSON with keys answer, evidence_used, next_state. "
        "answer: short reply that mentions the goal. "
        "evidence_used: copy exact strings from facts or open_threads. "
        "next_state.thread_touch: array of real open_threads id values, or []. "
        "Never invent thread ids. No files, URLs, tools, or cloud."
    )

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
            "options": {
                "temperature": temperature,
                "repeat_penalty": 1.1,
                "seed": seed,
                "num_ctx": num_ctx,
            },
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
            "options": {
                "temperature": temperature,
                "repeat_penalty": 1.1,
                "seed": seed,
                "num_ctx": num_ctx,
            },
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
    }


def compile_turn(
    state: SubstrateState,
    user_input: str,
    *,
    model: str | None = None,
    mode: Mode | None = None,
    repair_annotations: list[str] | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    profile: EdgeProfile | None = None,
    profile_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prof = profile or load_profile(profile_id)
    packet = build_arrival_packet(
        state,
        user_input,
        repair_annotations=repair_annotations,
        profile=prof,
        enforce_budget=True,
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
    )
    return packet, model_input
