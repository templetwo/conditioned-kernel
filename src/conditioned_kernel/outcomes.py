"""Canonical typed terminal outcomes and manifest-derived terminal ledger.

RUN 00.6A: one typed path for product, matrix, continuity, experiment, and
dry-run execution. Inference-layer outcomes remain in generate.RunStatus /
InferenceResult; this module projects them into lifecycle TerminalStatus and
enforces exactly-one terminal row per planned manifest cell.

Scientific completion is ONLY TerminalStatus.COMPLETED_VALID.
DRY_RUN_ONLY can never satisfy scientific completion.
Unknown statuses fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from conditioned_kernel.generate import InferenceResult, RunStatus
from conditioned_kernel.ids import make_id, utc_now_iso


class TerminalStatus(str, Enum):
    """Lifecycle-terminal status for one planned experiment/product cell.

    Inference-layer RunStatus values map into the operational subset
    (TIMEOUT, TRANSPORT_ERROR, INVALID_RESPONSE, NO_FINAL_RESPONSE).
    Lifecycle layers add parse/schema/semantic/dry/not-run distinctions.
    COMPLETED (RunStatus) is not terminal by itself — acceptance finalizes
    COMPLETED_VALID or a more specific failure.
    """

    COMPLETED_VALID = "completed_valid"
    COMPLETED_INVALID = "completed_invalid"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    INVALID_RESPONSE = "invalid_response"
    NO_FINAL_RESPONSE = "no_final_response"
    PARSE_FAILED = "parse_failed"
    SCHEMA_FAILED = "schema_failed"
    SEMANTIC_FAILED = "semantic_failed"
    NOT_RUN = "not_run"
    DRY_RUN_ONLY = "dry_run_only"


# Inference operational failures that are already terminal.
_INFERENCE_TERMINAL: dict[RunStatus, TerminalStatus] = {
    RunStatus.TIMEOUT: TerminalStatus.TIMEOUT,
    RunStatus.TRANSPORT_ERROR: TerminalStatus.TRANSPORT_ERROR,
    RunStatus.INVALID_RESPONSE: TerminalStatus.INVALID_RESPONSE,
    RunStatus.NO_FINAL_RESPONSE: TerminalStatus.NO_FINAL_RESPONSE,
}

# String aliases accepted by classify_unknown_status (fail-closed otherwise).
_STATUS_ALIASES: dict[str, TerminalStatus] = {
    **{s.value: s for s in TerminalStatus},
    # Inference-layer RunStatus values
    RunStatus.COMPLETED.value: TerminalStatus.COMPLETED_INVALID,  # not yet valid
    RunStatus.TIMEOUT.value: TerminalStatus.TIMEOUT,
    RunStatus.TRANSPORT_ERROR.value: TerminalStatus.TRANSPORT_ERROR,
    RunStatus.INVALID_RESPONSE.value: TerminalStatus.INVALID_RESPONSE,
    RunStatus.NO_FINAL_RESPONSE.value: TerminalStatus.NO_FINAL_RESPONSE,
    # Legacy row labels that are not scientific completion
    "completed": TerminalStatus.COMPLETED_INVALID,
    "error": TerminalStatus.TRANSPORT_ERROR,
    "dry": TerminalStatus.DRY_RUN_ONLY,
    "dry_run": TerminalStatus.DRY_RUN_ONLY,
}


class TerminalLedgerError(ValueError):
    """Duplicate or missing terminal rows relative to a planned manifest."""


class EmptyManifestError(ValueError):
    """Planned manifest has zero cells — not a valid completed scientific run.

    reason_code is always EMPTY_MANIFEST for machine-readable detection.
    """

    reason_code = "EMPTY_MANIFEST"

    def __init__(self, message: str = "EMPTY_MANIFEST: planned manifest has zero cells") -> None:
        super().__init__(message)
        self.reason_code = EmptyManifestError.reason_code


class ViolationClassificationError(ValueError):
    """Unknown violation category — fail closed rather than guess."""

    reason_code = "UNKNOWN_VIOLATION_CATEGORY"

    def __init__(self, violation: str) -> None:
        super().__init__(
            f"UNKNOWN_VIOLATION_CATEGORY: cannot classify violation {violation!r}"
        )
        self.violation = violation
        self.reason_code = ViolationClassificationError.reason_code


# ---------------------------------------------------------------------------
# Structured violation → terminal status mapping (no substring heuristics)
# ---------------------------------------------------------------------------
#
# Categories are matched by exact token or by documented prefix. Membership
# of an incidental substring inside a free-form string is never used.
# All required_section:<field> share SCHEMA_FAILED.

_SCHEMA_EXACT: frozenset[str] = frozenset(
    {
        "missing_answer",
        "template_echo",
    }
)
_SCHEMA_PREFIXES: tuple[str, ...] = (
    "required_section:",
    "parse_failed:",
    "max_words_exceeded:",
)

_SEMANTIC_EXACT: frozenset[str] = frozenset(
    {
        "goal_echo",
        "not_responsive",
        "goal_not_referenced",
        "template_echo_evidence",
        "evidence_used_empty",
    }
)
_SEMANTIC_PREFIXES: tuple[str, ...] = (
    "evidence_too_short:",
    "evidence_not_in_packet:",
    "forbidden:",
    "contradicts_facts:",
    "unknown_thread_touch:",
)


def classify_violation_token(violation: str) -> TerminalStatus:
    """Map one validator violation string to SCHEMA_FAILED or SEMANTIC_FAILED.

    Matching is structural:
    - exact equality against a closed allowlist, or
    - documented prefix (category:) at the start of the token.

    Unknown categories raise ViolationClassificationError (fail closed).
    The original violation text is never rewritten.
    """
    if not isinstance(violation, str) or not violation.strip():
        raise ViolationClassificationError(str(violation))
    token = violation.strip()

    if token in _SCHEMA_EXACT:
        return TerminalStatus.SCHEMA_FAILED
    for prefix in _SCHEMA_PREFIXES:
        if token.startswith(prefix):
            # required_section:<any field> is always SCHEMA_FAILED.
            return TerminalStatus.SCHEMA_FAILED

    if token in _SEMANTIC_EXACT:
        return TerminalStatus.SEMANTIC_FAILED
    for prefix in _SEMANTIC_PREFIXES:
        if token.startswith(prefix):
            return TerminalStatus.SEMANTIC_FAILED

    raise ViolationClassificationError(token)


def classify_violations(violations: Sequence[Any]) -> TerminalStatus:
    """Classify a list of violation tokens.

    Precedence: any SCHEMA_FAILED wins over SEMANTIC_FAILED (schema precedes
    semantic in the lifecycle). Unknown categories fail closed.
    Empty list is not classifiable — callers must handle "no violations".
    """
    if not violations:
        raise ValueError("classify_violations requires a non-empty violation list")
    statuses: list[TerminalStatus] = []
    for v in violations:
        statuses.append(classify_violation_token(str(v)))
    if TerminalStatus.SCHEMA_FAILED in statuses:
        return TerminalStatus.SCHEMA_FAILED
    if TerminalStatus.SEMANTIC_FAILED in statuses:
        return TerminalStatus.SEMANTIC_FAILED
    # Unreachable if classify_violation_token only returns those two.
    raise ViolationClassificationError(str(violations[0]))


def classify_inference(status: RunStatus | str) -> TerminalStatus | None:
    """Map inference RunStatus to a terminal status, or None if lifecycle continues.

    COMPLETED is not terminal: parse/validate/accept still run.
    All other RunStatus values are immediately terminal.
    """
    if isinstance(status, str):
        try:
            status = RunStatus(status)
        except ValueError as e:
            raise ValueError(f"unknown inference status: {status!r}") from e
    if status is RunStatus.COMPLETED:
        return None
    mapped = _INFERENCE_TERMINAL.get(status)
    if mapped is None:
        raise ValueError(f"unknown inference status: {status!r}")
    return mapped


def classify_unknown_status(status: Any) -> TerminalStatus:
    """Resolve a status token to TerminalStatus. Unknown values fail closed."""
    if status is None:
        raise ValueError("unknown status: None")
    if isinstance(status, TerminalStatus):
        return status
    if isinstance(status, RunStatus):
        # COMPLETED alone is not scientifically complete; map conservatively.
        if status is RunStatus.COMPLETED:
            return TerminalStatus.COMPLETED_INVALID
        terminal = classify_inference(status)
        if terminal is None:
            return TerminalStatus.COMPLETED_INVALID
        return terminal
    if not isinstance(status, str) or not status:
        raise ValueError(f"unknown status: {status!r}")
    key = status.strip().lower()
    if key not in _STATUS_ALIASES:
        raise ValueError(f"unknown status: {status!r}")
    return _STATUS_ALIASES[key]


def is_scientific_completion(outcome: "ExecutionOutcome | TerminalStatus") -> bool:
    """True only for COMPLETED_VALID. Dry runs and all failures are excluded."""
    if isinstance(outcome, ExecutionOutcome):
        return (
            outcome.status is TerminalStatus.COMPLETED_VALID
            and outcome.scientific_completion is True
            and outcome.dry_run is False
        )
    return outcome is TerminalStatus.COMPLETED_VALID


@dataclass(frozen=True)
class ManifestCell:
    """One planned execution cell. Identity is content-derived and stable.

    Optional ``cell_id_override`` (RUN 00.6F) allows a precomputed deterministic
    identity (e.g. SHA-256 of canonical planned-cell fields) without changing
    the default colon-joined scheme used by existing matrix/continuity paths.
    """

    run_id: str
    task_id: str
    condition_id: str
    episode: str | None = None
    replicate_id: str = "0"
    cell_id_override: str | None = None

    @property
    def cell_id(self) -> str:
        if self.cell_id_override is not None:
            return self.cell_id_override
        ep = self.episode if self.episode is not None else "-"
        return f"{self.run_id}:{self.task_id}:{self.condition_id}:{ep}:{self.replicate_id}"


@dataclass(frozen=True)
class ExecutionOutcome:
    """Immutable terminal (or dry) outcome for one planned cell / product turn."""

    status: TerminalStatus
    output: str | None
    scientific_completion: bool
    dry_run: bool
    quality_admitted: bool
    decision: str | None = None
    reason_codes: tuple[str, ...] = ()
    error: str | None = None
    manifest_cell_id: str | None = None
    task_id: str | None = None
    condition_id: str | None = None
    episode: str | None = None
    run_id: str | None = None
    candidate_id: str | None = None
    blocked_by_manifest_cell_id: str | None = None
    inference: dict[str, Any] | None = None
    phase_receipts: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    ended_at: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Hard invariants — freeze closed.
        if self.status is TerminalStatus.DRY_RUN_ONLY:
            if self.scientific_completion:
                raise ValueError("DRY_RUN_ONLY cannot have scientific_completion=True")
            if self.output is not None:
                raise ValueError("DRY_RUN_ONLY must have output=None (fixture is separate)")
            if not self.dry_run:
                raise ValueError("DRY_RUN_ONLY requires dry_run=True")
        if self.scientific_completion and self.status is not TerminalStatus.COMPLETED_VALID:
            raise ValueError(
                f"scientific_completion requires COMPLETED_VALID, got {self.status.value}"
            )
        if self.status is TerminalStatus.COMPLETED_VALID and self.dry_run:
            raise ValueError("COMPLETED_VALID cannot be a dry run")
        # Operational / non-observed terminals must never carry an answer string.
        if self.status in (
            TerminalStatus.TIMEOUT,
            TerminalStatus.TRANSPORT_ERROR,
            TerminalStatus.INVALID_RESPONSE,
            TerminalStatus.NO_FINAL_RESPONSE,
            TerminalStatus.NOT_RUN,
            TerminalStatus.DRY_RUN_ONLY,
        ) and self.output is not None:
            raise ValueError(f"{self.status.value} must have output=None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "output": self.output,
            "scientific_completion": self.scientific_completion,
            "dry_run": self.dry_run,
            "quality_admitted": self.quality_admitted,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "error": self.error,
            "manifest_cell_id": self.manifest_cell_id,
            "task_id": self.task_id,
            "condition_id": self.condition_id,
            "episode": self.episode,
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "blocked_by_manifest_cell_id": self.blocked_by_manifest_cell_id,
            "inference": self.inference,
            "phase_receipts": dict(self.phase_receipts),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "provenance": dict(self.provenance),
        }

    @staticmethod
    def _cell_fields(cell: ManifestCell | None) -> dict[str, Any]:
        if cell is None:
            return {}
        return {
            "manifest_cell_id": cell.cell_id,
            "task_id": cell.task_id,
            "condition_id": cell.condition_id,
            "episode": cell.episode,
            "run_id": cell.run_id,
        }

    @classmethod
    def dry_run_only(
        cls,
        *,
        cell: ManifestCell | None = None,
        reason: str = "dry_run",
        fixture_label: str | None = None,
    ) -> ExecutionOutcome:
        return cls(
            status=TerminalStatus.DRY_RUN_ONLY,
            output=None,
            scientific_completion=False,
            dry_run=True,
            quality_admitted=False,
            decision=None,
            reason_codes=(reason,),
            error=None,
            phase_receipts={"fixture_label": fixture_label} if fixture_label else {},
            ended_at=utc_now_iso(),
            **cls._cell_fields(cell),
        )

    @classmethod
    def not_run(
        cls,
        *,
        cell: ManifestCell | None = None,
        reason: str,
        blocked_by_manifest_cell_id: str | None = None,
    ) -> ExecutionOutcome:
        return cls(
            status=TerminalStatus.NOT_RUN,
            output=None,
            scientific_completion=False,
            dry_run=False,
            quality_admitted=False,
            decision=None,
            reason_codes=(reason,),
            error=reason,
            blocked_by_manifest_cell_id=blocked_by_manifest_cell_id,
            ended_at=utc_now_iso(),
            **cls._cell_fields(cell),
        )

    @classmethod
    def completed_valid(
        cls,
        *,
        cell: ManifestCell | None = None,
        output: str,
        decision: str = "accept",
        candidate_id: str | None = None,
        inference: dict[str, Any] | None = None,
        reason_codes: tuple[str, ...] = (),
    ) -> ExecutionOutcome:
        return cls(
            status=TerminalStatus.COMPLETED_VALID,
            output=output,
            scientific_completion=True,
            dry_run=False,
            quality_admitted=True,
            decision=decision,
            reason_codes=reason_codes,
            candidate_id=candidate_id,
            inference=inference,
            ended_at=utc_now_iso(),
            **cls._cell_fields(cell),
        )

    @classmethod
    def completed_invalid(
        cls,
        *,
        cell: ManifestCell | None = None,
        output: str | None,
        decision: str | None = "reject",
        reason_codes: tuple[str, ...] = ("rejected",),
        error: str | None = None,
        candidate_id: str | None = None,
        inference: dict[str, Any] | None = None,
    ) -> ExecutionOutcome:
        return cls(
            status=TerminalStatus.COMPLETED_INVALID,
            output=output,
            scientific_completion=False,
            dry_run=False,
            quality_admitted=False,
            decision=decision,
            reason_codes=reason_codes,
            error=error,
            candidate_id=candidate_id,
            inference=inference,
            ended_at=utc_now_iso(),
            **cls._cell_fields(cell),
        )

    @classmethod
    def from_lifecycle(
        cls,
        *,
        cell: ManifestCell | None = None,
        status: TerminalStatus,
        output: str | None,
        decision: str | None = None,
        reason_codes: tuple[str, ...] = (),
        error: str | None = None,
        candidate_id: str | None = None,
        inference: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> ExecutionOutcome:
        """Build a terminal outcome with invariant-safe flags."""
        if status is TerminalStatus.DRY_RUN_ONLY:
            return cls.dry_run_only(cell=cell, reason=(reason_codes[0] if reason_codes else "dry_run"))
        if status is TerminalStatus.COMPLETED_VALID:
            if output is None:
                raise ValueError("COMPLETED_VALID requires observed output string")
            return cls.completed_valid(
                cell=cell,
                output=output,
                decision=decision or "accept",
                candidate_id=candidate_id,
                inference=inference,
                reason_codes=reason_codes,
            )
        sci = False
        quality = False
        if status in (
            TerminalStatus.TIMEOUT,
            TerminalStatus.TRANSPORT_ERROR,
            TerminalStatus.INVALID_RESPONSE,
            TerminalStatus.NO_FINAL_RESPONSE,
            TerminalStatus.NOT_RUN,
        ):
            output = None
        return cls(
            status=status,
            output=output,
            scientific_completion=sci,
            dry_run=dry_run,
            quality_admitted=quality,
            decision=decision,
            reason_codes=reason_codes,
            error=error,
            candidate_id=candidate_id,
            inference=inference,
            ended_at=utc_now_iso(),
            **cls._cell_fields(cell),
        )


def outcome_from_inference(
    result: InferenceResult,
    *,
    cell: ManifestCell | None = None,
    decision: str | None = None,
    reason_codes: tuple[str, ...] = (),
) -> ExecutionOutcome:
    """Project an InferenceResult into a terminal or provisional outcome.

    Operational failures (timeout/transport/invalid/no-final) are terminal
    with output=None. COMPLETED is provisional: status becomes COMPLETED_INVALID
    until a caller finalizes COMPLETED_VALID after accept. Empty string is
    preserved as observed output; None is never coerced to "".
    """
    terminal = classify_inference(result.status)
    inf_dict = result.to_dict()
    if terminal is not None:
        # Operational failure — terminal now.
        return ExecutionOutcome(
            status=terminal,
            output=None,
            scientific_completion=False,
            dry_run=False,
            quality_admitted=False,
            decision=decision,
            reason_codes=reason_codes or (terminal.value,),
            error=result.error,
            inference=inf_dict,
            ended_at=utc_now_iso(),
            **ExecutionOutcome._cell_fields(cell),
        )
    # COMPLETED: observed answer (possibly empty string). Not yet scientifically complete.
    return ExecutionOutcome(
        status=TerminalStatus.COMPLETED_INVALID,  # provisional until accept finalizes
        output=result.output,  # may be "" — never None coerced
        scientific_completion=False,
        dry_run=False,
        quality_admitted=bool(result.observed),
        decision=decision,
        reason_codes=reason_codes or ("inference_completed",),
        error=result.error,
        inference=inf_dict,
        ended_at=utc_now_iso(),
        **ExecutionOutcome._cell_fields(cell),
    )


def finalize_accepted(
    provisional: ExecutionOutcome,
    *,
    output: str,
    decision: str = "accept",
    candidate_id: str | None = None,
    cell: ManifestCell | None = None,
) -> ExecutionOutcome:
    """Promote a provisional completed inference to COMPLETED_VALID after accept."""
    if provisional.dry_run or provisional.status is TerminalStatus.DRY_RUN_ONLY:
        raise ValueError("cannot finalize a dry run as COMPLETED_VALID")
    if provisional.status in _INFERENCE_TERMINAL.values() or provisional.status in (
        TerminalStatus.TIMEOUT,
        TerminalStatus.TRANSPORT_ERROR,
        TerminalStatus.INVALID_RESPONSE,
        TerminalStatus.NO_FINAL_RESPONSE,
        TerminalStatus.NOT_RUN,
        TerminalStatus.PARSE_FAILED,
        TerminalStatus.SCHEMA_FAILED,
        TerminalStatus.SEMANTIC_FAILED,
    ):
        raise ValueError(f"cannot finalize terminal failure {provisional.status.value}")
    return ExecutionOutcome.completed_valid(
        cell=cell
        or (
            ManifestCell(
                run_id=provisional.run_id or "local",
                task_id=provisional.task_id or "local",
                condition_id=provisional.condition_id or "product",
                episode=provisional.episode,
            )
            if provisional.manifest_cell_id
            else None
        ),
        output=output,
        decision=decision,
        candidate_id=candidate_id,
        inference=provisional.inference,
    )


def classify_product_decision(
    *,
    decision: str,
    candidate: Mapping[str, Any] | None,
    receipt: Mapping[str, Any] | None,
    raw_output: str | None,
    dry_run: bool = False,
    cell: ManifestCell | None = None,
    inference: InferenceResult | None = None,
) -> ExecutionOutcome:
    """Map product return-path decision into a terminal ExecutionOutcome."""
    if dry_run:
        return ExecutionOutcome.dry_run_only(cell=cell, reason="dry_candidate_text")

    if inference is not None:
        terminal = classify_inference(inference.status)
        if terminal is not None:
            return outcome_from_inference(inference, cell=cell, decision="error")

    cand = candidate or {}
    rec = receipt or {}
    violations = list(rec.get("violations") or [])

    if decision == "accept":
        return ExecutionOutcome.completed_valid(
            cell=cell,
            output=raw_output if raw_output is not None else str(cand.get("answer") or ""),
            decision="accept",
            candidate_id=cand.get("candidate_id"),
            inference=inference.to_dict() if inference is not None else None,
        )

    out = raw_output if raw_output is not None else cand.get("raw_text")
    cand_id = cand.get("candidate_id")
    inf_dict = inference.to_dict() if inference is not None else None

    # Prefer specific lifecycle failures.
    if not cand.get("parse_ok", True) or cand.get("parse_error"):
        return ExecutionOutcome.from_lifecycle(
            cell=cell,
            status=TerminalStatus.PARSE_FAILED,
            output=out if isinstance(out, str) or out is None else str(out),
            decision="reject",
            reason_codes=("parse_failed", str(cand.get("parse_error") or "parse_error")),
            error=str(cand.get("parse_error") or "parse_failed"),
            candidate_id=cand_id,
            inference=inf_dict,
        )

    if violations:
        # Preserve exact original violation strings in diagnostics.
        exact_violations = tuple(str(v) for v in violations)
        try:
            status = classify_violations(exact_violations)
        except ViolationClassificationError as e:
            # Fail closed: unknown category is not guessed into schema/semantic.
            return ExecutionOutcome.completed_invalid(
                cell=cell,
                output=out if isinstance(out, str) or out is None else str(out),
                decision="reject",
                reason_codes=(
                    e.reason_code,
                    *exact_violations[:8],
                ),
                error=e.reason_code,
                candidate_id=cand_id,
                inference=inf_dict,
            )
        return ExecutionOutcome.from_lifecycle(
            cell=cell,
            status=status,
            output=out if isinstance(out, str) or out is None else str(out),
            decision="reject",
            reason_codes=(status.value, *exact_violations[:8]),
            error=status.value,
            candidate_id=cand_id,
            inference=inf_dict,
        )

    return ExecutionOutcome.completed_invalid(
        cell=cell,
        output=out if isinstance(out, str) or out is None else str(out),
        decision=decision or "reject",
        reason_codes=("completed_invalid",),
        error=decision,
        candidate_id=cand_id,
        inference=inf_dict,
    )


class TerminalLedger:
    """Manifest-derived ledger: exactly one terminal row per planned cell."""

    def __init__(self, cells: Sequence[ManifestCell], *, run_id: str | None = None) -> None:
        if not cells:
            raise EmptyManifestError()
        self._planned: dict[str, ManifestCell] = {}
        for c in cells:
            if c.cell_id in self._planned:
                raise TerminalLedgerError(f"duplicate planned cell in manifest: {c.cell_id}")
            self._planned[c.cell_id] = c
        self.run_id = run_id or cells[0].run_id
        self._rows: dict[str, ExecutionOutcome] = {}

    @property
    def planned_cell_ids(self) -> tuple[str, ...]:
        return tuple(self._planned.keys())

    def record(self, cell_id: str, outcome: ExecutionOutcome) -> None:
        if cell_id not in self._planned:
            raise TerminalLedgerError(
                f"UNPLANNED_CELL: cell not in planned manifest: {cell_id}"
            )
        if cell_id in self._rows:
            raise TerminalLedgerError(
                f"DUPLICATE_TERMINALIZATION: duplicate terminal record for cell: {cell_id}"
            )
        # Bind cell identity if missing
        if outcome.manifest_cell_id is None:
            cell = self._planned[cell_id]
            outcome = ExecutionOutcome(
                status=outcome.status,
                output=outcome.output,
                scientific_completion=outcome.scientific_completion,
                dry_run=outcome.dry_run,
                quality_admitted=outcome.quality_admitted,
                decision=outcome.decision,
                reason_codes=outcome.reason_codes,
                error=outcome.error,
                manifest_cell_id=cell_id,
                task_id=cell.task_id,
                condition_id=cell.condition_id,
                episode=cell.episode,
                run_id=cell.run_id,
                candidate_id=outcome.candidate_id,
                blocked_by_manifest_cell_id=outcome.blocked_by_manifest_cell_id,
                inference=outcome.inference,
                phase_receipts=outcome.phase_receipts,
                started_at=outcome.started_at,
                ended_at=outcome.ended_at or utc_now_iso(),
                provenance=outcome.provenance,
            )
        elif outcome.manifest_cell_id != cell_id:
            raise TerminalLedgerError(
                f"outcome cell_id {outcome.manifest_cell_id!r} != record key {cell_id!r}"
            )
        self._rows[cell_id] = outcome

    def missing_cell_ids(self) -> list[str]:
        return [cid for cid in self._planned if cid not in self._rows]

    def validate(self) -> bool:
        missing = self.missing_cell_ids()
        if missing:
            raise TerminalLedgerError(
                f"missing terminal records for {len(missing)} cell(s): {missing[:5]}"
            )
        if len(self._rows) != len(self._planned):
            raise TerminalLedgerError(
                f"row count {len(self._rows)} != planned {len(self._planned)}"
            )
        return True

    def rows(self) -> list[ExecutionOutcome]:
        return [self._rows[cid] for cid in self._planned if cid in self._rows]

    def terminal_count(self) -> int:
        return len(self._rows)

    def planned_count(self) -> int:
        return len(self._planned)

    def count_status(self, status: TerminalStatus) -> int:
        return sum(1 for r in self._rows.values() if r.status is status)

    def scientific_completion_count(self) -> int:
        return sum(1 for r in self._rows.values() if is_scientific_completion(r))

    def diagnostic_counts(self) -> dict[str, Any]:
        """Ledger-derived factual counts only.

        Shared infrastructure: no experiment headline policy, no Episode-A
        language, no scientific_status / headline_eligible fields. Callers
        (run_continuity, run_matrix) attach their own policy after reading
        these facts.
        """
        rows = list(self._rows.values())
        inference_completed_n = 0
        final_response_present_n = 0
        candidate_valid_n = 0
        accepted_n = 0
        dry_run_n = 0
        failed_n = 0
        for r in rows:
            if r.dry_run or r.status is TerminalStatus.DRY_RUN_ONLY:
                dry_run_n += 1
                continue

            inf_completed = bool(
                r.quality_admitted
                or r.status is TerminalStatus.COMPLETED_VALID
                or (
                    r.inference is not None
                    and r.inference.get("status") == RunStatus.COMPLETED.value
                )
            )
            if inf_completed:
                inference_completed_n += 1
            if r.output is not None:
                final_response_present_n += 1
            if r.status is TerminalStatus.COMPLETED_VALID:
                accepted_n += 1
                candidate_valid_n += 1
            elif r.phase_receipts.get("candidate_valid") is True:
                candidate_valid_n += 1

            # Failures: operational / lifecycle rejects without an admitted answer.
            if r.status is TerminalStatus.COMPLETED_VALID:
                pass
            elif inf_completed and r.quality_admitted:
                # Diagnostic observation (e.g. Episode B text) — not a failure.
                pass
            else:
                failed_n += 1

        return {
            "planned_n": self.planned_count(),
            "terminal_n": self.terminal_count(),
            "inference_completed_n": inference_completed_n,
            "final_response_present_n": final_response_present_n,
            "candidate_valid_n": candidate_valid_n,
            "accepted_n": accepted_n,
            "scientific_completion_n": self.scientific_completion_count(),
            "dry_run_n": dry_run_n,
            "failed_n": failed_n,
        }

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        counts = self.diagnostic_counts()
        return {
            "run_id": self.run_id,
            "planned_n": counts["planned_n"],
            "terminal_n": counts["terminal_n"],
            "scientific_completion_n": counts["scientific_completion_n"],
            "status_counts": {
                s.value: self.count_status(s) for s in TerminalStatus if self.count_status(s)
            },
            "diagnostic_counts": counts,
            "rows": [r.to_dict() for r in self.rows()],
        }


def build_manifest(
    *,
    run_id: str | None = None,
    task_ids: Iterable[str],
    condition_ids: Iterable[str],
    episodes: Sequence[str | None] | None = None,
    replicate_ids: Sequence[str] = ("0",),
    allow_empty: bool = False,
) -> list[ManifestCell]:
    """Cartesian planned cells for a matrix/continuity-style experiment.

    Raises EmptyManifestError when the product is zero cells, unless
    allow_empty=True (test-only). An empty planned manifest is not a valid
    completed scientific run.
    """
    rid = run_id or make_id("run")
    tasks = [str(t) for t in task_ids]
    conds = [str(c) for c in condition_ids]
    eps: Sequence[str | None] = list(episodes) if episodes is not None else [None]
    reps = [str(r) for r in replicate_ids]
    cells: list[ManifestCell] = []
    for task_id in tasks:
        for condition_id in conds:
            for episode in eps:
                for rep in reps:
                    cells.append(
                        ManifestCell(
                            run_id=rid,
                            task_id=task_id,
                            condition_id=condition_id,
                            episode=episode,
                            replicate_id=rep,
                        )
                    )
    if not cells and not allow_empty:
        raise EmptyManifestError(
            "EMPTY_MANIFEST: planned manifest has zero cells "
            f"(tasks={len(tasks)}, conditions={len(conds)}, "
            f"episodes={len(eps)}, replicates={len(reps)})"
        )
    return cells


def require_nonempty_manifest(cells: Sequence[ManifestCell]) -> list[ManifestCell]:
    """Fail closed before execution if no cells are planned."""
    if not cells:
        raise EmptyManifestError()
    return list(cells)
