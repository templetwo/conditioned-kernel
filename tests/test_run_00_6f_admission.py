"""RUN 00.6F — admission accounting and headline gates (offline)."""

from __future__ import annotations

import copy

import pytest

from conditioned_kernel.control_contract import ConditionId
from conditioned_kernel.m0_admission import evaluate_admission, verify_manifest_hash
from conditioned_kernel.m0_ledger_integration import (
    M0LedgerSession,
    M0TerminalClassification,
    terminalize_synthetic,
)
from conditioned_kernel.m0_manifest import build_candidate_manifest
from conditioned_kernel.relational_scorer import score_cell


@pytest.fixture(scope="module")
def manifest():
    return build_candidate_manifest()


def _score(manifest, pc):
    gold = manifest["included_tasks"][0]["gold"]
    return score_cell(
        task_id=gold["task_id"],
        condition_id=pc["condition_id"],
        gold=gold,
        proposed_assertions=gold["expected_relations"],
        inference_status="completed",
        repo_commit=manifest["repository_commit"],
    )


def _score_all(manifest) -> tuple[dict, list[dict]]:
    m = copy.deepcopy(manifest)
    s = M0LedgerSession(m)
    terms = []
    for pc in m["planned_cells"]:
        terms.append(
            terminalize_synthetic(
                s,
                cell_id=pc["cell_id"],
                classification=M0TerminalClassification.SCORED,
                score_record=_score(m, pc),
                inference_status="completed",
                control_verification_status="pass",
                packet_verification_status="pass",
                provenance_complete=True,
                model_digest="sha256:fixture",
            )
        )
    return m, terms


def _auth(manifest, **overrides):
    base = {
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "authorizing_principal": "anthony",
        "authorization_timestamp": "2026-07-28T00:00:00Z",
        "experiment_contract_id": "ck.exp.m0.v1",
        "authorized_model": manifest["model_tag"],
        "authorized_planned_cell_count": manifest["planned_cell_count"],
        "authorized_condition_set": list(manifest.get("condition_set") or []),
        "resolved_model_digest": "sha256:fixture-digest",
    }
    base.update(overrides)
    return base


def test_terminalization_coverage_full():
    m, terms = _score_all(build_candidate_manifest())
    rep = evaluate_admission(manifest=m, terminal_cells=terms)
    assert rep["planned_cells_n"] == m["planned_cell_count"]
    assert rep["terminal_cells_n"] == m["planned_cell_count"]
    assert rep["terminalization_coverage"] == 1.0


def test_observed_score_coverage():
    m, terms = _score_all(build_candidate_manifest())
    rep = evaluate_admission(manifest=m, terminal_cells=terms)
    assert rep["scored_cells_n"] == m["planned_cell_count"]
    assert rep["observed_score_coverage"] == 1.0


def test_primary_pair_coverage_full_with_auth_still_blocks_without_receipt_fields():
    m, terms = _score_all(build_candidate_manifest())
    rep = evaluate_admission(manifest=m, terminal_cells=terms, authorization_receipt=None)
    assert rep["primary_pair_coverage"] == 1.0
    assert rep["primary_headline_eligible"] is False
    assert "MISSING_AUTHORIZATION_RECEIPT" in rep["headline_ineligible_reasons"]


def test_full_auth_and_complete_pairs_structurally_eligible():
    m, terms = _score_all(build_candidate_manifest())
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    assert rep["primary_pair_coverage"] == 1.0
    assert rep["terminalization_coverage"] == 1.0
    # RUN 00.6F.1: structural readiness ≠ report headline eligibility
    assert rep.get("primary_headline_structurally_ready") is True
    assert rep["primary_headline_eligible"] is False
    assert "SCIENTIFIC_COMPLETION_REQUIRED_FOR_HEADLINE" in rep["headline_ineligible_reasons"]
    assert rep["scientific_completion"] is False
    assert rep["headline_eligible"] is False


def test_one_missing_primary_cell_blocks_headline():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    # skip C1
    for pc in m["planned_cells"]:
        if pc["condition_id"] == ConditionId.C1_BUDGET_MATCHED_BARE.value:
            continue
        terms.append(
            terminalize_synthetic(
                s,
                cell_id=pc["cell_id"],
                classification=M0TerminalClassification.SCORED,
                score_record=_score(m, pc),
            )
        )
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    assert rep["primary_pair_coverage"] < 1.0
    assert rep["primary_headline_eligible"] is False
    assert rep["primary_headline"] is None
    assert rep["partial_descriptive_summaries"] is not None


def test_timeout_in_primary_pair_blocks_headline():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    for pc in m["planned_cells"]:
        if pc["condition_id"] == ConditionId.C1_BUDGET_MATCHED_BARE.value:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.TIMEOUT,
                )
            )
        else:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.SCORED,
                    score_record=_score(m, pc),
                )
            )
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    assert rep["primary_pair_coverage"] == 0.0
    assert rep["primary_headline_eligible"] is False
    assert any(
        "C1_NOT_SCORED" in r
        for p in rep["invalid_primary_pair_reasons"]
        for r in p["reasons"]
    )


def test_control_failure_in_primary_pair_blocks():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    for pc in m["planned_cells"]:
        if pc["condition_id"] == ConditionId.C3_STATIC_CK.value:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.CONTROL_CONTRACT_FAILED,
                    control_verification_status="fail",
                )
            )
        else:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.SCORED,
                    score_record=_score(m, pc),
                    control_verification_status="pass",
                )
            )
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    assert rep["primary_headline_eligible"] is False
    assert rep["control_contract_failures"] >= 1


def test_incomplete_provenance_blocks():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    for pc in m["planned_cells"]:
        terms.append(
            terminalize_synthetic(
                s,
                cell_id=pc["cell_id"],
                classification=M0TerminalClassification.SCORED,
                score_record=_score(m, pc),
                provenance_complete=(
                    pc["condition_id"] != ConditionId.C1_BUDGET_MATCHED_BARE.value
                ),
            )
        )
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    assert rep["primary_headline_eligible"] is False


def test_duplicate_terminal_blocks_admission():
    m, terms = _score_all(build_candidate_manifest())
    # inject duplicate
    terms2 = terms + [copy.deepcopy(terms[0])]
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms2, authorization_receipt=_auth(m)
    )
    assert rep["duplicate_terminal_record_n"] == 1
    assert rep["primary_headline_eligible"] is False
    assert "DUPLICATE_TERMINAL_RECORDS" in rep["headline_ineligible_reasons"]


def test_unplanned_terminal_blocks_admission():
    m, terms = _score_all(build_candidate_manifest())
    forged = copy.deepcopy(terms[0])
    forged["cell_id"] = "f" * 64
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms + [forged], authorization_receipt=_auth(m)
    )
    assert rep["unplanned_terminal_record_n"] == 1
    assert rep["primary_headline_eligible"] is False


def test_missing_authorization_blocks():
    m, terms = _score_all(build_candidate_manifest())
    rep = evaluate_admission(manifest=m, terminal_cells=terms)
    assert rep["primary_headline_eligible"] is False
    assert "MISSING_AUTHORIZATION_RECEIPT" in rep["headline_ineligible_reasons"]


def test_wrong_manifest_authorization_hash_blocks():
    m, terms = _score_all(build_candidate_manifest())
    bad = _auth(m, manifest_sha256="0" * 64)
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=bad
    )
    assert rep["primary_headline_eligible"] is False
    assert "AUTHORIZATION_MANIFEST_HASH_MISMATCH" in rep["headline_ineligible_reasons"]


def test_partial_observations_descriptive_only():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    for pc in m["planned_cells"]:
        if pc["condition_id"] == ConditionId.C0_BARE.value:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.TIMEOUT,
                )
            )
        else:
            terms.append(
                terminalize_synthetic(
                    s,
                    cell_id=pc["cell_id"],
                    classification=M0TerminalClassification.SCORED,
                    score_record=_score(m, pc),
                )
            )
    rep = evaluate_admission(
        manifest=m, terminal_cells=terms, authorization_receipt=_auth(m)
    )
    # C0 timeout doesn't break C1/C3 pair if both scored — still need full terminalization
    # We did terminalize all 4; C0 is timeout but pair may still be valid
    assert rep["terminalization_coverage"] == 1.0
    assert rep["observed_score_coverage"] < 1.0
    # primary pair may still be valid; if so headline could be eligible
    # Ensure scientific_completion false either way
    assert rep["scientific_completion"] is False


def test_verify_manifest_hash():
    m = build_candidate_manifest()
    assert verify_manifest_hash(m)
    bad = copy.deepcopy(m)
    bad["manifest_sha256"] = "1" * 64
    assert not verify_manifest_hash(bad)


def test_failure_counts_and_no_disappearance():
    m = build_candidate_manifest()
    s = M0LedgerSession(copy.deepcopy(m))
    terms = []
    mapping = {
        ConditionId.C0_BARE.value: M0TerminalClassification.TIMEOUT,
        ConditionId.C1_BUDGET_MATCHED_BARE.value: M0TerminalClassification.TRANSPORT_ERROR,
        ConditionId.C2_INSTRUCTION_IDENTICAL.value: M0TerminalClassification.PACKET_CONTRACT_FAILED,
        ConditionId.C3_STATIC_CK.value: M0TerminalClassification.SCORER_INTERNAL_ERROR,
    }
    for pc in m["planned_cells"]:
        terms.append(
            terminalize_synthetic(
                s,
                cell_id=pc["cell_id"],
                classification=mapping[pc["condition_id"]],
                packet_verification_status=(
                    "fail"
                    if mapping[pc["condition_id"]]
                    is M0TerminalClassification.PACKET_CONTRACT_FAILED
                    else "pass"
                ),
            )
        )
    rep = evaluate_admission(manifest=m, terminal_cells=terms)
    assert rep["terminalization_coverage"] == 1.0
    assert rep["failure_counts_by_classification"]["TIMEOUT"] == 1
    assert rep["failure_counts_by_classification"]["TRANSPORT_ERROR"] == 1
    assert rep["failure_counts_by_classification"]["PACKET_CONTRACT_FAILED"] == 1
    assert rep["failure_counts_by_classification"]["SCORER_INTERNAL_ERROR"] == 1
    assert rep["scored_cells_n"] == 0
    assert rep["primary_headline_eligible"] is False
