"""Compile substrate state + user input into an arrival packet and model payload."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

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
    max_words: int = 180,
    repair_annotations: list[str] | None = None,
) -> dict[str, Any]:
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
            "max_words": max_words,
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
        packet["repair"] = {
            "pass_index": 1,
            "violations": repair_annotations,
            "instruction": (
                "Previous output failed validation. Return corrected JSON only. "
                "Use only evidence strings that appear in facts or open_threads. "
                "Reference the current goal in the answer."
            ),
        }
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
    num_ctx: int = 4096,
    keep_alive: str = "5m",
) -> dict[str, Any]:
    serialized = json.dumps(packet, ensure_ascii=False, indent=2)
    system = (
        "You are a local conditioned-kernel transducer. "
        "Return ONLY valid JSON matching the schema. "
        "answer: short natural language reply. "
        "evidence_used: strings copied from packet facts or open_threads titles/ids. "
        "next_state.thread_touch: open thread ids you used (or []). "
        "Do not invent files, URLs, tools, or cloud services."
    )

    if mode == "chat_json":
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        "Arrival packet follows. Answer the user_input under all constraints.\n\n"
                        + serialized
                    ),
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
    }


def compile_turn(
    state: SubstrateState,
    user_input: str,
    *,
    model: str,
    mode: Mode = "chat_json",
    repair_annotations: list[str] | None = None,
    temperature: float = 0.3,
    seed: int = 42,
    num_ctx: int = 4096,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet = build_arrival_packet(
        state,
        user_input,
        repair_annotations=repair_annotations,
    )
    model_input = build_model_input(
        packet,
        model=model,
        mode=mode,
        temperature=temperature,
        seed=seed,
        num_ctx=num_ctx,
    )
    return packet, model_input
