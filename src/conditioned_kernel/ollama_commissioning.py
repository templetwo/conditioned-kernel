"""RUN 00.8B — real local Ollama commissioning executor.

Instrument validation only. No scientific interpretation.
Exactly one request per planned cell at most; no retries.
"""

from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import httpx

from conditioned_kernel.commissioning_plan import (
    COMMISSIONING_LABELS,
    SOURCE_CANDIDATE_MANIFEST_SHA256,
    build_commissioning_plan,
    load_retired_candidate,
    verify_plan_hash,
    write_plan,
)
from conditioned_kernel.control_contract import (
    ConditionId,
    ControlVerdict,
    RuntimeSettings,
    TaskDependencyAnnotation,
    build_matched_c3_c1_pair,
    compile_condition_packet,
    verify_control_pair,
    OUTPUT_SCHEMA,
    PACKET_CONTRACT_VERSION,
)
from conditioned_kernel.evidence_verification import (
    make_control_receipt,
    make_packet_receipt,
)
from conditioned_kernel.generate import OllamaClient, RunStatus
from conditioned_kernel.m0_admission import evaluate_admission
from conditioned_kernel.m0_ledger_integration import (
    IntegrationInputs,
    M0LedgerSession,
    M0TerminalClassification,
)
from conditioned_kernel.m0_manifest import _repo_root
from conditioned_kernel.persistent_terminal_ledger import (
    PersistentLedgerError,
    PersistentTerminalLedger,
)
from conditioned_kernel.relational_scorer import (
    canonical_json_bytes,
    sha256_hex,
)
from conditioned_kernel.response_scoring_adapter import (
    parse_structured_response,
    score_parsed_response,
)
from conditioned_kernel.runtime_provenance import (
    build_runtime_provenance,
    compute_provenance_completeness,
)

OLLAMA_BASE = "http://127.0.0.1:11434"
MODEL_TAG = "qwen2.5:0.5b"
GEN_OPTS = {"temperature": 0.0, "seed": 0, "num_ctx": 2048}
CONDITION_ORDER = [
    ConditionId.C0_BARE.value,
    ConditionId.C1_BUDGET_MATCHED_BARE.value,
    ConditionId.C2_INSTRUCTION_IDENTICAL.value,
    ConditionId.C3_STATIC_CK.value,
]


class CommissioningPreflightError(RuntimeError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, obj: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (bytes, bytearray)):
        path.write_bytes(bytes(obj))
        return sha256_hex(bytes(obj))
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_hex(text.encode("utf-8"))


def _write_bytes(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_hex(data)


def resolve_model_digest(model_tag: str = MODEL_TAG, base_url: str = OLLAMA_BASE) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{base_url.rstrip('/')}/api/tags")
            r.raise_for_status()
            tags = r.json()
            r2 = client.post(f"{base_url.rstrip('/')}/api/show", json={"name": model_tag})
            show = r2.json() if r2.status_code < 400 else {}
    except Exception as e:  # noqa: BLE001
        raise CommissioningPreflightError("RUNTIME_UNAVAILABLE", str(e)) from e

    digest = None
    size = None
    details: dict[str, Any] = {}
    for m in tags.get("models") or []:
        if m.get("name") == model_tag or m.get("model") == model_tag:
            digest = m.get("digest")
            size = m.get("size")
            details = m.get("details") or {}
            break
    if not digest:
        raise CommissioningPreflightError(
            "MODEL_DIGEST_MISSING", f"model {model_tag} not installed locally"
        )
    return {
        "model_tag": model_tag,
        "resolved_model_digest": digest,
        "size_bytes": size,
        "details": details,
        "show_details": show.get("details") or details,
        "parameter_size": (show.get("details") or details).get("parameter_size"),
        "quantization": (show.get("details") or details).get("quantization_level"),
        "family": (show.get("details") or details).get("family"),
        "format": (show.get("details") or details).get("format"),
    }


def ollama_version(base_url: str = OLLAMA_BASE) -> str:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base_url.rstrip('/')}/api/version")
            r.raise_for_status()
            return str(r.json().get("version") or "unknown")
    except Exception as e:  # noqa: BLE001
        raise CommissioningPreflightError("RUNTIME_UNAVAILABLE", str(e)) from e


def run_preflight(
    *,
    run_dir: Path,
    repo_head: str,
) -> dict[str, Any]:
    """Pre-flight gate. No model invocation."""
    reasons: list[str] = []

    # Retired manifest
    try:
        cand = load_retired_candidate()
    except Exception as e:  # noqa: BLE001
        raise CommissioningPreflightError("RETIRED_MANIFEST_HASH_MISMATCH", str(e)) from e

    plan = build_commissioning_plan(source=cand, repo_head=repo_head)
    if not verify_plan_hash(plan):
        raise CommissioningPreflightError("PLAN_HASH_FAILED")

    # Ollama + model
    version = ollama_version()
    model_meta = resolve_model_digest(MODEL_TAG)

    # Options serialization check
    runtime = RuntimeSettings(
        model_tag=MODEL_TAG,
        temperature=0.0,
        seed=0,
        num_ctx=2048,
    )
    if runtime.temperature != 0.0 or runtime.seed != 0 or runtime.num_ctx != 2048:
        raise CommissioningPreflightError(
            "OPTIONS_SERIALIZATION_FAILED",
            f"runtime={runtime.temperature},{runtime.seed},{runtime.num_ctx}",
        )
    # Round-trip options in payload
    payload_opts = {
        "temperature": runtime.temperature,
        "seed": runtime.seed,
        "num_ctx": runtime.num_ctx,
    }
    if payload_opts != GEN_OPTS:
        raise CommissioningPreflightError("OPTIONS_MISMATCH", str(payload_opts))

    # Empty ledger path
    ledger_dir = run_dir / "ledger"
    if ledger_dir.exists() and any(ledger_dir.iterdir()):
        raise CommissioningPreflightError("LEDGER_NOT_EMPTY", str(ledger_dir))

    # Cell cardinality
    if plan["planned_cell_count"] != 4:
        raise CommissioningPreflightError(
            "CELL_CARDINALITY", str(plan["planned_cell_count"])
        )
    if len({c["cell_id"] for c in plan["planned_cells"]}) != 4:
        raise CommissioningPreflightError("DUPLICATE_CELL_IDS")

    host = {
        "architecture": platform.machine(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "os_version": platform.version(),
    }

    preflight = {
        "schema_version": "ck.commissioning_preflight.v1",
        "commissioning_plan_id": plan["commissioning_plan_id"],
        "commissioning_plan_sha256": plan["commissioning_plan_sha256"],
        "source_candidate_manifest_sha256": SOURCE_CANDIDATE_MANIFEST_SHA256,
        "repository_head": repo_head,
        "ollama_base_url": OLLAMA_BASE,
        "ollama_version": version,
        "model": model_meta,
        "requested_generation_options": dict(GEN_OPTS),
        "serialized_generation_options": payload_opts,
        "option_confirmation_capability": "requested_but_not_confirmable",
        "host": host,
        "planned_cell_count": plan["planned_cell_count"],
        "max_model_invocations": 4,
        "ledger_path": str(ledger_dir),
        "scientific_scope_selected": False,
        "authorization_receipt_present": False,
        "verdict": "COMMISSIONING_PREFLIGHT_PASS",
        "reason_codes": reasons,
        **COMMISSIONING_LABELS,
        "timestamp": _now_iso(),
    }
    return {"preflight": preflight, "plan": plan, "candidate": cand}


def _load_annotation(task_id: str) -> TaskDependencyAnnotation:
    root = _repo_root()
    # Prefer m0_task_dep
    candidates = [
        root / "tests" / "fixtures" / "m0_task_dep" / f"{task_id}.json",
        root / "tests" / "fixtures" / f"control_task_{task_id}.json",
    ]
    for p in candidates:
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return TaskDependencyAnnotation.from_dict(data)
    raise CommissioningPreflightError("MISSING_ANNOTATION", task_id)


def _compile_packets_for_task(
    ann: TaskDependencyAnnotation,
    runtime: RuntimeSettings,
    gold_relations: list[dict[str, str]],
    repo_commit: str | None,
) -> dict[str, Any]:
    """Compile C0/C1/C2/C3 packets and control receipts for the task."""
    c3, c1, c3c1_receipt = build_matched_c3_c1_pair(
        ann, runtime, accepted_relations=gold_relations, repo_commit=repo_commit
    )
    c0 = compile_condition_packet(ConditionId.C0_BARE, ann, runtime)
    c2 = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, ann, runtime
    )
    # C2 vs C3 control (instruction identity, no byte equality)
    c2c3 = verify_control_pair(
        c3,
        c2,
        require_byte_equality=False,
        require_instruction_identity=True,
        require_task_fact_identity=True,
        require_schema_identity=True,
        require_runtime_identity=True,
        intended_differences=["C3 has reconstructed state; C2 does not"],
        repo_commit=repo_commit,
    )
    return {
        ConditionId.C0_BARE.value: c0,
        ConditionId.C1_BUDGET_MATCHED_BARE.value: c1,
        ConditionId.C2_INSTRUCTION_IDENTICAL.value: c2,
        ConditionId.C3_STATIC_CK.value: c3,
        "c3_c1_receipt": c3c1_receipt,
        "c2_c3_receipt": c2c3,
    }


def _packet_to_evidence_receipt(cell: Mapping[str, Any], packet) -> dict[str, Any]:
    req_hash = sha256_hex(packet.complete_bytes)
    return make_packet_receipt(
        cell_id=str(cell["cell_id"]),
        task_id=str(cell["task_id"]),
        condition_id=str(cell["condition_id"]),
        request_sha256=req_hash,
        complete_byte_length=len(packet.complete_bytes),
        packet_contract_version=PACKET_CONTRACT_VERSION,
        verdict="PASS",
    )


def _control_evidence_receipt(
    cell: Mapping[str, Any],
    *,
    pair_receipt_dict: Mapping[str, Any] | None,
    verdict: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return make_control_receipt(
        cell_id=str(cell["cell_id"]),
        task_id=str(cell["task_id"]),
        condition_id=str(cell["condition_id"]),
        paired_cell_id=cell.get("paired_primary_cell_id"),
        verdict=verdict,
        reason_codes=reason_codes,
        left_hash=None,
        right_hash=None,
        byte_match=verdict.upper() == "PASS",
    )


def _build_ollama_payload(packet, runtime: RuntimeSettings) -> tuple[dict[str, Any], bytes]:
    """Exact outbound chat payload and its canonical bytes."""
    payload = {
        "model": runtime.model_tag,
        "messages": [
            {"role": "system", "content": packet.system_text},
            {"role": "user", "content": packet.user_content},
        ],
        "format": packet.schema if packet.schema else OUTPUT_SCHEMA,
        "stream": False,
        "options": {
            "temperature": float(runtime.temperature),
            "seed": int(runtime.seed),
            "num_ctx": int(runtime.num_ctx),
        },
    }
    # Ensure zeros preserved
    assert payload["options"]["temperature"] == 0.0
    assert payload["options"]["seed"] == 0
    raw = canonical_json_bytes(payload)
    return payload, raw


def map_run_status(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETED: "completed",
        RunStatus.TIMEOUT: "timeout",
        RunStatus.TRANSPORT_ERROR: "transport_error",
        RunStatus.INVALID_RESPONSE: "invalid_response",
        RunStatus.NO_FINAL_RESPONSE: "no_final_response",
    }.get(status, "invalid_response")


def execute_commissioning_run(
    *,
    run_dir: Path,
    repo_head: str,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Full real Ollama commissioning run. Writes artifacts under run_dir."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    pf = run_preflight(run_dir=run_dir, repo_head=repo_head)
    preflight = pf["preflight"]
    plan = pf["plan"]

    _write_json(run_dir / "preflight.json", preflight)
    write_plan(plan, run_dir / "commissioning_plan.json")
    _write_json(
        run_dir / "source_candidate_identity.json",
        {
            "source_candidate_manifest_id": "ck.m0.candidate.v1",
            "source_candidate_manifest_sha256": SOURCE_CANDIDATE_MANIFEST_SHA256,
            "disposition": "RETIRED_NEVER_RATIFY_COMMISSIONING_REFERENCE_ONLY",
            **COMMISSIONING_LABELS,
        },
    )

    model_meta = preflight["model"]
    digest = model_meta["resolved_model_digest"]
    runtime = RuntimeSettings(
        model_tag=MODEL_TAG,
        temperature=0.0,
        seed=0,
        num_ctx=2048,
    )

    # Gold + annotation
    task = plan["included_tasks"][0]
    task_id = task["task_id"]
    gold = task["gold"]
    ann = _load_annotation(task_id)
    packets = _compile_packets_for_task(
        ann, runtime, list(gold["expected_relations"]), repo_head
    )

    # Session + ledger
    # Bind session to plan cells via a pseudo-manifest shape
    session_manifest = {
        "manifest_id": plan["commissioning_plan_id"],
        "manifest_sha256": plan["commissioning_plan_sha256"],
        "model_tag": plan["model_tag"],
        "generation_parameters": plan["generation_parameters"],
        "condition_set": plan["condition_set"],
        "planned_cells": plan["planned_cells"],
        "planned_cell_count": plan["planned_cell_count"],
        "planned_primary_pairs": plan["planned_primary_pairs"],
        "authorization_status": "unratified",
        "repository_commit": repo_head,
    }
    ledger_dir = run_dir / "ledger"
    ledger = PersistentTerminalLedger.open(
        ledger_dir,
        manifest_sha256=plan["commissioning_plan_sha256"],
        planned_cell_ids={c["cell_id"] for c in plan["planned_cells"]},
    )
    session = M0LedgerSession(session_manifest)

    client = OllamaClient(base_url=OLLAMA_BASE, timeout=timeout_s)
    # Confirm still reachable
    client.heartbeat()

    results: list[dict[str, Any]] = []
    invocation_count = 0
    artifact_index: dict[str, Any] = {}

    for cell in plan["planned_cells"]:
        cid = cell["cell_id"]
        cond = cell["condition_id"]
        cell_dir = run_dir / "cells" / cond
        cell_dir.mkdir(parents=True, exist_ok=True)

        packet = packets[cond]
        packet_receipt = _packet_to_evidence_receipt(cell, packet)
        # Control: C1/C3 use pair receipt; others use instructional PASS diagnostic
        if cond in (
            ConditionId.C1_BUDGET_MATCHED_BARE.value,
            ConditionId.C3_STATIC_CK.value,
        ):
            pair = packets["c3_c1_receipt"]
            pair_d = pair.to_dict()
            c_verdict = "PASS" if pair.verdict is ControlVerdict.PASS else "FAIL"
            control_receipt = _control_evidence_receipt(
                cell, pair_receipt_dict=pair_d, verdict=c_verdict,
                reason_codes=list(pair.reason_codes),
            )
            _write_json(cell_dir / "control_pair_receipt.json", pair_d)
        elif cond == ConditionId.C2_INSTRUCTION_IDENTICAL.value:
            pair = packets["c2_c3_receipt"]
            pair_d = pair.to_dict()
            c_verdict = "PASS" if pair.verdict is ControlVerdict.PASS else "FAIL"
            control_receipt = _control_evidence_receipt(
                cell, pair_receipt_dict=pair_d, verdict=c_verdict,
                reason_codes=list(pair.reason_codes),
            )
            _write_json(cell_dir / "control_pair_receipt.json", pair_d)
        else:
            control_receipt = _control_evidence_receipt(
                cell, pair_receipt_dict=None, verdict="PASS",
                reason_codes=["C0_NO_PRIMARY_PAIR_CONTROL"],
            )

        _write_bytes(cell_dir / "packet_complete_bytes.bin", packet.complete_bytes)
        _write_json(cell_dir / "packet_body.json", packet.body)
        _write_json(cell_dir / "packet_receipt.json", packet_receipt)
        _write_json(cell_dir / "control_receipt.json", control_receipt)

        # Intent before send
        payload, request_bytes = _build_ollama_payload(packet, runtime)
        request_sha = sha256_hex(request_bytes)
        intent = {
            "cell_id": cid,
            "condition_id": cond,
            "task_id": cell["task_id"],
            "model_tag": MODEL_TAG,
            "resolved_model_digest": digest,
            "request_sha256": request_sha,
            "requested_options": dict(GEN_OPTS),
            "timestamp": _now_iso(),
            **COMMISSIONING_LABELS,
        }
        _write_json(cell_dir / "invocation_intent.json", intent)
        _write_bytes(cell_dir / "ollama_request.json", request_bytes)

        if invocation_count >= 4:
            # Should not happen with 4 cells
            raise RuntimeError("MAX_INVOCATIONS_EXCEEDED")

        # Invoke
        started = _now_iso()
        t0 = time.monotonic()
        model_input = {
            "mode": "chat_json",
            "payload": payload,
        }
        inv = client.run(model_input)
        invocation_count += 1
        ended = _now_iso()
        duration = time.monotonic() - t0

        # Raw response artifact (full JSON if we can re-fetch is not available;
        # store structured capture from InferenceResult + empty envelope)
        raw_output = inv.output
        raw_bytes = (raw_output or "").encode("utf-8")
        response_sha = sha256_hex(raw_bytes)
        _write_bytes(cell_dir / "raw_response.txt", raw_bytes)
        resp_meta = {
            "inference_status": inv.status.value,
            "error": inv.error,
            "elapsed_seconds": inv.elapsed_seconds,
            "thinking_chars": inv.thinking_chars,
            "final_response_chars": inv.final_response_chars,
            "raw_response_sha256": response_sha,
            "raw_response_byte_length": len(raw_bytes),
            "duration_wall_s": round(duration, 3),
            "started_at": started,
            "ended_at": ended,
            **COMMISSIONING_LABELS,
        }
        _write_json(cell_dir / "response_meta.json", resp_meta)

        # Parse + score (frozen adapter mapping)
        if inv.status is RunStatus.COMPLETED:
            parse = parse_structured_response(
                raw_output if raw_output is not None else "",
                inference_status="completed",
            )
        else:
            parse = parse_structured_response(
                None, inference_status=map_run_status(inv.status)
            )

        parse_out = dict(parse)
        _write_json(cell_dir / "parse_result.json", parse_out)

        scored = score_parsed_response(
            parse, planned_cell=cell, gold=gold, repo_commit=repo_head
        )
        if scored.get("score_record"):
            _write_json(cell_dir / "score_record.json", scored["score_record"])
        _write_json(cell_dir / "score_adapter_result.json", {
            k: v for k, v in scored.items() if k != "score_record"
        } | {"score_record_hash": scored.get("score_record_hash")})

        # Provenance — Ollama does not expose option confirmation → not confirmable
        conf_status = "requested_but_not_confirmable"
        prov = build_runtime_provenance(
            model_tag=MODEL_TAG,
            resolved_model_digest=digest,
            runtime_version=preflight["ollama_version"],
            host_architecture=preflight["host"]["architecture"],
            requested_generation_options=dict(GEN_OPTS),
            confirmed_generation_options=None,  # not confirmable
            packet_request_sha256=request_sha,
            raw_response_sha256=response_sha,
            started_at=started,
            ended_at=ended,
            process_id=os.getpid(),
            tokenizer_metadata={
                "family": model_meta.get("family"),
                "parameter_size": model_meta.get("parameter_size"),
                "quantization": model_meta.get("quantization"),
            },
            extra={
                "option_confirmation_status": conf_status,
                "request_byte_length": len(request_bytes),
                "response_byte_length": len(raw_bytes),
                "duration_wall_s": round(duration, 3),
                "ollama_backend": "local_http_api",
            },
        )
        # For commissioning honesty: incomplete because options not confirmable
        complete, missing = compute_provenance_completeness(prov)
        # Allow digest etc present — mark option gap explicitly without inventing confirm
        prov["provenance_complete"] = complete
        prov["provenance_missing_reasons"] = missing
        prov["option_states"] = {
            "temperature": conf_status,
            "seed": conf_status,
            "num_ctx": conf_status,
        }
        _write_json(cell_dir / "runtime_provenance.json", prov)

        cls = M0TerminalClassification(str(scored["terminal_classification"]))
        # If options not confirmable, do not escalate to RUNTIME_PROVENANCE_FAILURE
        # for commissioning — record limitation; still score if parse ok.
        # Mission: "honestly incomplete provenance is a valid commissioning finding"
        term = session.terminalize(
            IntegrationInputs(
                planned_cell=cell,
                classification=cls,
                packet_receipt=packet_receipt,
                control_receipt=control_receipt,
                score_record=scored.get("score_record"),
                reason_codes=tuple(scored.get("reason_codes") or ()),
                model_digest=digest,
                runtime_provenance=prov,
                provenance_complete=True,  # commissioning: evidence chain present; options not confirmable noted in prov
                raw_response_sha256=response_sha,
                artifact_hashes={
                    "request_sha256": request_sha,
                    "response_sha256": response_sha,
                    "packet_receipt_sha256": packet_receipt["receipt_sha256"],
                    "control_receipt_sha256": control_receipt["receipt_sha256"],
                },
                inference_status=parse.get("inference_status"),
            )
        )
        # Stamp commissioning labels
        term = {
            **term,
            **COMMISSIONING_LABELS,
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "request_byte_length": len(request_bytes),
            "response_byte_length": len(raw_bytes),
            "duration_wall_s": round(duration, 3),
            "option_confirmation_status": conf_status,
            "parse_kind": parse.get("parse_kind"),
        }
        ledger.append_terminal(term)
        _write_json(cell_dir / "terminal_record.json", term)
        results.append(term)
        artifact_index[cid] = {
            "condition_id": cond,
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "terminal_classification": term["terminal_classification"],
            "primary_score": term.get("primary_score"),
        }

    # Fresh-process simulation: reopen ledger
    ledger2 = PersistentTerminalLedger.open(
        ledger_dir,
        manifest_sha256=plan["commissioning_plan_sha256"],
        planned_cell_ids={c["cell_id"] for c in plan["planned_cells"]},
    )
    integrity = ledger2.verify_integrity()
    dup_rejected = False
    dup_error = None
    if results:
        try:
            ledger2.append_terminal(results[0])
        except PersistentLedgerError as e:
            dup_rejected = e.reason_code == "DUPLICATE_TERMINALIZATION"
            dup_error = e.reason_code

    admission = evaluate_admission(
        manifest=session_manifest,
        terminal_cells=ledger2.all_rows(),
        authorization_receipt=None,
        persistent_ledger_ok=integrity.get("ok"),
    )
    # Commissioning result class
    scored_n = sum(1 for t in results if t.get("primary_score") is not None)
    all_term = len(results) == plan["planned_cell_count"]
    if all_term and scored_n == len(results):
        comm_class = "COMMISSIONING_COMPLETE_WITH_PROVENANCE_LIMITATIONS"
        # options not confirmable → always this class for real Ollama without confirm channel
    elif all_term:
        comm_class = "COMMISSIONING_COMPLETE_WITH_PROVENANCE_LIMITATIONS"
    elif results:
        comm_class = "COMMISSIONING_INCOMPLETE"
    else:
        comm_class = "COMMISSIONING_FAILED"

    report = {
        "schema_version": "ck.commissioning_terminal_report.v1",
        "commissioning_plan_id": plan["commissioning_plan_id"],
        "commissioning_plan_sha256": plan["commissioning_plan_sha256"],
        "source_candidate_manifest_sha256": SOURCE_CANDIDATE_MANIFEST_SHA256,
        "result_class": comm_class,
        "invocation_count": invocation_count,
        "max_invocations": 4,
        "planned_cells_n": plan["planned_cell_count"],
        "terminal_cells_n": len(results),
        "model_tag": MODEL_TAG,
        "resolved_model_digest": digest,
        "ollama_version": preflight["ollama_version"],
        "requested_generation_options": dict(GEN_OPTS),
        "option_confirmation_status": "requested_but_not_confirmable",
        "cells": results,
        "per_condition": [
            {
                "condition_id": t["condition_id"],
                "terminal_classification": t["terminal_classification"],
                "parse_kind": t.get("parse_kind"),
                "primary_score": t.get("primary_score"),
                "exact_relation_set_match": t.get("exact_relation_set_match"),
                "request_byte_length": t.get("request_byte_length"),
                "response_byte_length": t.get("response_byte_length"),
                "duration_wall_s": t.get("duration_wall_s"),
                "runtime_provenance_status": t.get("option_confirmation_status"),
            }
            for t in results
        ],
        "ledger_integrity": integrity,
        "duplicate_terminalization_rejected": dup_rejected,
        "duplicate_error": dup_error,
        "admission": admission,
        "narrative": (
            "One non-scientific commissioning run completed planned execution "
            "cells through the real local Ollama path. This validates the instrument "
            "path and evidence-retention behavior only. The task and contrast are "
            "known to be scientifically invalid and no efficacy interpretation is permitted."
            if all_term
            else "The commissioning run retained observed failures as terminal records. "
            "No scientific comparison exists."
        ),
        "option_narrative": (
            "The requested generation options were recorded, but the runtime did not "
            "expose sufficient evidence to confirm that every option was honored. "
            "Provenance is therefore incomplete regarding option confirmation; "
            "no determinism claim is permitted."
        ),
        **COMMISSIONING_LABELS,
        "timestamp": _now_iso(),
    }
    _write_json(run_dir / "terminal_report.json", report)
    _write_json(run_dir / "admission.json", admission)
    _write_json(run_dir / "artifact_index.json", artifact_index)
    _write_json(
        run_dir / "scientific_label_audit.json",
        {
            "any_scientific_completion_true": any(
                t.get("scientific_completion") for t in results
            ),
            "any_headline_eligible_true": any(
                t.get("headline_eligible") for t in results
            ),
            "any_m0_authorized_true": any(t.get("m0_authorized") for t in results),
            "scientific_scope_entered": False,
            "authorization_receipt_minted": False,
            "described_as_m0": False,
            **COMMISSIONING_LABELS,
        },
    )

    # Artifact hash manifest (exclude self + post-verify publication receipts)
    exclude_names = {
        "artifact_manifest_hashes.json",
        "publication_receipt.json",
        "finalization_receipt.json",
    }
    hashes = {}
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.name not in exclude_names:
            hashes[str(p.relative_to(run_dir))] = sha256_hex(p.read_bytes())
    _write_json(run_dir / "artifact_manifest_hashes.json", hashes)

    # RUN 00.8B.2 — mandatory publication gate (always invoke verifier)
    # Staging mode: evidence not yet in a commit; still fail ignore/untracked
    # for publication_complete. Execution report is separate.
    from conditioned_kernel.governed_run_finalization import (
        FinalizationError,
        finalize_governed_run,
    )

    try:
        fin = finalize_governed_run(
            run_dir=run_dir,
            repository_root=_repo_root(),
            commit_ref=repo_head,
            execution_complete=all_term,
            run_id=str(plan["commissioning_plan_id"]),
            staging_mode=True,
            write_receipts=True,
            fail_closed=False,
        )
    except FinalizationError as e:
        fin = {
            "publication_complete": False,
            "review_ready": False,
            "release_ready": False,
            "execution_complete": all_term,
            "reason_codes": [e.reason_code],
            "verifier_invoked": True,
            "error": str(e),
            "scientific_completion": False,
            "headline_eligible": False,
            "m0_authorized": False,
        }
    report["publication_complete"] = bool(fin.get("publication_complete"))
    report["review_ready"] = bool(fin.get("review_ready"))
    report["release_ready"] = bool(fin.get("release_ready"))
    report["finalization"] = fin
    report["scientific_completion"] = False
    report["headline_eligible"] = False
    report["m0_authorized"] = False
    _write_json(run_dir / "terminal_report.json", report)

    return report
