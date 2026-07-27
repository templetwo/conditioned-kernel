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
    }
)


def map_classification_to_status(cls: M0TerminalClassification) -> TerminalStatus:
    return _CLASS_TO_STATUS[cls]


@dataclass
class IntegrationInputs:
    """Inputs for one planned-cell terminalization."""

    planned_cell: Mapping[str, Any]
    classification: M0TerminalClassification
    reason_codes: tuple[str, ...] = ()
    packet_verification_status: str = "not_run"
    control_verification_status: str = "not_run"
    inference_status: str | None = None
    scorer_status: str | None = None
    score_record: Mapping[str, Any] | None = None
    packet_request_hash: str | None = None
    control_receipt_hash: str | None = None
    model_digest: str | None = None
    runtime_provenance: Mapping[str, Any] | None = None
    provenance_complete: bool = True
    artifact_hashes: Mapping[str, str] | None = None
    terminal_timestamp: str | None = None


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

        classification = inputs.classification
        score_rec = inputs.score_record
        primary_score: float | None
        exact_match: bool | None
        score_hash: str | None
        scorer_status: str | None
        proposed_hash: str | None
        expected_hash = str(planned.get("expected_relation_hash") or "")

        if classification is M0TerminalClassification.SCORED:
            if score_rec is None:
                raise M0LedgerError("MISSING_SCORE_RECORD", cell_id)
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
                # Allow passing scorer null records for hash audit when present
                if score_rec.get("primary_score") is not None:
                    # Never allow a numeric score on null-class terminals
                    primary_score = None
                score_hash = score_record_hash(score_rec)
                proposed_hash = score_rec.get("proposed_assertion_hash")
                if score_rec.get("expected_relation_hash"):
                    expected_hash = str(score_rec["expected_relation_hash"])
        else:
            primary_score = None
            exact_match = None
            score_hash = None
            scorer_status = inputs.scorer_status
            proposed_hash = None

        # Provenance gate: incomplete → reclassify if still "SCORED"
        provenance_complete = bool(inputs.provenance_complete)
        reason_codes = list(inputs.reason_codes)
        final_cls = classification
        if not provenance_complete and classification is M0TerminalClassification.SCORED:
            final_cls = M0TerminalClassification.PROVENANCE_INCOMPLETE
            primary_score = None
            exact_match = None
            reason_codes = ["PROVENANCE_INCOMPLETE", *reason_codes]
            scorer_status = "PROVENANCE_INCOMPLETE"

        if not reason_codes:
            reason_codes = [final_cls.value]

        ts = inputs.terminal_timestamp or utc_now_iso()
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
            "packet_verification_status": inputs.packet_verification_status,
            "control_verification_status": inputs.control_verification_status,
            "inference_status": inputs.inference_status,
            "scorer_status": scorer_status,
            "primary_score": primary_score,
            "exact_relation_set_match": exact_match,
            "score_record_hash": score_hash,
            "packet_request_hash": inputs.packet_request_hash,
            "control_receipt_hash": inputs.control_receipt_hash,
            "expected_relation_hash": expected_hash,
            "proposed_assertion_hash": proposed_hash,
            "model_tag": planned["model_tag"],
            "model_digest": inputs.model_digest,
            "generation_parameters": dict(planned["generation_parameters"]),
            "runtime_provenance": dict(inputs.runtime_provenance or {}),
            "provenance_completeness": provenance_complete,
            "artifact_hashes": dict(inputs.artifact_hashes or {}),
            "terminal_timestamp": ts,
            "scientific_completion": False,
            "headline_eligible": False,
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
                "packet_verification_status": inputs.packet_verification_status,
                "control_verification_status": inputs.control_verification_status,
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


def terminalize_synthetic(
    session: M0LedgerSession,
    *,
    cell_id: str,
    classification: M0TerminalClassification,
    score_record: Mapping[str, Any] | None = None,
    reason_codes: Sequence[str] = (),
    packet_verification_status: str = "pass",
    control_verification_status: str = "pass",
    inference_status: str | None = None,
    provenance_complete: bool = True,
    model_digest: str | None = "sha256:fixture",
    runtime_provenance: Mapping[str, Any] | None = None,
    packet_request_hash: str | None = None,
    control_receipt_hash: str | None = None,
) -> dict[str, Any]:
    pc = session._planned_by_id[cell_id]
    return session.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=classification,
            reason_codes=tuple(reason_codes),
            packet_verification_status=packet_verification_status,
            control_verification_status=control_verification_status,
            inference_status=inference_status or classification.value.lower(),
            scorer_status=(
                "SCORED"
                if classification is M0TerminalClassification.SCORED
                else classification.value
            ),
            score_record=score_record,
            packet_request_hash=packet_request_hash,
            control_receipt_hash=control_receipt_hash,
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
