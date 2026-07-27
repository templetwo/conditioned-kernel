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


def recompute_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Independently recompute canonical manifest SHA-256 (embedded field excluded)."""
    body = {k: v for k, v in dict(manifest).items() if k != "manifest_sha256"}
    return sha256_hex(canonical_json_bytes(body))


def verify_manifest_integrity(
    manifest: Mapping[str, Any],
) -> tuple[bool, str | None, str | None, list[str]]:
    """Return (ok, claimed_hash, computed_hash, reasons)."""
    reasons: list[str] = []
    claimed = manifest.get("manifest_sha256")
    claimed_s = str(claimed) if claimed is not None else None
    try:
        computed = recompute_manifest_sha256(manifest)
    except Exception as e:  # noqa: BLE001
        return False, claimed_s, None, ["MANIFEST_CANONICALIZATION_FAILED", type(e).__name__]
    if not claimed_s:
        reasons.append("MANIFEST_INTEGRITY_UNVERIFIED")
        return False, claimed_s, computed, reasons
    if claimed_s != computed:
        reasons.append("MANIFEST_HASH_MISMATCH")
        return False, claimed_s, computed, reasons
    return True, claimed_s, computed, []


def verify_authorization_receipt(
    *,
    manifest: Mapping[str, Any],
    authorization_receipt: Mapping[str, Any] | None,
    computed_manifest_sha256: str | None,
) -> tuple[bool, str, list[str]]:
    """Bind receipt to exact manifest identity, model, count, conditions."""
    auth_status = str(manifest.get("authorization_status") or "unratified")
    reasons: list[str] = []
    if authorization_receipt is None:
        return False, auth_status, ["MISSING_AUTHORIZATION_RECEIPT"]

    required = [
        "manifest_id",
        "manifest_sha256",
        "authorizing_principal",
        "authorization_timestamp",
        "experiment_contract_id",
        "authorized_model",
        "authorized_planned_cell_count",
        "authorized_condition_set",
        "resolved_model_digest",
    ]
    for f in required:
        if authorization_receipt.get(f) in (None, "", [], {}):
            reasons.append(f"AUTHORIZATION_MISSING_FIELD:{f}")

    if str(authorization_receipt.get("manifest_id")) != str(manifest.get("manifest_id")):
        reasons.append("AUTHORIZATION_MANIFEST_ID_MISMATCH")

    claimed_hash = str(authorization_receipt.get("manifest_sha256") or "")
    if computed_manifest_sha256 and claimed_hash != computed_manifest_sha256:
        reasons.append("AUTHORIZATION_MANIFEST_HASH_MISMATCH")
    if claimed_hash != str(manifest.get("manifest_sha256") or ""):
        reasons.append("AUTHORIZATION_MANIFEST_HASH_MISMATCH")

    if str(authorization_receipt.get("authorized_model")) != str(
        manifest.get("model_tag")
    ):
        reasons.append("AUTHORIZATION_MODEL_MISMATCH")

    try:
        auth_count = int(authorization_receipt.get("authorized_planned_cell_count"))
        if auth_count != int(manifest.get("planned_cell_count") or -1):
            reasons.append("AUTHORIZATION_CELL_COUNT_MISMATCH")
    except (TypeError, ValueError):
        reasons.append("AUTHORIZATION_CELL_COUNT_MISMATCH")

    auth_conds = authorization_receipt.get("authorized_condition_set")
    man_conds = list(manifest.get("condition_set") or [])
    if not isinstance(auth_conds, list) or sorted(str(x) for x in auth_conds) != sorted(
        str(x) for x in man_conds
    ):
        reasons.append("AUTHORIZATION_CONDITION_SET_MISMATCH")

    # Dedupe
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    if out:
        return False, auth_status, out
    return True, "ratified_receipt_present", []


def evaluate_admission(
    *,
    manifest: Mapping[str, Any],
    terminal_cells: Sequence[Mapping[str, Any]],
    authorization_receipt: Mapping[str, Any] | None = None,
    persistent_ledger_ok: bool | None = None,
) -> dict[str, Any]:
    """Deterministic admission report for a manifest + terminal set.

    Independently recomputes and verifies canonical manifest SHA-256 (00.8A).
    Never treats truthiness of an embedded hash as integrity.
    """
    # --- FIX 1: independent manifest integrity ---
    manifest_ok, claimed_hash, computed_hash, manifest_reasons = verify_manifest_integrity(
        manifest
    )

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

    # Authorization — never echo ratified when integrity failed
    auth_ok, auth_status, auth_reasons = verify_authorization_receipt(
        manifest=manifest,
        authorization_receipt=authorization_receipt,
        computed_manifest_sha256=computed_hash,
    )
    if not manifest_ok:
        auth_ok = False
        if auth_status == "ratified_receipt_present":
            auth_status = str(manifest.get("authorization_status") or "unratified")
        for r in manifest_reasons:
            if r not in auth_reasons:
                auth_reasons.append(r)

    # Ledger integrity
    ledger_ok = (
        missing_n == 0
        and dup_n == 0
        and unplanned_n == 0
        and terminalization_coverage == 1.0
    )
    if persistent_ledger_ok is False:
        ledger_ok = False

    # Per-condition classification counts (descriptive commissioning only)
    per_condition_class_counts: dict[str, dict[str, int]] = {}
    for cond in (
        ConditionId.C0_BARE.value,
        ConditionId.C1_BUDGET_MATCHED_BARE.value,
        ConditionId.C2_INSTRUCTION_IDENTICAL.value,
        ConditionId.C3_STATIC_CK.value,
    ):
        per_condition_class_counts[cond] = {
            cls.value: sum(
                1
                for t in unique_rows
                if str(t.get("condition_id")) == cond
                and str(t.get("terminal_classification")) == cls.value
            )
            for cls in M0TerminalClassification
        }

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
        headline_reasons.extend(manifest_reasons or ["MANIFEST_INTEGRITY_FAILED"])
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
        "manifest_hash_claimed": claimed_hash,
        "manifest_hash_computed": computed_hash,
        "manifest_integrity_reasons": manifest_reasons,
        "authorization_reasons": auth_reasons,
        "per_condition_classification_counts": per_condition_class_counts,
        "execution_scope": "commissioning_validation",
        "scientific_status": "commissioning_safety_only",
        "m0_authorized": False,
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
    ok, _, _, _ = verify_manifest_integrity(manifest)
    return ok
