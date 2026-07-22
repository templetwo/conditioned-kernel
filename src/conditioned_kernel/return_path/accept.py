"""Persist accepted/rejected outcomes and allowed state deltas."""

from __future__ import annotations

from typing import Any

from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.state import SubstrateState


def accept_candidate(
    state: SubstrateState,
    *,
    packet: dict[str, Any],
    candidate: dict[str, Any],
    receipt: dict[str, Any],
    model_input: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = receipt.get("decision")
    applied: list[str] = []

    if decision == "accept":
        applied = state.apply_state_updates(candidate.get("next_state"))
        # bump receipt counter
        state.current["receipt_count_24h"] = int(state.current.get("receipt_count_24h") or 0) + 1
        state.save_current()

    outcome = {
        "accepted_at": utc_now_iso(),
        "decision": decision,
        "packet_id": packet.get("packet_id"),
        "candidate_id": candidate.get("candidate_id"),
        "receipt_id": receipt.get("receipt_id"),
        "applied_updates": applied,
        "answer": candidate.get("answer") if decision == "accept" else None,
        "reject_reason": None if decision == "accept" else list(receipt.get("violations") or []),
        "model": (model_input or {}).get("model"),
        "mode": (model_input or {}).get("mode"),
        "packet_hash": (model_input or {}).get("packet_hash"),
        "telemetry": telemetry or {},
    }

    state.log_receipt({**receipt, **{"outcome": outcome}})
    state.log_candidate(candidate)
    state.log_history(
        {
            "ts": utc_now_iso(),
            "packet_id": packet.get("packet_id"),
            "packet_hash": (model_input or {}).get("packet_hash"),
            "user_input": packet.get("user_input"),
            "candidate_id": candidate.get("candidate_id"),
            "decision": decision,
            "pass_index": candidate.get("pass_index"),
        }
    )
    return outcome
