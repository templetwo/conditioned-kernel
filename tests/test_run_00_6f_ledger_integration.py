"""RUN 00.6F — TerminalLedger integration (offline synthetic outcomes)."""

from __future__ import annotations

import copy

import pytest

from conditioned_kernel.control_contract import ConditionId
from conditioned_kernel.m0_ledger_integration import (
    IntegrationInputs,
    M0LedgerError,
    M0LedgerSession,
    M0TerminalClassification,
    terminalize_synthetic,
)
from conditioned_kernel.m0_manifest import build_candidate_manifest
from conditioned_kernel.relational_scorer import score_cell, score_record_hash


@pytest.fixture(scope="module")
def manifest():
    return build_candidate_manifest()


@pytest.fixture
def session(manifest):
    return M0LedgerSession(copy.deepcopy(manifest))


def _gold(manifest):
    return manifest["included_tasks"][0]["gold"]


def _perfect_score(manifest, planned_cell):
    gold = _gold(manifest)
    return score_cell(
        task_id=gold["task_id"],
        condition_id=planned_cell["condition_id"],
        gold=gold,
        proposed_assertions=gold["expected_relations"],
        inference_status="completed",
        repo_commit=manifest["repository_commit"],
        model_provenance={"model_tag": planned_cell["model_tag"]},
    )


def _cell(manifest, condition: str):
    return next(
        c for c in manifest["planned_cells"] if c["condition_id"] == condition
    )


def test_every_planned_cell_one_terminal(session, manifest):
    for pc in manifest["planned_cells"]:
        rec = _perfect_score(manifest, pc)
        terminalize_synthetic(
            session,
            cell_id=pc["cell_id"],
            classification=M0TerminalClassification.SCORED,
            score_record=rec,
            inference_status="completed",
        )
    session.validate_complete()
    assert session.ledger.terminal_count() == session.ledger.planned_count()
    assert len(session.terminal_cells()) == manifest["planned_cell_count"]


def test_duplicate_terminalization_fails_closed(session, manifest):
    pc = manifest["planned_cells"][0]
    rec = _perfect_score(manifest, pc)
    terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.SCORED,
        score_record=rec,
    )
    with pytest.raises(M0LedgerError) as ei:
        terminalize_synthetic(
            session,
            cell_id=pc["cell_id"],
            classification=M0TerminalClassification.SCORED,
            score_record=rec,
        )
    assert ei.value.reason_code == "DUPLICATE_TERMINALIZATION"


def test_unplanned_cell_fails_closed(session, manifest):
    from conditioned_kernel.m0_ledger_integration import synthetic_pass_receipts

    pc = copy.deepcopy(manifest["planned_cells"][0])
    # receipts for a planned cell identity, but cell_id is unplanned
    p_rec, c_rec = synthetic_pass_receipts(manifest["planned_cells"][0])
    pc["cell_id"] = "0" * 64
    with pytest.raises(M0LedgerError) as ei:
        session.terminalize(
            IntegrationInputs(
                planned_cell=pc,
                classification=M0TerminalClassification.TIMEOUT,
                packet_receipt=p_rec,
                control_receipt=c_rec,
            )
        )
    assert ei.value.reason_code == "UNPLANNED_CELL"


def test_timeout_emits_null_score(session, manifest):
    pc = _cell(manifest, ConditionId.C1_BUDGET_MATCHED_BARE.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.TIMEOUT,
        inference_status="timeout",
    )
    assert term["terminal_classification"] == "TIMEOUT"
    assert term["primary_score"] is None
    assert term["exact_relation_set_match"] is None
    assert term["scientific_completion"] is False
    assert term["headline_eligible"] is False


def test_transport_error_null_score(session, manifest):
    pc = _cell(manifest, ConditionId.C0_BARE.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.TRANSPORT_ERROR,
    )
    assert term["primary_score"] is None
    assert term["terminal_classification"] == "TRANSPORT_ERROR"


def test_invalid_response_null_score(session, manifest):
    pc = _cell(manifest, ConditionId.C2_INSTRUCTION_IDENTICAL.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.INVALID_RESPONSE,
    )
    assert term["primary_score"] is None


def test_control_contract_failure_retained(session, manifest):
    pc = _cell(manifest, ConditionId.C1_BUDGET_MATCHED_BARE.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.CONTROL_CONTRACT_FAILED,
        control_verification_status="fail",
        reason_codes=("CONTROL_CONTRACT_FAILED",),
    )
    assert term["terminal_classification"] == "CONTROL_CONTRACT_FAILED"
    assert term["primary_score"] is None
    assert term["control_verification_status"] == "fail"
    assert session.ledger.terminal_count() == 1


def test_packet_contract_failure_retained(session, manifest):
    pc = _cell(manifest, ConditionId.C3_STATIC_CK.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.PACKET_CONTRACT_FAILED,
        packet_verification_status="fail",
    )
    assert term["terminal_classification"] == "PACKET_CONTRACT_FAILED"
    assert term["primary_score"] is None


def test_task_contract_failure_retained(session, manifest):
    pc = _cell(manifest, ConditionId.C3_STATIC_CK.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.TASK_CONTRACT_ERROR,
    )
    assert term["primary_score"] is None
    assert term["terminal_classification"] == "TASK_CONTRACT_ERROR"


def test_scorer_internal_error_retained(session, manifest):
    pc = _cell(manifest, ConditionId.C0_BARE.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.SCORER_INTERNAL_ERROR,
    )
    assert term["primary_score"] is None
    assert term["terminal_classification"] == "SCORER_INTERNAL_ERROR"


def test_missing_provenance_retained(session, manifest):
    pc = _cell(manifest, ConditionId.C3_STATIC_CK.value)
    rec = _perfect_score(manifest, pc)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.SCORED,
        score_record=rec,
        provenance_complete=False,
    )
    assert term["terminal_classification"] == "PROVENANCE_INCOMPLETE"
    assert term["primary_score"] is None
    assert term["provenance_completeness"] is False


def test_scored_preserves_score_record_hash(session, manifest):
    pc = _cell(manifest, ConditionId.C3_STATIC_CK.value)
    rec = _perfect_score(manifest, pc)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.SCORED,
        score_record=rec,
        inference_status="completed",
    )
    assert term["primary_score"] == 1.0
    assert term["score_record_hash"] == score_record_hash(rec)
    assert term["scientific_completion"] is False
    assert term["headline_eligible"] is False


def test_malformed_assertions_null(session, manifest):
    pc = _cell(manifest, ConditionId.C2_INSTRUCTION_IDENTICAL.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.MALFORMED_ASSERTIONS,
    )
    assert term["primary_score"] is None


def test_no_final_response_null(session, manifest):
    pc = _cell(manifest, ConditionId.C0_BARE.value)
    term = terminalize_synthetic(
        session,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.NO_FINAL_RESPONSE,
    )
    assert term["primary_score"] is None


def test_failed_cell_never_disappears(session, manifest):
    """Timeout + control fail + scored still all in ledger counts."""
    c0 = _cell(manifest, ConditionId.C0_BARE.value)
    c1 = _cell(manifest, ConditionId.C1_BUDGET_MATCHED_BARE.value)
    c2 = _cell(manifest, ConditionId.C2_INSTRUCTION_IDENTICAL.value)
    c3 = _cell(manifest, ConditionId.C3_STATIC_CK.value)
    terminalize_synthetic(
        session, cell_id=c0["cell_id"], classification=M0TerminalClassification.TIMEOUT
    )
    terminalize_synthetic(
        session,
        cell_id=c1["cell_id"],
        classification=M0TerminalClassification.CONTROL_CONTRACT_FAILED,
        control_verification_status="fail",
    )
    terminalize_synthetic(
        session,
        cell_id=c2["cell_id"],
        classification=M0TerminalClassification.INVALID_RESPONSE,
    )
    rec = _perfect_score(manifest, c3)
    terminalize_synthetic(
        session,
        cell_id=c3["cell_id"],
        classification=M0TerminalClassification.SCORED,
        score_record=rec,
    )
    session.validate_complete()
    classes = {t["terminal_classification"] for t in session.terminal_cells()}
    assert "TIMEOUT" in classes
    assert "CONTROL_CONTRACT_FAILED" in classes
    assert "INVALID_RESPONSE" in classes
    assert "SCORED" in classes
    assert session.ledger.planned_count() == 4


def test_no_retry_replacement(session, manifest):
    """A failed cell stays; second terminalization is rejected (no replace)."""
    pc = _cell(manifest, ConditionId.C1_BUDGET_MATCHED_BARE.value)
    terminalize_synthetic(
        session, cell_id=pc["cell_id"], classification=M0TerminalClassification.TIMEOUT
    )
    rec = _perfect_score(manifest, pc)
    with pytest.raises(M0LedgerError) as ei:
        terminalize_synthetic(
            session,
            cell_id=pc["cell_id"],
            classification=M0TerminalClassification.SCORED,
            score_record=rec,
        )
    assert ei.value.reason_code == "DUPLICATE_TERMINALIZATION"
    term = session.terminal_cells()[0]
    assert term["terminal_classification"] == "TIMEOUT"
    assert term["primary_score"] is None


def test_wrong_manifest_id_rejected(session, manifest):
    from conditioned_kernel.m0_ledger_integration import synthetic_pass_receipts

    pc = copy.deepcopy(manifest["planned_cells"][0])
    p_rec, c_rec = synthetic_pass_receipts(pc)
    pc["manifest_id"] = "ck.m0.forged"
    with pytest.raises(M0LedgerError) as ei:
        session.terminalize(
            IntegrationInputs(
                planned_cell=pc,
                classification=M0TerminalClassification.TIMEOUT,
                packet_receipt=p_rec,
                control_receipt=c_rec,
            )
        )
    assert ei.value.reason_code == "WRONG_MANIFEST_ID"
