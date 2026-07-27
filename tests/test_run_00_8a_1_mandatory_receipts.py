"""RUN 00.8A.1 — mandatory evidence receipts at terminalization boundary."""

from __future__ import annotations

import copy
import inspect

import pytest

from conditioned_kernel.commissioning_executor import (
    CommissioningExecutor,
    default_perfect_responder,
)
from conditioned_kernel.evidence_verification import (
    make_control_receipt,
    make_packet_receipt,
)
from conditioned_kernel.m0_ledger_integration import (
    IntegrationInputs,
    M0LedgerError,
    M0LedgerSession,
    M0TerminalClassification,
    synthetic_pass_receipts,
    terminalize_synthetic,
)
from conditioned_kernel.m0_manifest import PACKET_CONTRACT_VERSION, build_candidate_manifest
from conditioned_kernel.persistent_terminal_ledger import PersistentTerminalLedger
from conditioned_kernel.m0_admission import recompute_manifest_sha256
from conditioned_kernel.relational_scorer import score_cell


@pytest.fixture
def manifest():
    return build_candidate_manifest()


def _score(manifest, pc):
    gold = manifest["included_tasks"][0]["gold"]
    return score_cell(
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        gold=gold,
        proposed_assertions=gold["expected_relations"],
        inference_status="completed",
    )


def test_8a1_missing_packet_receipt_fails_direct_session(manifest):
    pc = manifest["planned_cells"][0]
    _, c_rec = synthetic_pass_receipts(pc)
    with pytest.raises(TypeError):
        # packet_receipt is required on IntegrationInputs
        IntegrationInputs(  # type: ignore[call-arg]
            planned_cell=pc,
            classification=M0TerminalClassification.TIMEOUT,
            control_receipt=c_rec,
        )


def test_8a1_none_packet_receipt_raises(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    _, c_rec = synthetic_pass_receipts(pc)
    # Construct with None by bypassing dataclass if needed — use object.__new__
    # Prefer: call terminalize after forcing None via setattr
    p_rec, c_rec = synthetic_pass_receipts(pc)
    inp = IntegrationInputs(
        planned_cell=pc,
        classification=M0TerminalClassification.TIMEOUT,
        packet_receipt=p_rec,
        control_receipt=c_rec,
    )
    object.__setattr__(inp, "packet_receipt", None)
    with pytest.raises(M0LedgerError) as ei:
        s.terminalize(inp)
    assert ei.value.reason_code == "PACKET_RECEIPT_REQUIRED"


def test_8a1_none_control_receipt_raises(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    p_rec, c_rec = synthetic_pass_receipts(pc)
    inp = IntegrationInputs(
        planned_cell=pc,
        classification=M0TerminalClassification.TIMEOUT,
        packet_receipt=p_rec,
        control_receipt=c_rec,
    )
    object.__setattr__(inp, "control_receipt", None)
    with pytest.raises(M0LedgerError) as ei:
        s.terminalize(inp)
    assert ei.value.reason_code == "CONTROL_RECEIPT_REQUIRED"


def test_8a1_caller_pass_strings_not_on_api(manifest):
    fields = IntegrationInputs.__dataclass_fields__
    assert "require_evidence_receipts" not in fields
    assert "packet_verification_status" not in fields
    assert "control_verification_status" not in fields


def test_8a1_direct_session_without_receipts_cannot_use_pass_strings(manifest):
    """Pre-fix bypass class: omit receipts + claim PASS — now impossible."""
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    rec = _score(manifest, pc)
    # No packet/control receipts in kwargs — must TypeError (required fields)
    with pytest.raises(TypeError):
        s.terminalize(
            IntegrationInputs(  # type: ignore[call-arg]
                planned_cell=pc,
                classification=M0TerminalClassification.SCORED,
                score_record=rec,
                packet_verification_status="pass",  # type: ignore[call-arg]
                control_verification_status="pass",  # type: ignore[call-arg]
            )
        )


def test_8a1_fail_control_receipt_wins_over_diagnostic_pass(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    p_rec, _ = synthetic_pass_receipts(pc)
    fail_c = make_control_receipt(
        cell_id=pc["cell_id"],
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        paired_cell_id=None,
        verdict="FAIL",
        reason_codes=["BYTE_MISMATCH"],
    )
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.SCORED,
            packet_receipt=p_rec,
            control_receipt=fail_c,
            score_record=_score(manifest, pc),
            packet_verification_status_diagnostic="pass",
            control_verification_status_diagnostic="pass",
            provenance_complete=True,
            model_digest="sha256:x",
        )
    )
    assert term["control_verification_status"] == "fail"
    assert term["terminal_classification"] == "CONTROL_CONTRACT_FAILED"
    assert term["primary_score"] is None
    assert term["control_receipt_hash"] is not None


def test_8a1_fail_packet_receipt_wins(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    _, c_rec = synthetic_pass_receipts(pc)
    fail_p = make_packet_receipt(
        cell_id=pc["cell_id"],
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        request_sha256="cd" * 32,
        complete_byte_length=0,
        packet_contract_version=PACKET_CONTRACT_VERSION,
        verdict="FAIL",
        reason_codes=["PACKET_FAIL"],
    )
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.SCORED,
            packet_receipt=fail_p,
            control_receipt=c_rec,
            score_record=_score(manifest, pc),
            packet_verification_status_diagnostic="pass",
            provenance_complete=True,
        )
    )
    assert term["packet_verification_status"] == "fail"
    assert term["terminal_classification"] == "PACKET_CONTRACT_FAILED"
    assert term["primary_score"] is None


def test_8a1_receipt_cell_mismatch_fails(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    other = manifest["planned_cells"][1]
    bad_p = make_packet_receipt(
        cell_id=other["cell_id"],  # wrong cell
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        request_sha256="ab" * 32,
        complete_byte_length=10,
        packet_contract_version=PACKET_CONTRACT_VERSION,
        verdict="PASS",
    )
    _, c_rec = synthetic_pass_receipts(pc)
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.TIMEOUT,
            packet_receipt=bad_p,
            control_receipt=c_rec,
            provenance_complete=True,
        )
    )
    assert term["packet_verification_status"] == "fail"
    assert term["terminal_classification"] == "PACKET_CONTRACT_FAILED"
    assert "EVIDENCE_RECEIPT_CELL_MISMATCH" in term["terminal_reason_codes"] or any(
        "MISMATCH" in r for r in term["terminal_reason_codes"]
    )


def test_8a1_receipt_condition_mismatch_fails(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    bad_p = make_packet_receipt(
        cell_id=pc["cell_id"],
        task_id=pc["task_id"],
        condition_id="C0_bare",  # likely wrong
        request_sha256="ab" * 32,
        complete_byte_length=10,
        packet_contract_version=PACKET_CONTRACT_VERSION,
        verdict="PASS",
    )
    if bad_p["condition_id"] == pc["condition_id"]:
        bad_p = make_packet_receipt(
            cell_id=pc["cell_id"],
            task_id=pc["task_id"],
            condition_id="C9_forged",
            request_sha256="ab" * 32,
            complete_byte_length=10,
            packet_contract_version=PACKET_CONTRACT_VERSION,
            verdict="PASS",
        )
    _, c_rec = synthetic_pass_receipts(pc)
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.TIMEOUT,
            packet_receipt=bad_p,
            control_receipt=c_rec,
            provenance_complete=True,
        )
    )
    assert term["packet_verification_status"] == "fail"


def test_8a1_receipt_hash_retained(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    p_rec, c_rec = synthetic_pass_receipts(pc)
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.TIMEOUT,
            packet_receipt=p_rec,
            control_receipt=c_rec,
            provenance_complete=True,
        )
    )
    assert term["packet_request_hash"] == p_rec["receipt_sha256"]
    assert term["control_receipt_hash"] == c_rec["receipt_sha256"]
    assert term["packet_verification_status"] == "pass"
    assert term["control_verification_status"] == "pass"


def test_8a1_executor_still_succeeds_with_receipts(tmp_path, manifest):
    gold_map = {t["task_id"]: t["gold"] for t in manifest["included_tasks"]}
    ex = CommissioningExecutor(
        manifest=manifest,
        ledger_dir=tmp_path / "run",
        gold_by_task=gold_map,
        responder=default_perfect_responder(gold_map),
    )
    terms = ex.run_all()
    assert len(terms) == manifest["planned_cell_count"]
    for t in terms:
        assert t["packet_verification_status"] == "pass"
        assert t["control_verification_status"] == "pass"
        assert t["scientific_completion"] is False
        assert t["headline_eligible"] is False


def test_8a1_persistent_restart_intact(tmp_path, manifest):
    ids = {c["cell_id"] for c in manifest["planned_cells"]}
    sha = recompute_manifest_sha256(manifest)
    led = PersistentTerminalLedger.open(
        tmp_path / "led", manifest_sha256=sha, planned_cell_ids=ids
    )
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    term = terminalize_synthetic(
        s, cell_id=pc["cell_id"], classification=M0TerminalClassification.TIMEOUT
    )
    led.append_terminal(term)
    led2 = PersistentTerminalLedger.open(
        tmp_path / "led", manifest_sha256=sha, planned_cell_ids=ids
    )
    assert led2.has(pc["cell_id"])
    with pytest.raises(Exception) as ei:
        led2.append_terminal(term)
    assert "DUPLICATE" in str(ei.value).upper() or getattr(
        ei.value, "reason_code", ""
    ) == "DUPLICATE_TERMINALIZATION"


def test_8a1_score_binding_intact(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    c1 = next(c for c in manifest["planned_cells"] if "C1" in c["condition_id"])
    c3 = next(c for c in manifest["planned_cells"] if "C3" in c["condition_id"])
    rec = _score(manifest, c3)
    p_rec, c_rec = synthetic_pass_receipts(c1)
    with pytest.raises(M0LedgerError) as ei:
        s.terminalize(
            IntegrationInputs(
                planned_cell=c1,
                classification=M0TerminalClassification.SCORED,
                packet_receipt=p_rec,
                control_receipt=c_rec,
                score_record=rec,
            )
        )
    assert ei.value.reason_code == "SCORE_CELL_MISMATCH"


def test_8a1_commissioning_labels_false(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    term = terminalize_synthetic(
        s, cell_id=pc["cell_id"], classification=M0TerminalClassification.TIMEOUT
    )
    assert term["scientific_completion"] is False
    assert term["headline_eligible"] is False
    assert term.get("m0_authorized") is False


def test_8a1_no_require_evidence_field_in_source():
    import conditioned_kernel.m0_ledger_integration as mod

    src = inspect.getsource(mod)
    assert "require_evidence_receipts" not in src


def test_8a1_retired_manifest_unchanged():
    from pathlib import Path
    from conditioned_kernel.m0_manifest import RETIRED_MANIFEST_SHA256
    from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex
    import json

    p = Path("experiments/manifests/m0_candidate_v1.json")
    if not p.is_file():
        pytest.skip("retired manifest not in tree")
    m = json.loads(p.read_text(encoding="utf-8"))
    assert m["manifest_sha256"] == RETIRED_MANIFEST_SHA256
    body = {k: v for k, v in m.items() if k != "manifest_sha256"}
    assert sha256_hex(canonical_json_bytes(body)) == RETIRED_MANIFEST_SHA256
