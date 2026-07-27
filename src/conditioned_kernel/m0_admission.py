"""RUN 00.6F — M0 admission accounting (separate from TerminalLedger facts).

Consumes frozen manifest + terminal_cell records only.
Never decides by re-running models. Never imputes missing scores.
scientific_completion remains false for unratified candidate manifests.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from conditioned_kernel.control_contract import ConditionId
from conditioned_kernel.m0_ledger_integration import M0TerminalClassification
from conditioned_kernel.m0_manifest import ADMISSION_SCHEMA_VERSION, MANIFEST_ID
from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex


def _count_class(
    terminals: Sequence[Mapping[str, Any]], classification: str
) -> int:
    return sum(
        1
        for t in terminals
        if str(t.get("terminal_classification")) == classification
    )


def evaluate_admission(
    *,
    manifest: Mapping[str, Any],
    terminal_cells: Sequence[Mapping[str, Any]],
    authorization_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic admission report for a manifest + terminal set."""
    planned = list(manifest.get("planned_cells") or [])
    planned_ids = {str(c["cell_id"]) for c in planned}
    planned_n = len(planned)

    terminals = list(terminal_cells)
    terminal_ids = [str(t["cell_id"]) for t in terminals]
    terminal_id_set = set(terminal_ids)

    # Duplicates in the provided terminal list
    dup_n = len(terminal_ids) - len(terminal_id_set)
    unplanned_n = sum(1 for cid in terminal_id_set if cid not in planned_ids)
    missing_n = sum(1 for cid in planned_ids if cid not in terminal_id_set)

    # Prefer unique planned terminals for coverage (if dups present, still count unique)
    unique_planned_terminals = [
        t for t in terminals if str(t["cell_id"]) in planned_ids
    ]
    # de-dupe by cell_id keeping first
    seen: set[str] = set()
    unique_rows: list[Mapping[str, Any]] = []
    for t in unique_planned_terminals:
        cid = str(t["cell_id"])
        if cid in seen:
            continue
        seen.add(cid)
        unique_rows.append(t)

    terminal_cells_n = len(unique_rows)
    terminalization_coverage = (
        (terminal_cells_n / planned_n) if planned_n > 0 else 0.0
    )

    scored = [
        t
        for t in unique_rows
        if str(t.get("terminal_classification"))
        == M0TerminalClassification.SCORED.value
        and t.get("primary_score") is not None
    ]
    scored_cells_n = len(scored)
    observed_score_coverage = (scored_cells_n / planned_n) if planned_n > 0 else 0.0

    primary_pairs = list(manifest.get("planned_primary_pairs") or [])
    planned_primary_pairs_n = len(primary_pairs)
    by_id = {str(t["cell_id"]): t for t in unique_rows}

    valid_pairs: list[dict[str, Any]] = []
    invalid_pair_reasons: list[dict[str, Any]] = []
    for pair in primary_pairs:
        c1_id = str(pair["c1_cell_id"])
        c3_id = str(pair["c3_cell_id"])
        reasons: list[str] = []
        c1 = by_id.get(c1_id)
        c3 = by_id.get(c3_id)
        if c1 is None:
            reasons.append("MISSING_C1_TERMINAL")
        if c3 is None:
            reasons.append("MISSING_C3_TERMINAL")
        if c1 is not None and c3 is not None:
            if str(c1.get("terminal_classification")) != M0TerminalClassification.SCORED.value:
                reasons.append(f"C1_NOT_SCORED:{c1.get('terminal_classification')}")
            if str(c3.get("terminal_classification")) != M0TerminalClassification.SCORED.value:
                reasons.append(f"C3_NOT_SCORED:{c3.get('terminal_classification')}")
            if str(c1.get("control_verification_status")) not in ("pass", "PASS"):
                reasons.append("C1_CONTROL_FAILED")
            if str(c3.get("control_verification_status")) not in ("pass", "PASS"):
                reasons.append("C3_CONTROL_FAILED")
            if str(c1.get("packet_verification_status")) not in ("pass", "PASS"):
                reasons.append("C1_PACKET_FAILED")
            if str(c3.get("packet_verification_status")) not in ("pass", "PASS"):
                reasons.append("C3_PACKET_FAILED")
            if not c1.get("provenance_completeness"):
                reasons.append("C1_PROVENANCE_INCOMPLETE")
            if not c3.get("provenance_completeness"):
                reasons.append("C3_PROVENANCE_INCOMPLETE")
            if c1.get("primary_score") is None:
                reasons.append("C1_NULL_SCORE")
            if c3.get("primary_score") is None:
                reasons.append("C3_NULL_SCORE")
            # Frozen model / params
            if str(c1.get("model_tag")) != str(manifest.get("model_tag")):
                reasons.append("C1_MODEL_MISMATCH")
            if str(c3.get("model_tag")) != str(manifest.get("model_tag")):
                reasons.append("C3_MODEL_MISMATCH")
            if c1.get("generation_parameters") != manifest.get("generation_parameters"):
                reasons.append("C1_GENERATION_PARAM_MISMATCH")
            if c3.get("generation_parameters") != manifest.get("generation_parameters"):
                reasons.append("C3_GENERATION_PARAM_MISMATCH")
            for label, row in (("C1", c1), ("C3", c3)):
                if str(row.get("terminal_classification")) == (
                    M0TerminalClassification.TASK_CONTRACT_ERROR.value
                ):
                    reasons.append(f"{label}_TASK_CONTRACT_ERROR")
                if str(row.get("terminal_classification")) == (
                    M0TerminalClassification.SCORER_INTERNAL_ERROR.value
                ):
                    reasons.append(f"{label}_SCORER_INTERNAL_ERROR")
        if reasons:
            invalid_pair_reasons.append(
                {
                    "task_id": pair.get("task_id"),
                    "c1_cell_id": c1_id,
                    "c3_cell_id": c3_id,
                    "reasons": reasons,
                }
            )
        else:
            valid_pairs.append(
                {
                    "task_id": pair.get("task_id"),
                    "c1_cell_id": c1_id,
                    "c3_cell_id": c3_id,
                    "c1_score": c1.get("primary_score") if c1 else None,
                    "c3_score": c3.get("primary_score") if c3 else None,
                }
            )

    valid_primary_pairs_n = len(valid_pairs)
    primary_pair_coverage = (
        (valid_primary_pairs_n / planned_primary_pairs_n)
        if planned_primary_pairs_n > 0
        else 0.0
    )

    failure_counts = {
        cls.value: _count_class(unique_rows, cls.value)
        for cls in M0TerminalClassification
    }
    control_contract_failures = failure_counts[
        M0TerminalClassification.CONTROL_CONTRACT_FAILED.value
    ]
    task_contract_failures = failure_counts[
        M0TerminalClassification.TASK_CONTRACT_ERROR.value
    ]
    provenance_failures = failure_counts[
        M0TerminalClassification.PROVENANCE_INCOMPLETE.value
    ] + sum(1 for t in unique_rows if not t.get("provenance_completeness"))

    # Authorization
    auth_status = str(manifest.get("authorization_status") or "unratified")
    auth_ok = False
    auth_reasons: list[str] = []
    if authorization_receipt is None:
        auth_reasons.append("MISSING_AUTHORIZATION_RECEIPT")
    else:
        if str(authorization_receipt.get("manifest_id")) != str(
            manifest.get("manifest_id")
        ):
            auth_reasons.append("AUTHORIZATION_MANIFEST_ID_MISMATCH")
        if str(authorization_receipt.get("manifest_sha256")) != str(
            manifest.get("manifest_sha256")
        ):
            auth_reasons.append("AUTHORIZATION_MANIFEST_HASH_MISMATCH")
        required = [
            "manifest_id",
            "manifest_sha256",
            "authorizing_principal",
            "authorization_timestamp",
            "experiment_contract_id",
            "authorized_model",
            "authorized_planned_cell_count",
        ]
        for f in required:
            if not authorization_receipt.get(f):
                auth_reasons.append(f"AUTHORIZATION_MISSING_FIELD:{f}")
        if not auth_reasons:
            auth_ok = True
            auth_status = "ratified_receipt_present"

    # Ledger integrity
    ledger_ok = (
        missing_n == 0
        and dup_n == 0
        and unplanned_n == 0
        and terminalization_coverage == 1.0
    )
    manifest_ok = bool(manifest.get("manifest_sha256")) and bool(
        manifest.get("manifest_id")
    )

    headline_reasons: list[str] = []
    if not auth_ok:
        headline_reasons.extend(auth_reasons or ["MANIFEST_UNRATIFIED"])
    if terminalization_coverage != 1.0:
        headline_reasons.append("TERMINALIZATION_COVERAGE_INCOMPLETE")
    if primary_pair_coverage != 1.0:
        headline_reasons.append("PRIMARY_PAIR_COVERAGE_INCOMPLETE")
    if not ledger_ok:
        headline_reasons.append("LEDGER_INTEGRITY_FAILED")
    if not manifest_ok:
        headline_reasons.append("MANIFEST_INTEGRITY_FAILED")
    if dup_n > 0:
        headline_reasons.append("DUPLICATE_TERMINAL_RECORDS")
    if unplanned_n > 0:
        headline_reasons.append("UNPLANNED_TERMINAL_RECORDS")
    if task_contract_failures > 0:
        # only block if in primary cells — conservative: any planned task-contract
        headline_reasons.append("TASK_CONTRACT_ERROR_PRESENT")
    if failure_counts[M0TerminalClassification.SCORER_INTERNAL_ERROR.value] > 0:
        headline_reasons.append("SCORER_INTERNAL_ERROR_PRESENT")
    # Control / provenance already reflected in pair validity
    if any(
        r
        for p in invalid_pair_reasons
        for r in p["reasons"]
        if "CONTROL" in r or "PROVENANCE" in r or "NOT_SCORED" in r or "MISSING" in r
    ):
        if "PRIMARY_PAIR_COVERAGE_INCOMPLETE" not in headline_reasons:
            headline_reasons.append("PRIMARY_PAIR_INVALID")

    # Deduplicate reasons preserving order
    seen_r: set[str] = set()
    headline_ineligible_reasons = []
    for r in headline_reasons:
        if r not in seen_r:
            seen_r.add(r)
            headline_ineligible_reasons.append(r)

    # Structural readiness for a future primary contrast summary.
    primary_headline_structurally_ready = len(headline_ineligible_reasons) == 0
    primary_headline = None
    partial_descriptive: dict[str, Any] | None = None
    if primary_headline_structurally_ready and valid_pairs:
        primary_headline = {
            "contrast": "C3_vs_C1",
            "pairs": valid_pairs,
            "note": (
                "structurally ready only; report headline_eligible remains false "
                "while scientific_completion is false (RUN 00.6F.1 invariant)"
            ),
        }
    elif valid_pairs or invalid_pair_reasons:
        partial_descriptive = {
            "valid_pairs": valid_pairs,
            "invalid_pairs": invalid_pair_reasons,
            "note": "descriptive only; not a complete-case primary headline",
        }

    # Report-policy invariant:
    #   headline_eligible == true  ⇒  scientific_completion == true
    # A report may be scientifically complete but headline-ineligible.
    # During unratified M0 candidate era both remain false.
    scientific_completion = False
    headline_eligible = False
    if headline_eligible and not scientific_completion:
        raise ValueError(
            "REPORT_POLICY_VIOLATION: headline_eligible requires scientific_completion"
        )
    # primary_headline_eligible tracks structural gate only; never implies
    # report-level headline_eligible while scientifically incomplete.
    primary_headline_eligible = (
        primary_headline_structurally_ready and scientific_completion
    )
    if primary_headline_structurally_ready and not scientific_completion:
        if "SCIENTIFIC_COMPLETION_REQUIRED_FOR_HEADLINE" not in headline_ineligible_reasons:
            headline_ineligible_reasons.append(
                "SCIENTIFIC_COMPLETION_REQUIRED_FOR_HEADLINE"
            )

    report = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "manifest_id": manifest.get("manifest_id", MANIFEST_ID),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "authorization_status": auth_status,
        "planned_cells_n": planned_n,
        "terminal_cells_n": terminal_cells_n,
        "terminalization_coverage": terminalization_coverage,
        "scored_cells_n": scored_cells_n,
        "observed_score_coverage": observed_score_coverage,
        "planned_primary_pairs_n": planned_primary_pairs_n,
        "valid_primary_pairs_n": valid_primary_pairs_n,
        "primary_pair_coverage": primary_pair_coverage,
        "failure_counts_by_classification": failure_counts,
        "control_contract_failures": control_contract_failures,
        "task_contract_failures": task_contract_failures,
        "provenance_failures": provenance_failures,
        "duplicate_terminal_record_n": dup_n,
        "unplanned_terminal_record_n": unplanned_n,
        "missing_terminal_record_n": missing_n,
        "ledger_integrity_ok": ledger_ok,
        "manifest_integrity_ok": manifest_ok,
        "primary_headline_eligible": primary_headline_eligible,
        "primary_headline_structurally_ready": primary_headline_structurally_ready,
        "headline_ineligible_reasons": headline_ineligible_reasons,
        "primary_headline": primary_headline,
        "partial_descriptive_summaries": partial_descriptive,
        "invalid_primary_pair_reasons": invalid_pair_reasons,
        "scientific_completion": scientific_completion,
        "headline_eligible": headline_eligible,
        "conditions": {
            ConditionId.C0_BARE.value: _count_class_condition(
                unique_rows, ConditionId.C0_BARE.value
            ),
            ConditionId.C1_BUDGET_MATCHED_BARE.value: _count_class_condition(
                unique_rows, ConditionId.C1_BUDGET_MATCHED_BARE.value
            ),
            ConditionId.C2_INSTRUCTION_IDENTICAL.value: _count_class_condition(
                unique_rows, ConditionId.C2_INSTRUCTION_IDENTICAL.value
            ),
            ConditionId.C3_STATIC_CK.value: _count_class_condition(
                unique_rows, ConditionId.C3_STATIC_CK.value
            ),
        },
    }
    report["admission_report_sha256"] = sha256_hex(canonical_json_bytes(report))
    return report


def _count_class_condition(rows: Sequence[Mapping[str, Any]], condition_id: str) -> int:
    return sum(1 for t in rows if str(t.get("condition_id")) == condition_id)


def verify_manifest_hash(manifest: Mapping[str, Any]) -> bool:
    """Recompute manifest SHA-256 without the embedded hash field."""
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return sha256_hex(canonical_json_bytes(body)) == str(manifest.get("manifest_sha256"))
