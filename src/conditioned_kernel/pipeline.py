"""End-to-end conditioned turn: compile → generate → return path."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from conditioned_kernel.compile import compile_turn
from conditioned_kernel.edge import BudgetError, EdgeProfile, load_profile
from conditioned_kernel.generate import OllamaClient, OllamaError
from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.return_path.accept import accept_candidate
from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.repair import build_repair_annotations
from conditioned_kernel.return_path.validate import validate_candidate
from conditioned_kernel.state import SubstrateState

Mode = Literal["chat_json", "generate_raw"]


@dataclass
class TurnResult:
    ok: bool
    decision: str
    answer: str
    packet: dict[str, Any]
    candidate: dict[str, Any]
    receipt: dict[str, Any]
    outcome: dict[str, Any]
    passes: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    profile_id: str | None = None


def run_turn(
    user_input: str,
    *,
    model: str | None = None,
    mode: Mode | None = None,
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    base_url: str = "http://127.0.0.1:11434",
    max_repair: int | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    profile: EdgeProfile | None = None,
    profile_id: str | None = None,
    client: OllamaClient | None = None,
    dry_candidate_text: str | None = None,
) -> TurnResult:
    """Run one conditioned turn under an edge profile (default: orin_nano_8gb)."""
    prof = profile or load_profile(profile_id)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    ollama = client or OllamaClient(base_url=base_url, timeout=prof.timeout_s)
    passes: list[dict[str, Any]] = []
    repairs = prof.max_repair if max_repair is None else max_repair

    repair_annotations: list[str] | None = None
    last_packet: dict[str, Any] = {}
    last_candidate: dict[str, Any] = {}
    last_receipt: dict[str, Any] = {}
    last_model_input: dict[str, Any] = {}
    last_telemetry: dict[str, Any] = {}

    use_model = model or prof.model
    use_mode: Mode = mode or prof.mode  # type: ignore[assignment]
    if use_mode not in ("chat_json", "generate_raw"):
        use_mode = "chat_json"

    for pass_index in range(repairs + 1):
        try:
            packet, model_input = compile_turn(
                state,
                user_input,
                model=use_model,
                mode=use_mode,
                repair_annotations=repair_annotations,
                temperature=temperature,
                seed=seed,
                num_ctx=num_ctx,
                keep_alive=keep_alive,
                profile=prof,
            )
        except BudgetError as e:
            state.log_error(
                {
                    "ts": utc_now_iso(),
                    "error": str(e),
                    "kind": "budget",
                    "profile_id": prof.profile_id,
                }
            )
            return TurnResult(
                ok=False,
                decision="error",
                answer="",
                packet={},
                candidate={},
                receipt={},
                outcome={},
                passes=passes,
                error=str(e),
                profile_id=prof.profile_id,
            )

        last_packet = packet
        last_model_input = model_input

        try:
            if dry_candidate_text is not None:
                raw = dry_candidate_text
                telemetry: dict[str, Any] = {
                    "dry_run": True,
                    "pass_index": pass_index,
                    "profile_id": prof.profile_id,
                }
            else:
                response = ollama.generate(model_input)
                raw = OllamaClient.extract_text(response, use_mode)
                telemetry = OllamaClient.extract_telemetry(response)
                telemetry["profile_id"] = prof.profile_id
                telemetry["packet_bytes"] = model_input.get("packet_bytes")
        except OllamaError as e:
            state.log_error(
                {
                    "ts": utc_now_iso(),
                    "error": str(e),
                    "packet_id": packet.get("packet_id"),
                    "pass_index": pass_index,
                    "profile_id": prof.profile_id,
                }
            )
            return TurnResult(
                ok=False,
                decision="error",
                answer="",
                packet=packet,
                candidate={},
                receipt={},
                outcome={},
                passes=passes,
                error=str(e),
                profile_id=prof.profile_id,
            )

        candidate = parse_candidate(raw, packet_id=packet["packet_id"], pass_index=pass_index)
        receipt = validate_candidate(candidate, packet)
        receipt = assess(receipt, pass_index=pass_index, max_repair=repairs)
        receipt["profile_id"] = prof.profile_id
        last_candidate = candidate
        last_receipt = receipt
        last_telemetry = telemetry

        passes.append(
            {
                "pass_index": pass_index,
                "candidate_id": candidate.get("candidate_id"),
                "decision": receipt.get("decision"),
                "violations": list(receipt.get("violations") or []),
                "telemetry": telemetry,
                "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
            }
        )

        if receipt["decision"] == "accept":
            outcome = accept_candidate(
                state,
                packet=packet,
                candidate=candidate,
                receipt=receipt,
                model_input=model_input,
                telemetry=telemetry,
            )
            return TurnResult(
                ok=True,
                decision="accept",
                answer=str(candidate.get("answer") or ""),
                packet=packet,
                candidate=candidate,
                receipt=receipt,
                outcome=outcome,
                passes=passes,
                profile_id=prof.profile_id,
            )

        if receipt["decision"] == "repair" and pass_index < repairs:
            repair_annotations = build_repair_annotations(receipt, candidate)
            state.log_candidate(candidate)
            state.log_receipt(receipt)
            continue

        outcome = accept_candidate(
            state,
            packet=packet,
            candidate=candidate,
            receipt=receipt,
            model_input=model_input,
            telemetry=telemetry,
        )
        return TurnResult(
            ok=False,
            decision="reject",
            answer=str(candidate.get("answer") or ""),
            packet=last_packet,
            candidate=last_candidate,
            receipt=last_receipt,
            outcome=outcome,
            passes=passes,
            error="rejected_after_validation",
            profile_id=prof.profile_id,
        )

    return TurnResult(
        ok=False,
        decision="reject",
        answer="",
        packet=last_packet,
        candidate=last_candidate,
        receipt=last_receipt,
        outcome={},
        passes=passes,
        error="exhausted_passes",
        profile_id=prof.profile_id,
    )
