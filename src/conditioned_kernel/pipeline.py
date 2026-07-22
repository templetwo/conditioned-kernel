"""End-to-end conditioned turn: compile → generate → return path."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from conditioned_kernel.compile import compile_turn
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


def run_turn(
    user_input: str,
    *,
    model: str = "qwen2.5:0.5b",
    mode: Mode = "chat_json",
    state_dir: Path | None = None,
    logs_dir: Path | None = None,
    base_url: str = "http://127.0.0.1:11434",
    max_repair: int = 1,
    temperature: float = 0.3,
    seed: int = 42,
    num_ctx: int = 4096,
    client: OllamaClient | None = None,
    dry_candidate_text: str | None = None,
) -> TurnResult:
    """Run one conditioned turn.

    dry_candidate_text: if set, skip Ollama and inject this raw text (tests).
    """
    state = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    ollama = client or OllamaClient(base_url=base_url)
    passes: list[dict[str, Any]] = []

    repair_annotations: list[str] | None = None
    last_packet: dict[str, Any] = {}
    last_candidate: dict[str, Any] = {}
    last_receipt: dict[str, Any] = {}
    last_model_input: dict[str, Any] = {}
    last_telemetry: dict[str, Any] = {}

    for pass_index in range(max_repair + 1):
        packet, model_input = compile_turn(
            state,
            user_input,
            model=model,
            mode=mode,
            repair_annotations=repair_annotations,
            temperature=temperature,
            seed=seed,
            num_ctx=num_ctx,
        )
        last_packet = packet
        last_model_input = model_input

        try:
            if dry_candidate_text is not None and pass_index == 0:
                raw = dry_candidate_text
                telemetry: dict[str, Any] = {"dry_run": True}
            elif dry_candidate_text is not None and pass_index > 0:
                # For dry multi-pass, reuse unless a custom path is needed
                raw = dry_candidate_text
                telemetry = {"dry_run": True, "pass_index": pass_index}
            else:
                response = ollama.generate(model_input)
                raw = OllamaClient.extract_text(response, mode)
                telemetry = OllamaClient.extract_telemetry(response)
        except OllamaError as e:
            state.log_error(
                {
                    "ts": utc_now_iso(),
                    "error": str(e),
                    "packet_id": packet.get("packet_id"),
                    "pass_index": pass_index,
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
            )

        candidate = parse_candidate(raw, packet_id=packet["packet_id"], pass_index=pass_index)
        receipt = validate_candidate(candidate, packet)
        receipt = assess(receipt, pass_index=pass_index, max_repair=max_repair)
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
            )

        if receipt["decision"] == "repair" and pass_index < max_repair:
            repair_annotations = build_repair_annotations(receipt, candidate)
            state.log_candidate(candidate)
            state.log_receipt(receipt)
            continue

        # reject
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
        )

    # Unreachable, but keeps type checkers calm
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
    )
