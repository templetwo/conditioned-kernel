"""End-to-end conditioned turn: compile → generate → return path."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from conditioned_kernel.authoritative_state import (
    enforce_authoritative_candidate,
    resolve_obligation,
)
from conditioned_kernel.compile import compile_turn
from conditioned_kernel.edge import BudgetError, EdgeProfile, load_profile
from conditioned_kernel.generate import InferenceResult, OllamaClient
from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.outcomes import (
    ExecutionOutcome,
    TerminalStatus,
    classify_product_decision,
    outcome_from_inference,
)
from conditioned_kernel.return_path.accept import accept_candidate
from conditioned_kernel.return_path.assess import assess
from conditioned_kernel.return_path.parse import parse_candidate
from conditioned_kernel.return_path.repair import build_repair_plan
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
    execution_outcome: ExecutionOutcome | None = None


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
    acceptance_mode: str = "companion",
) -> TurnResult:
    """Run one conditioned turn under an edge profile (default: orin_nano_8gb).

    acceptance_mode defaults to companion (Studio product). Pass measurement for
    Laboratory experiment contracts that require model-produced evidence.
    """
    prof = profile or load_profile(profile_id)
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    ollama = client or OllamaClient(base_url=base_url, timeout=prof.timeout_s)
    passes: list[dict[str, Any]] = []
    repairs = prof.max_repair if max_repair is None else max_repair
    is_dry = dry_candidate_text is not None

    repair_plan: dict[str, Any] | None = None
    last_packet: dict[str, Any] = {}
    last_candidate: dict[str, Any] = {}
    last_receipt: dict[str, Any] = {}
    last_inference: InferenceResult | None = None
    last_raw: str | None = None

    use_model = model or prof.model
    use_mode: Mode = mode or prof.mode  # type: ignore[assignment]
    if use_mode not in ("chat_json", "generate_raw"):
        use_mode = "chat_json"

    # Studio only: resolve narrow authoritative-state obligations.
    obligation = None
    if acceptance_mode == "companion":
        obligation = resolve_obligation(
            state, user_input, profile=prof, model=use_model
        )

    def _error_result(
        *,
        decision: str,
        error: str,
        packet: dict[str, Any],
        execution_outcome: ExecutionOutcome,
        answer: str = "",
        candidate: dict[str, Any] | None = None,
        receipt: dict[str, Any] | None = None,
        outcome: dict[str, Any] | None = None,
    ) -> TurnResult:
        return TurnResult(
            ok=False,
            decision=decision,
            answer=answer,
            packet=packet,
            candidate=candidate or {},
            receipt=receipt or {},
            outcome=outcome or {},
            passes=passes,
            error=error,
            profile_id=prof.profile_id,
            execution_outcome=execution_outcome,
        )

    for pass_index in range(repairs + 1):
        try:
            packet, model_input = compile_turn(
                state,
                user_input,
                model=use_model,
                mode=use_mode,
                repair_plan=repair_plan,
                temperature=temperature,
                seed=seed,
                num_ctx=num_ctx,
                keep_alive=keep_alive,
                profile=prof,
                acceptance_mode=acceptance_mode,
                authoritative_obligation=(
                    obligation.to_dict() if obligation is not None else None
                ),
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
            eo = ExecutionOutcome.from_lifecycle(
                status=TerminalStatus.COMPLETED_INVALID,
                output=None,
                decision="error",
                reason_codes=("budget",),
                error=str(e),
            )
            return _error_result(
                decision="error",
                error=str(e),
                packet={},
                execution_outcome=eo,
            )

        last_packet = packet

        if is_dry:
            raw = dry_candidate_text if dry_candidate_text is not None else ""
            telemetry: dict[str, Any] = {
                "dry_run": True,
                "pass_index": pass_index,
                "profile_id": prof.profile_id,
            }
            last_inference = None
        else:
            # Canonical typed inference path (OllamaClient.run). Never generate()
            # and never reconstruct status from exception strings.
            inference = ollama.run(model_input)
            last_inference = inference
            terminal = outcome_from_inference(inference)
            if terminal.status in (
                TerminalStatus.TIMEOUT,
                TerminalStatus.TRANSPORT_ERROR,
                TerminalStatus.INVALID_RESPONSE,
                TerminalStatus.NO_FINAL_RESPONSE,
            ):
                state.log_error(
                    {
                        "ts": utc_now_iso(),
                        "error": inference.error or terminal.status.value,
                        "packet_id": packet.get("packet_id"),
                        "pass_index": pass_index,
                        "profile_id": prof.profile_id,
                        "inference_status": terminal.status.value,
                    }
                )
                return _error_result(
                    decision="error",
                    error=inference.error or terminal.status.value,
                    packet=packet,
                    execution_outcome=terminal,
                )

            # Observed final response only (may be empty string). Never coerce None → "".
            if inference.output is None:
                # Should be unreachable for COMPLETED; fail closed.
                eo = ExecutionOutcome.from_lifecycle(
                    status=TerminalStatus.NO_FINAL_RESPONSE,
                    output=None,
                    decision="error",
                    reason_codes=("output_null_on_completed",),
                    error="completed_inference_with_null_output",
                    inference=inference.to_dict(),
                )
                return _error_result(
                    decision="error",
                    error="completed_inference_with_null_output",
                    packet=packet,
                    execution_outcome=eo,
                )
            raw = inference.output
            telemetry = {
                "profile_id": prof.profile_id,
                "packet_bytes": model_input.get("packet_bytes"),
                "inference_status": inference.status.value,
                "thinking_chars": inference.thinking_chars,
                "final_response_chars": inference.final_response_chars,
                "elapsed_seconds": inference.elapsed_seconds,
            }

        last_raw = raw
        candidate = parse_candidate(raw, packet_id=packet["packet_id"], pass_index=pass_index)
        auth_reasons: list[str] = []
        if obligation is not None and acceptance_mode == "companion":
            candidate, auth_reasons = enforce_authoritative_candidate(
                candidate,
                obligation,
                user_input=user_input,
                packet_id=str(packet.get("packet_id") or ""),
            )
            packet = dict(packet)
            packet["authoritative_enforced"] = True
            packet["authoritative_fallback"] = bool(
                candidate.get("authoritative_fallback")
            )
            packet["authoritative_reasons"] = list(auth_reasons)
        receipt = validate_candidate(candidate, packet)
        receipt = assess(receipt, pass_index=pass_index, max_repair=repairs)
        receipt["profile_id"] = prof.profile_id
        if obligation is not None:
            receipt["authoritative_kind"] = obligation.kind
            receipt["authoritative_fallback"] = bool(
                candidate.get("authoritative_fallback")
            )
            receipt["authoritative_reasons"] = list(auth_reasons)
        last_candidate = candidate
        last_receipt = receipt

        passes.append(
            {
                "pass_index": pass_index,
                "candidate_id": candidate.get("candidate_id"),
                "decision": receipt.get("decision"),
                "violations": list(receipt.get("violations") or []),
                "telemetry": telemetry,
                "packet_bytes": (packet.get("_edge") or {}).get("packet_bytes"),
                "authoritative_kind": obligation.kind if obligation else None,
                "authoritative_fallback": bool(
                    candidate.get("authoritative_fallback")
                ),
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
            eo = classify_product_decision(
                decision="accept",
                candidate=candidate,
                receipt=receipt,
                raw_output=raw,
                dry_run=is_dry,
                inference=last_inference,
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
                execution_outcome=eo,
            )

        if receipt["decision"] == "repair" and pass_index < repairs:
            repair_plan = build_repair_plan(receipt, candidate, packet)
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
        eo = classify_product_decision(
            decision="reject",
            candidate=candidate,
            receipt=receipt,
            raw_output=raw,
            dry_run=is_dry,
            inference=last_inference,
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
            execution_outcome=eo,
        )

    eo = classify_product_decision(
        decision="reject",
        candidate=last_candidate,
        receipt=last_receipt,
        raw_output=last_raw,
        dry_run=is_dry,
        inference=last_inference,
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
        execution_outcome=eo,
    )
