"""RUN 00.6F — planned-cell → TerminalLedger integration adapter.

Uses existing TerminalLedger (exactly one terminal row per planned cell).
Does not decide scientific headlines. Always scientific_completion=false
and headline_eligible=false on M0 terminal records.

Offline dry integration only in this run — no model invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from conditioned_kernel.ids import utc_now_iso
from conditioned_kernel.m0_manifest import (
    TERMINAL_CELL_SCHEMA_VERSION,
    manifest_to_manifest_cells,
)
from conditioned_kernel.outcomes import (
    ExecutionOutcome,
    TerminalLedger,
    TerminalLedgerError,
    TerminalStatus,
)
from conditioned_kernel.relational_scorer import score_record_hash


class M0LedgerError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


class M0TerminalClassification(str, Enum):
    SCORED = "SCORED"
    TIMEOUT = "TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    NO_FINAL_RESPONSE = "NO_FINAL_RESPONSE"
    MALFORMED_ASSERTIONS = "MALFORMED_ASSERTIONS"
    PACKET_CONTRACT_FAILED = "PACKET_CONTRACT_FAILED"
    CONTROL_CONTRACT_FAILED = "CONTROL_CONTRACT_FAILED"
    TASK_CONTRACT_ERROR = "TASK_CONTRACT_ERROR"
    SCORER_INTERNAL_ERROR = "SCORER_INTERNAL_ERROR"
    UPSTREAM_STATE_UNAVAILABLE = "UPSTREAM_STATE_UNAVAILABLE"
    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    INTERNAL_EXECUTION_ERROR = "INTERNAL_EXECUTION_ERROR"
    RUNTIME_PROVENANCE_FAILURE = "RUNTIME_PROVENANCE_FAILURE"


# Map M0 classification → existing TerminalStatus (no enum redesign).
_CLASS_TO_STATUS: dict[M0TerminalClassification, TerminalStatus] = {
    M0TerminalClassification.SCORED: TerminalStatus.COMPLETED_VALID,
    M0TerminalClassification.TIMEOUT: TerminalStatus.TIMEOUT,
    M0TerminalClassification.TRANSPORT_ERROR: TerminalStatus.TRANSPORT_ERROR,
    M0TerminalClassification.INVALID_RESPONSE: TerminalStatus.INVALID_RESPONSE,
    M0TerminalClassification.NO_FINAL_RESPONSE: TerminalStatus.NO_FINAL_RESPONSE,
    M0TerminalClassification.MALFORMED_ASSERTIONS: TerminalStatus.PARSE_FAILED,
    M0TerminalClassification.PACKET_CONTRACT_FAILED: TerminalStatus.SCHEMA_FAILED,
    M0TerminalClassification.CONTROL_CONTRACT_FAILED: TerminalStatus.COMPLETED_INVALID,
    M0TerminalClassification.TASK_CONTRACT_ERROR: TerminalStatus.SEMANTIC_FAILED,
    M0TerminalClassification.SCORER_INTERNAL_ERROR: TerminalStatus.COMPLETED_INVALID,
    M0TerminalClassification.UPSTREAM_STATE_UNAVAILABLE: TerminalStatus.NOT_RUN,
    M0TerminalClassification.PROVENANCE_INCOMPLETE: TerminalStatus.COMPLETED_INVALID,
    M0TerminalClassification.INTERNAL_EXECUTION_ERROR: TerminalStatus.COMPLETED_INVALID,
    M0TerminalClassification.RUNTIME_PROVENANCE_FAILURE: TerminalStatus.COMPLETED_INVALID,
}

_NULL_SCORE_CLASSES = frozenset(
    {
        M0TerminalClassification.TIMEOUT,
        M0TerminalClassification.TRANSPORT_ERROR,
        M0TerminalClassification.INVALID_RESPONSE,
        M0TerminalClassification.NO_FINAL_RESPONSE,
        M0TerminalClassification.MALFORMED_ASSERTIONS,
        M0TerminalClassification.PACKET_CONTRACT_FAILED,
        M0TerminalClassification.CONTROL_CONTRACT_FAILED,
        M0TerminalClassification.TASK_CONTRACT_ERROR,
        M0TerminalClassification.SCORER_INTERNAL_ERROR,
        M0TerminalClassification.UPSTREAM_STATE_UNAVAILABLE,
        M0TerminalClassification.PROVENANCE_INCOMPLETE,
        M0TerminalClassification.INTERNAL_EXECUTION_ERROR,
        M0TerminalClassification.RUNTIME_PROVENANCE_FAILURE,
    }
)


def map_classification_to_status(cls: M0TerminalClassification) -> TerminalStatus:
    return _CLASS_TO_STATUS[cls]


@dataclass
class IntegrationInputs:
    """Inputs for one planned-cell terminalization.

    RUN 00.8A.1 — evidence receipts are mandatory. Packet/control status is
    derived only from verified canonical receipts. Caller-supplied
    packet/control status strings are non-authoritative diagnostics only and
    never decide terminal validity.

    Schema surface: ``ck.terminal_integration.v2`` (v1 optional-receipt bypass
    removed; no production flag turns verification off).
    """

    planned_cell: Mapping[str, Any]
    classification: M0TerminalClassification
    packet_receipt: Mapping[str, Any]
    control_receipt: Mapping[str, Any]
    reason_codes: tuple[str, ...] = ()
    # Non-authoritative diagnostics only (ignored for pass/fail derivation).
    packet_verification_status_diagnostic: str | None = None
    control_verification_status_diagnostic: str | None = None
    inference_status: str | None = None
    scorer_status: str | None = None
    score_record: Mapping[str, Any] | None = None
    packet_request_hash: str | None = None
    control_receipt_hash: str | None = None
    model_digest: str | None = None
    runtime_provenance: Mapping[str, Any] | None = None
    provenance_complete: bool | None = None  # None → compute from runtime_provenance
    artifact_hashes: Mapping[str, str] | None = None
    terminal_timestamp: str | None = None
    raw_response_sha256: str | None = None


class M0LedgerSession:
    """Append-only integration over TerminalLedger + terminal_cell.v1 records."""

    def __init__(self, manifest: Mapping[str, Any]) -> None:
        self.manifest = manifest
        self.manifest_id = str(manifest["manifest_id"])
        self._planned_by_id: dict[str, dict[str, Any]] = {
            str(c["cell_id"]): dict(c) for c in manifest["planned_cells"]
        }
        mcells = manifest_to_manifest_cells(manifest)
        self._ledger = TerminalLedger(mcells, run_id=self.manifest_id)
        self._terminal_cells: dict[str, dict[str, Any]] = {}

    @property
    def ledger(self) -> TerminalLedger:
        return self._ledger

    @property
    def planned_cell_ids(self) -> tuple[str, ...]:
        return tuple(self._planned_by_id.keys())

    def terminal_cells(self) -> list[dict[str, Any]]:
        return [self._terminal_cells[cid] for cid in self._planned_by_id if cid in self._terminal_cells]

    def terminalize(self, inputs: IntegrationInputs) -> dict[str, Any]:
        """Emit exactly one terminal record for a planned cell. Fail closed on dups/unplanned."""
        from conditioned_kernel.evidence_verification import (
            verify_control_receipt,
            verify_packet_receipt,
        )
        from conditioned_kernel.runtime_provenance import compute_provenance_completeness

        pc = inputs.planned_cell
        cell_id = str(pc["cell_id"])
        manifest_id = str(pc.get("manifest_id") or self.manifest_id)

        if cell_id not in self._planned_by_id:
            raise M0LedgerError("UNPLANNED_CELL", cell_id)
        if manifest_id != self.manifest_id:
            raise M0LedgerError("WRONG_MANIFEST_ID", manifest_id)
        if cell_id in self._terminal_cells:
            raise M0LedgerError("DUPLICATE_TERMINALIZATION", cell_id)

        planned = self._planned_by_id[cell_id]
        planned_hash = str(planned.get("planned_cell_hash") or "")
        # Planned expected hash is authoritative — never overwrite from score.
        expected_hash = str(planned.get("expected_relation_hash") or "")

        reason_codes = list(inputs.reason_codes)
        classification = inputs.classification

        # --- Evidence-derived packet/control status (00.8A.1: always mandatory) ---
        # Caller-supplied status strings are never authority.
        if inputs.packet_receipt is None:
            raise M0LedgerError("PACKET_RECEIPT_REQUIRED", cell_id)
        if inputs.control_receipt is None:
            raise M0LedgerError("CONTROL_RECEIPT_REQUIRED", cell_id)

        p_st, p_hash, p_reasons = verify_packet_receipt(
            inputs.packet_receipt,
            cell_id=cell_id,
            task_id=str(planned["task_id"]),
            condition_id=str(planned["condition_id"]),
        )
        packet_status = p_st
        packet_receipt_hash = p_hash
        if p_st != "pass":
            classification = M0TerminalClassification.PACKET_CONTRACT_FAILED
            reason_codes = (
                ["EVIDENCE_RECEIPT_UNVERIFIED", *p_reasons] + reason_codes
                if p_reasons
                else ["EVIDENCE_RECEIPT_UNVERIFIED"] + reason_codes
            )
            if any("MISMATCH" in r for r in p_reasons):
                reason_codes = ["EVIDENCE_RECEIPT_CELL_MISMATCH", *reason_codes]

        c_st, c_hash, c_reasons = verify_control_receipt(
            inputs.control_receipt,
            cell_id=cell_id,
            task_id=str(planned["task_id"]),
            condition_id=str(planned["condition_id"]),
        )
        control_status = c_st
        control_receipt_hash = c_hash
        if c_st != "pass" and classification is not (
            M0TerminalClassification.PACKET_CONTRACT_FAILED
        ):
            classification = M0TerminalClassification.CONTROL_CONTRACT_FAILED
            reason_codes = (
                ["EVIDENCE_RECEIPT_UNVERIFIED", *c_reasons] + reason_codes
                if c_reasons
                else ["EVIDENCE_RECEIPT_UNVERIFIED"] + reason_codes
            )
            if any("MISMATCH" in r for r in c_reasons):
                reason_codes = ["EVIDENCE_RECEIPT_CELL_MISMATCH", *reason_codes]

        score_rec = inputs.score_record
        primary_score: float | None
        exact_match: bool | None
        score_hash: str | None
        scorer_status: str | None
        proposed_hash: str | None

        if classification is M0TerminalClassification.SCORED:
            if score_rec is None:
                raise M0LedgerError("SCORED_WITHOUT_SCORE_RECORD", cell_id)
            # Score-to-cell binding
            if str(score_rec.get("task_id") or "") not in (
                "",
                str(planned["task_id"]),
            ):
                raise M0LedgerError("SCORE_CELL_MISMATCH", "task_id")
            if str(score_rec.get("condition_id") or "") not in (
                "",
                str(planned["condition_id"]),
            ):
                raise M0LedgerError("SCORE_CELL_MISMATCH", "condition_id")
            score_exp = score_rec.get("expected_relation_hash")
            if score_exp and expected_hash and str(score_exp) != expected_hash:
                raise M0LedgerError("SCORE_EXPECTED_HASH_MISMATCH", cell_id)
            score_schema = score_rec.get("scorer_schema_version") or score_rec.get(
                "schema_version"
            )
            if score_schema and str(score_schema) != str(
                planned.get("scorer_schema_version")
            ):
                raise M0LedgerError("SCORE_SCHEMA_MISMATCH", cell_id)
            tc_ver = score_rec.get("task_contract_version")
            if tc_ver and str(tc_ver) != str(planned.get("task_contract_version")):
                raise M0LedgerError("SCORE_CELL_MISMATCH", "task_contract_version")

            primary_score = score_rec.get("primary_score")
            exact_match = score_rec.get("exact_relation_set_match")
            score_hash = score_record_hash(score_rec)
            scorer_status = str(
                inputs.scorer_status or score_rec.get("scoring_status") or "SCORED"
            )
            proposed_hash = score_rec.get("proposed_assertion_hash")
        elif classification in _NULL_SCORE_CLASSES:
            primary_score = None
            exact_match = None
            score_hash = None
            scorer_status = inputs.scorer_status or classification.value
            proposed_hash = None
            if score_rec is not None:
                score_hash = score_record_hash(score_rec)
                proposed_hash = score_rec.get("proposed_assertion_hash")
                # Do NOT overwrite planned expected_hash from score
        else:
            primary_score = None
            exact_match = None
            score_hash = None
            scorer_status = inputs.scorer_status
            proposed_hash = None

        # Provenance: derive when None; explicit True remains fixture-path allowed
        # once evidence receipts have already been verified above.
        runtime_prov = dict(inputs.runtime_provenance or {})
        if inputs.provenance_complete is None:
            provenance_complete, missing = compute_provenance_completeness(runtime_prov)
            if missing:
                reason_codes = list(missing) + reason_codes
        else:
            provenance_complete = bool(inputs.provenance_complete)

        final_cls = classification
        if (
            not provenance_complete
            and final_cls is M0TerminalClassification.SCORED
        ):
            if "RUNTIME_PROVENANCE_FAILURE" in reason_codes:
                final_cls = M0TerminalClassification.RUNTIME_PROVENANCE_FAILURE
            else:
                final_cls = M0TerminalClassification.PROVENANCE_INCOMPLETE
            primary_score = None
            exact_match = None
            reason_codes = ["PROVENANCE_INCOMPLETE", *reason_codes]
            scorer_status = final_cls.value

        if not reason_codes:
            reason_codes = [final_cls.value]

        ts = inputs.terminal_timestamp or utc_now_iso()
        model_digest = inputs.model_digest or runtime_prov.get("resolved_model_digest")
        term: dict[str, Any] = {
            "schema_version": TERMINAL_CELL_SCHEMA_VERSION,
            "cell_id": cell_id,
            "manifest_id": self.manifest_id,
            "task_id": planned["task_id"],
            "condition_id": planned["condition_id"],
            "replicate_id": planned["replicate_id"],
            "planned_cell_hash": planned_hash,
            "terminal_classification": final_cls.value,
            "terminal_reason_codes": reason_codes,
            "packet_verification_status": packet_status,
            "control_verification_status": control_status,
            "inference_status": inputs.inference_status,
            "scorer_status": scorer_status,
            "primary_score": primary_score,
            "exact_relation_set_match": exact_match,
            "score_record_hash": score_hash,
            "packet_request_hash": packet_receipt_hash,
            "control_receipt_hash": control_receipt_hash,
            "expected_relation_hash": expected_hash,
            "proposed_assertion_hash": proposed_hash,
            "model_tag": planned["model_tag"],
            "model_digest": model_digest,
            "generation_parameters": dict(planned["generation_parameters"]),
            "runtime_provenance": runtime_prov,
            "provenance_completeness": provenance_complete,
            "artifact_hashes": dict(inputs.artifact_hashes or {}),
            "raw_response_sha256": inputs.raw_response_sha256,
            "terminal_timestamp": ts,
            "scientific_completion": False,
            "headline_eligible": False,
            "scientific_status": "commissioning_safety_only",
            "execution_scope": "commissioning_validation",
            "m0_authorized": False,
        }

        status = map_classification_to_status(final_cls)
        # Operational failures must have output=None; SCORED may carry marker only.
        output: str | None = None
        if final_cls is M0TerminalClassification.SCORED and primary_score is not None:
            output = json_marker_scored(primary_score)

        outcome = ExecutionOutcome(
            status=status,
            output=output,
            scientific_completion=False,
            dry_run=False,
            quality_admitted=False,
            decision=None,
            reason_codes=tuple(reason_codes),
            error=None if final_cls is M0TerminalClassification.SCORED else final_cls.value,
            manifest_cell_id=cell_id,
            task_id=str(planned["task_id"]),
            condition_id=str(planned["condition_id"]),
            episode=None,
            run_id=self.manifest_id,
            candidate_id=None,
            blocked_by_manifest_cell_id=None,
            inference={
                "status": inputs.inference_status,
                "m0_terminal_classification": final_cls.value,
            },
            phase_receipts={
                "m0_terminal_classification": final_cls.value,
                "packet_verification_status": packet_status,
                "control_verification_status": control_status,
                "scorer_status": scorer_status,
                "primary_score": primary_score,
                "score_record_hash": score_hash,
                "scientific_completion": False,
                "headline_eligible": False,
            },
            started_at=None,
            ended_at=ts,
            provenance={
                "model_tag": planned["model_tag"],
                "model_digest": inputs.model_digest,
                "generation_parameters": dict(planned["generation_parameters"]),
                "runtime_provenance": dict(inputs.runtime_provenance or {}),
                "provenance_completeness": provenance_complete,
                "planned_cell_hash": planned_hash,
            },
        )

        try:
            self._ledger.record(cell_id, outcome)
        except TerminalLedgerError as e:
            msg = str(e)
            if "UNPLANNED_CELL" in msg:
                raise M0LedgerError("UNPLANNED_CELL", cell_id) from e
            if "DUPLICATE_TERMINALIZATION" in msg:
                raise M0LedgerError("DUPLICATE_TERMINALIZATION", cell_id) from e
            raise M0LedgerError("LEDGER_RECORD_FAILED", msg) from e

        self._terminal_cells[cell_id] = term
        return term

    def validate_complete(self) -> bool:
        self._ledger.validate()
        if len(self._terminal_cells) != len(self._planned_by_id):
            raise M0LedgerError(
                "INCOMPLETE_TERMINALIZATION",
                f"{len(self._terminal_cells)}/{len(self._planned_by_id)}",
            )
        return True


def json_marker_scored(score: float) -> str:
    """Minimal non-null output marker for SCORED COMPLETED_VALID rows."""
    return f'{{"m0_scored":true,"primary_score":{score!r}}}'


def synthetic_pass_receipts(planned_cell: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Canonical synthetic PASS receipts for offline fixtures (not caller PASS strings)."""
    from conditioned_kernel.evidence_verification import (
        make_control_receipt,
        make_packet_receipt,
    )
    from conditioned_kernel.m0_manifest import PACKET_CONTRACT_VERSION

    cell_id = str(planned_cell["cell_id"])
    task_id = str(planned_cell["task_id"])
    condition_id = str(planned_cell["condition_id"])
    packet = make_packet_receipt(
        cell_id=cell_id,
        task_id=task_id,
        condition_id=condition_id,
        request_sha256="ab" * 32,
        complete_byte_length=64,
        packet_contract_version=PACKET_CONTRACT_VERSION,
        verdict="PASS",
    )
    control = make_control_receipt(
        cell_id=cell_id,
        task_id=task_id,
        condition_id=condition_id,
        paired_cell_id=planned_cell.get("paired_primary_cell_id"),
        verdict="PASS",
        byte_match=True,
    )
    return packet, control


def terminalize_synthetic(
    session: M0LedgerSession,
    *,
    cell_id: str,
    classification: M0TerminalClassification,
    score_record: Mapping[str, Any] | None = None,
    reason_codes: Sequence[str] = (),
    inference_status: str | None = None,
    provenance_complete: bool = True,
    model_digest: str | None = "sha256:fixture",
    runtime_provenance: Mapping[str, Any] | None = None,
    packet_receipt: Mapping[str, Any] | None = None,
    control_receipt: Mapping[str, Any] | None = None,
    # Legacy kwargs: map status strings to synthetic FAIL/PASS *receipts*
    # (never used as authority strings on the terminalize path).
    packet_verification_status: str = "pass",
    control_verification_status: str = "pass",
) -> dict[str, Any]:
    """Offline helper: always supplies verified synthetic receipts.

    Caller PASS/FAIL strings only select which synthetic receipt artifact to
    build; terminalize derives status from those receipts alone.
    """
    from conditioned_kernel.evidence_verification import (
        make_control_receipt,
        make_packet_receipt,
    )
    from conditioned_kernel.m0_manifest import PACKET_CONTRACT_VERSION

    pc = session._planned_by_id[cell_id]
    cell_id_s = str(pc["cell_id"])
    task_id = str(pc["task_id"])
    condition_id = str(pc["condition_id"])

    if packet_receipt is None:
        p_verdict = (
            "FAIL"
            if str(packet_verification_status).lower() in ("fail", "failed")
            else "PASS"
        )
        packet_receipt = make_packet_receipt(
            cell_id=cell_id_s,
            task_id=task_id,
            condition_id=condition_id,
            request_sha256="ab" * 32,
            complete_byte_length=64 if p_verdict == "PASS" else 0,
            packet_contract_version=PACKET_CONTRACT_VERSION,
            verdict=p_verdict,
            reason_codes=["PACKET_SYNTHETIC_FAIL"] if p_verdict == "FAIL" else [],
        )
    if control_receipt is None:
        c_verdict = (
            "FAIL"
            if str(control_verification_status).lower() in ("fail", "failed")
            else "PASS"
        )
        control_receipt = make_control_receipt(
            cell_id=cell_id_s,
            task_id=task_id,
            condition_id=condition_id,
            paired_cell_id=pc.get("paired_primary_cell_id"),
            verdict=c_verdict,
            reason_codes=["CONTROL_SYNTHETIC_FAIL"] if c_verdict == "FAIL" else [],
            byte_match=c_verdict == "PASS",
        )
    return session.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=classification,
            packet_receipt=packet_receipt,
            control_receipt=control_receipt,
            reason_codes=tuple(reason_codes),
            inference_status=inference_status or classification.value.lower(),
            scorer_status=(
                "SCORED"
                if classification is M0TerminalClassification.SCORED
                else classification.value
            ),
            score_record=score_record,
            model_digest=model_digest,
            runtime_provenance=runtime_provenance
            or {"backend": "offline_fixture", "model_tag": pc["model_tag"]},
            provenance_complete=provenance_complete,
        )
    )


def complete_all_scored_fixture(
    session: M0LedgerSession,
    score_record_factory,
) -> list[dict[str, Any]]:
    """Terminalize every planned cell as SCORED with factory(planned_cell)->score."""
    out: list[dict[str, Any]] = []
    for cid in session.planned_cell_ids:
        pc = session._planned_by_id[cid]
        rec = score_record_factory(pc)
        out.append(
            terminalize_synthetic(
                session,
                cell_id=cid,
                classification=M0TerminalClassification.SCORED,
                score_record=rec,
                inference_status="completed",
            )
        )
    return out
