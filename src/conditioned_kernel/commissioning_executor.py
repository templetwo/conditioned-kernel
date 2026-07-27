"""RUN 00.8A — bounded commissioning executor (synthetic model only).

Joins:
  manifest cell → packet/control receipts → synthetic response
  → response scoring adapter → persistent ledger → admission

Synthetic model adapters only. No scientific scope without verified authorization.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping

from conditioned_kernel.control_contract import require_ratified_experiment_contract
from conditioned_kernel.evidence_verification import (
    make_control_receipt,
    make_packet_receipt,
)
from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.m0_admission import evaluate_admission, recompute_manifest_sha256
from conditioned_kernel.m0_ledger_integration import (
    IntegrationInputs,
    M0LedgerError,
    M0LedgerSession,
    M0TerminalClassification,
)
from conditioned_kernel.m0_manifest import PACKET_CONTRACT_VERSION
from conditioned_kernel.persistent_terminal_ledger import (
    PersistentLedgerError,
    PersistentTerminalLedger,
)
from conditioned_kernel.relational_scorer import sha256_hex
from conditioned_kernel.response_scoring_adapter import (
    parse_structured_response,
    score_parsed_response,
)
from conditioned_kernel.runtime_provenance import (
    COMMISSIONING_EXECUTION_SCOPE,
    SCIENTIFIC_STATUS,
    build_runtime_provenance,
    options_honored,
    synthetic_model_digest,
)

# Synthetic adapter: cell_id → raw response bytes or special codes
SyntheticResponder = Callable[[Mapping[str, Any]], bytes | str | None]


class CommissioningError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def enforce_execution_scope(
    execution_scope: str,
    *,
    experiment_contract_id: str | None = None,
    authorization_receipt: Mapping[str, Any] | None = None,
) -> None:
    """Scientific scope requires verified authorization; commissioning is closed."""
    if execution_scope == "scientific_experiment":
        try:
            require_ratified_experiment_contract(execution_scope, experiment_contract_id)
        except Exception as e:  # noqa: BLE001
            raise CommissioningError(
                getattr(e, "reason_code", "SCIENTIFIC_SCOPE_UNAUTHORIZED"),
                str(e),
            ) from e
        if authorization_receipt is None:
            raise CommissioningError(
                "SCIENTIFIC_SCOPE_UNAUTHORIZED",
                "scientific_experiment requires verified authorization receipt",
            )
        return
    if execution_scope not in (
        COMMISSIONING_EXECUTION_SCOPE,
        "dry_planning_only",
        "commissioning_validation",
    ):
        raise CommissioningError("UNKNOWN_EXECUTION_SCOPE", execution_scope)


class CommissioningExecutor:
    """End-to-end commissioning path with synthetic model adapter only."""

    def __init__(
        self,
        *,
        manifest: Mapping[str, Any],
        ledger_dir: Path | str,
        gold_by_task: Mapping[str, Mapping[str, Any]],
        responder: SyntheticResponder,
        host_architecture: str = "test-arch",
        runtime_version: str = "synthetic-runtime-00.8A",
    ) -> None:
        enforce_execution_scope(COMMISSIONING_EXECUTION_SCOPE)
        self.manifest = manifest
        self.manifest_sha256 = str(
            manifest.get("manifest_sha256") or recompute_manifest_sha256(manifest)
        )
        # Prefer recomputed integrity
        computed = recompute_manifest_sha256(manifest)
        if str(manifest.get("manifest_sha256")) != computed:
            raise CommissioningError("MANIFEST_HASH_MISMATCH", computed)
        self.manifest_sha256 = computed
        self.gold_by_task = dict(gold_by_task)
        self.responder = responder
        self.host_architecture = host_architecture
        self.runtime_version = runtime_version
        planned_ids = {str(c["cell_id"]) for c in manifest["planned_cells"]}
        self.persistent = PersistentTerminalLedger.open(
            ledger_dir,
            manifest_sha256=self.manifest_sha256,
            planned_cell_ids=planned_ids,
        )
        self.session = M0LedgerSession(manifest)
        self._run_dir = Path(ledger_dir)
        self._responses_dir = self._run_dir / "responses"
        self._responses_dir.mkdir(parents=True, exist_ok=True)

    def run_cell(self, cell_id: str) -> dict[str, Any]:
        if self.persistent.has(cell_id):
            raise CommissioningError("DUPLICATE_TERMINALIZATION", cell_id)
        planned = None
        for c in self.manifest["planned_cells"]:
            if c["cell_id"] == cell_id:
                planned = c
                break
        if planned is None:
            raise CommissioningError("UNPLANNED_CELL", cell_id)

        task_id = str(planned["task_id"])
        condition_id = str(planned["condition_id"])
        gold = self.gold_by_task.get(task_id)
        if gold is None:
            raise CommissioningError("MISSING_GOLD", task_id)

        started = utc_now_iso()
        # Packet receipt (synthetic compile evidence)
        req_body = {
            "cell_id": cell_id,
            "task_id": task_id,
            "condition_id": condition_id,
            "generation_parameters": planned["generation_parameters"],
        }
        request_sha = sha256_hex(
            __import__("json")
            .dumps(req_body, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
        )
        packet_receipt = make_packet_receipt(
            cell_id=cell_id,
            task_id=task_id,
            condition_id=condition_id,
            request_sha256=request_sha,
            complete_byte_length=128,
            packet_contract_version=PACKET_CONTRACT_VERSION,
            verdict="PASS",
        )
        control_receipt = make_control_receipt(
            cell_id=cell_id,
            task_id=task_id,
            condition_id=condition_id,
            paired_cell_id=planned.get("paired_primary_cell_id"),
            verdict="PASS",
            byte_match=True,
        )

        # Allow responder to inject failures via special planned metadata
        # or by returning special tokens — handled in parse.

        # Synthetic model call
        transport_err: str | None
        try:
            raw = self.responder(planned)
        except Exception as e:  # noqa: BLE001
            raw = None
            inference_status = "transport_error"
            transport_err = str(e)
        else:
            inference_status = "completed"
            transport_err = None

        if isinstance(raw, dict) and raw.get("_inject"):
            # Special control channel for synthetic adversarial traces
            inj = raw["_inject"]
            if inj == "timeout":
                inference_status = "timeout"
                raw = None
            elif inj == "packet_fail":
                packet_receipt = make_packet_receipt(
                    cell_id=cell_id,
                    task_id=task_id,
                    condition_id=condition_id,
                    request_sha256=request_sha,
                    complete_byte_length=0,
                    packet_contract_version=PACKET_CONTRACT_VERSION,
                    verdict="FAIL",
                    reason_codes=["PACKET_SYNTHETIC_FAIL"],
                )
                raw = raw.get("body", b"{}")
            elif inj == "control_fail":
                control_receipt = make_control_receipt(
                    cell_id=cell_id,
                    task_id=task_id,
                    condition_id=condition_id,
                    paired_cell_id=planned.get("paired_primary_cell_id"),
                    verdict="FAIL",
                    reason_codes=["CONTROL_SYNTHETIC_FAIL"],
                    byte_match=False,
                )
                raw = raw.get("body", b"{}")
            elif inj == "missing_digest":
                raw = raw.get("body", b'{"continuity_assertions":[]}')
            else:
                raw = raw.get("body")

        parse = parse_structured_response(raw, inference_status=inference_status)
        scored = score_parsed_response(
            parse,
            planned_cell=planned,
            gold=gold,
            repo_commit=str(self.manifest.get("repository_commit")),
        )

        # Persist raw response artifact
        resp_path = self._responses_dir / f"{cell_id}.raw"
        raw_bytes = b""
        if raw is not None and not isinstance(raw, dict):
            raw_bytes = raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode()
            resp_path.write_bytes(raw_bytes)

        model_tag = str(planned["model_tag"])
        digest: str | None = synthetic_model_digest(model_tag)
        if isinstance(raw, dict) and raw.get("_inject") == "missing_digest":
            digest = None

        req_opts = dict(planned["generation_parameters"])
        conf_opts = dict(req_opts)
        if isinstance(raw, dict) and raw.get("_inject") == "unverified_options":
            conf_opts = {}

        ended = utc_now_iso()
        prov = build_runtime_provenance(
            model_tag=model_tag,
            resolved_model_digest=digest,
            runtime_version=self.runtime_version,
            host_architecture=self.host_architecture,
            requested_generation_options=req_opts,
            confirmed_generation_options=conf_opts if conf_opts else None,
            packet_request_sha256=request_sha,
            raw_response_sha256=parse["raw_response_sha256"],
            started_at=started,
            ended_at=ended,
            process_id=os.getpid(),
        )
        honored, honor_reasons = options_honored(req_opts, conf_opts if conf_opts else None)
        if not honored:
            prov["provenance_missing_reasons"] = list(
                set(prov.get("provenance_missing_reasons") or []) | set(honor_reasons)
            )
            prov["provenance_complete"] = False

        cls = M0TerminalClassification(str(scored["terminal_classification"]))
        score_record = scored.get("score_record")

        # Classification overrides from packet/control already applied in terminalize
        try:
            term = self.session.terminalize(
                IntegrationInputs(
                    planned_cell=planned,
                    classification=cls,
                    reason_codes=tuple(scored.get("reason_codes") or ()),
                    score_record=score_record,
                    packet_receipt=packet_receipt,
                    control_receipt=control_receipt,
                    require_evidence_receipts=True,
                    model_digest=digest,
                    runtime_provenance=prov,
                    provenance_complete=None,  # compute
                    raw_response_sha256=parse["raw_response_sha256"],
                    artifact_hashes={
                        "raw_response_path": str(resp_path.name),
                        "raw_response_sha256": parse["raw_response_sha256"],
                    },
                    inference_status=parse.get("inference_status") or inference_status,
                )
            )
        except M0LedgerError as e:
            raise CommissioningError(e.reason_code, str(e)) from e

        try:
            self.persistent.append_terminal(term)
        except PersistentLedgerError as e:
            raise CommissioningError(e.reason_code, str(e)) from e

        term["transport_error"] = transport_err
        term["scientific_status"] = SCIENTIFIC_STATUS
        term["execution_scope"] = COMMISSIONING_EXECUTION_SCOPE
        term["m0_authorized"] = False
        return term

    def run_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for c in self.manifest["planned_cells"]:
            out.append(self.run_cell(str(c["cell_id"])))
        return out

    def admit(
        self,
        *,
        authorization_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            self.persistent.verify_integrity()
            ledger_ok = True
        except PersistentLedgerError:
            ledger_ok = False
        return evaluate_admission(
            manifest=self.manifest,
            terminal_cells=self.persistent.all_rows(),
            authorization_receipt=authorization_receipt,
            persistent_ledger_ok=ledger_ok,
        )


def default_perfect_responder(gold_by_task: Mapping[str, Mapping[str, Any]]) -> SyntheticResponder:
    """Return JSON with all expected relations for any cell."""

    def _resp(planned: Mapping[str, Any]) -> bytes:
        import json

        gold = gold_by_task[str(planned["task_id"])]
        body = {"continuity_assertions": list(gold["expected_relations"])}
        return json.dumps(body).encode("utf-8")

    return _resp
