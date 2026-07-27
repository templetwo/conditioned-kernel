"""RUN 00.8A — commissioning trust-boundary closure (offline, no models)."""

from __future__ import annotations

import copy
import json

import pytest

from conditioned_kernel.commissioning_executor import (
    CommissioningError,
    CommissioningExecutor,
    default_perfect_responder,
    enforce_execution_scope,
)
from conditioned_kernel.control_contract import PAD_DELIMITER, require_ratified_experiment_contract
from conditioned_kernel.edge import EdgeProfile
from conditioned_kernel.evidence_verification import (
    make_control_receipt,
    make_packet_receipt,
)
from conditioned_kernel.m0_admission import (
    evaluate_admission,
    recompute_manifest_sha256,
    verify_manifest_integrity,
)
from conditioned_kernel.m0_ledger_integration import (
    IntegrationInputs,
    M0LedgerError,
    M0LedgerSession,
    M0TerminalClassification,
    synthetic_pass_receipts,
    terminalize_synthetic,
)
from conditioned_kernel.m0_manifest import (
    RETIRED_MANIFEST_SHA256,
    FrozenArtifactError,
    build_candidate_manifest,
    write_frozen_artifacts,
)
from conditioned_kernel.persistent_terminal_ledger import (
    PersistentLedgerError,
    PersistentTerminalLedger,
)
from conditioned_kernel.relational_scorer import score_cell
from conditioned_kernel.response_scoring_adapter import (
    parse_structured_response,
    score_parsed_response,
)
from conditioned_kernel.runtime_provenance import (
    build_runtime_provenance,
    compute_provenance_completeness,
    synthetic_model_digest,
)


@pytest.fixture
def manifest():
    return build_candidate_manifest()


@pytest.fixture
def gold_map(manifest):
    return {t["task_id"]: t["gold"] for t in manifest["included_tasks"]}


def _score(manifest, pc):
    gold = manifest["included_tasks"][0]["gold"]
    return score_cell(
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        gold=gold,
        proposed_assertions=gold["expected_relations"],
        inference_status="completed",
        repo_commit=manifest["repository_commit"],
    )


def _full_auth(manifest):
    return {
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": recompute_manifest_sha256(manifest),
        "authorizing_principal": "anthony",
        "authorization_timestamp": "2026-07-28T00:00:00Z",
        "experiment_contract_id": "ck.exp.m0.v1",
        "authorized_model": manifest["model_tag"],
        "authorized_planned_cell_count": manifest["planned_cell_count"],
        "authorized_condition_set": list(manifest["condition_set"]),
        "resolved_model_digest": synthetic_model_digest(manifest["model_tag"]),
    }


# --- FIX 7: falsy generation parameters ---


def test_temperature_zero_preserved():
    p = EdgeProfile.from_dict(
        {
            "profile_id": "t",
            "temperature": 0.0,
            "seed": 0,
            "model": "qwen2.5:0.5b",
        }
    )
    assert p.temperature == 0.0
    assert p.seed == 0


def test_seed_zero_not_replaced_with_42():
    p = EdgeProfile.from_dict({"profile_id": "t", "seed": 0, "temperature": 0.0})
    assert p.seed == 0


# --- FIX 1: manifest integrity ---


def test_tampered_manifest_fails_admission(manifest):
    m = copy.deepcopy(manifest)
    m["model_tag"] = "tampered-model"
    # leave stale hash
    ok, claimed, computed, reasons = verify_manifest_integrity(m)
    assert ok is False
    assert "MANIFEST_HASH_MISMATCH" in reasons
    rep = evaluate_admission(manifest=m, terminal_cells=[])
    assert rep["manifest_integrity_ok"] is False
    assert rep["authorization_status"] != "ratified_receipt_present"
    assert claimed != computed


def test_canonical_hash_recomputed_during_admission(manifest):
    rep = evaluate_admission(manifest=manifest, terminal_cells=[])
    assert rep["manifest_hash_computed"] == recompute_manifest_sha256(manifest)
    assert rep["manifest_integrity_ok"] is True


def test_stale_embedded_hash_fails(manifest):
    m = copy.deepcopy(manifest)
    m["manifest_sha256"] = "0" * 64
    rep = evaluate_admission(manifest=m, terminal_cells=[])
    assert rep["manifest_integrity_ok"] is False
    assert "MANIFEST_HASH_MISMATCH" in rep["manifest_integrity_reasons"]


# --- FIX 2: authorization binding ---


def test_wrong_authorization_hash_fails(manifest):
    bad = _full_auth(manifest)
    bad["manifest_sha256"] = "1" * 64
    rep = evaluate_admission(
        manifest=manifest, terminal_cells=[], authorization_receipt=bad
    )
    assert "AUTHORIZATION_MANIFEST_HASH_MISMATCH" in rep["authorization_reasons"]
    assert rep["primary_headline_eligible"] is False


def test_wrong_authorized_model_fails(manifest):
    bad = _full_auth(manifest)
    bad["authorized_model"] = "other:model"
    rep = evaluate_admission(
        manifest=manifest, terminal_cells=[], authorization_receipt=bad
    )
    assert "AUTHORIZATION_MODEL_MISMATCH" in rep["authorization_reasons"]


def test_wrong_authorized_cell_count_fails(manifest):
    bad = _full_auth(manifest)
    bad["authorized_planned_cell_count"] = 999
    rep = evaluate_admission(
        manifest=manifest, terminal_cells=[], authorization_receipt=bad
    )
    assert "AUTHORIZATION_CELL_COUNT_MISMATCH" in rep["authorization_reasons"]


# --- FIX 3: persistent ledger ---


def test_persistent_ledger_survives_restart(tmp_path, manifest):
    ids = {c["cell_id"] for c in manifest["planned_cells"]}
    sha = recompute_manifest_sha256(manifest)
    led = PersistentTerminalLedger.open(
        tmp_path / "led", manifest_sha256=sha, planned_cell_ids=ids
    )
    pc = manifest["planned_cells"][0]
    term = {
        "cell_id": pc["cell_id"],
        "task_id": pc["task_id"],
        "condition_id": pc["condition_id"],
        "terminal_classification": "TIMEOUT",
        "primary_score": None,
        "scientific_completion": False,
        "headline_eligible": False,
    }
    led.append_terminal(term)
    # new process/session
    led2 = PersistentTerminalLedger.open(
        tmp_path / "led", manifest_sha256=sha, planned_cell_ids=ids
    )
    assert led2.has(pc["cell_id"])
    with pytest.raises(PersistentLedgerError) as ei:
        led2.append_terminal(term)
    assert ei.value.reason_code == "DUPLICATE_TERMINALIZATION"


def test_persistent_unplanned_fails(tmp_path, manifest):
    sha = recompute_manifest_sha256(manifest)
    led = PersistentTerminalLedger.open(
        tmp_path / "led2",
        manifest_sha256=sha,
        planned_cell_ids={c["cell_id"] for c in manifest["planned_cells"]},
    )
    with pytest.raises(PersistentLedgerError) as ei:
        led.append_terminal({"cell_id": "f" * 64, "terminal_classification": "TIMEOUT"})
    assert ei.value.reason_code == "UNPLANNED_CELL"


# --- FIX 4: score-to-cell binding ---


def test_score_condition_mismatch_fails(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    c1 = next(
        c
        for c in manifest["planned_cells"]
        if "C1" in c["condition_id"]
    )
    c3 = next(
        c
        for c in manifest["planned_cells"]
        if "C3" in c["condition_id"]
    )
    # Score computed for C3, applied to C1
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


def test_scored_without_score_record_fails(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    p_rec, c_rec = synthetic_pass_receipts(pc)
    with pytest.raises(M0LedgerError) as ei:
        s.terminalize(
            IntegrationInputs(
                planned_cell=pc,
                classification=M0TerminalClassification.SCORED,
                packet_receipt=p_rec,
                control_receipt=c_rec,
                score_record=None,
            )
        )
    assert ei.value.reason_code == "SCORED_WITHOUT_SCORE_RECORD"


def test_expected_hash_mismatch_fails(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    rec = _score(manifest, pc)
    rec = dict(rec)
    rec["expected_relation_hash"] = "deadbeef" * 8
    p_rec, c_rec = synthetic_pass_receipts(pc)
    with pytest.raises(M0LedgerError) as ei:
        s.terminalize(
            IntegrationInputs(
                planned_cell=pc,
                classification=M0TerminalClassification.SCORED,
                packet_receipt=p_rec,
                control_receipt=c_rec,
                score_record=rec,
            )
        )
    assert ei.value.reason_code == "SCORE_EXPECTED_HASH_MISMATCH"


def test_planned_expected_hash_not_overwritten(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    rec = _score(manifest, pc)
    term = terminalize_synthetic(
        s,
        cell_id=pc["cell_id"],
        classification=M0TerminalClassification.TIMEOUT,
        score_record=rec,  # should not overwrite planned expected
    )
    assert term["expected_relation_hash"] == pc["expected_relation_hash"]


# --- FIX 5: receipt-derived control ---


def test_failed_control_receipt_cannot_be_called_pass(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    pc = manifest["planned_cells"][0]
    fail_rec = make_control_receipt(
        cell_id=pc["cell_id"],
        task_id=pc["task_id"],
        condition_id=pc["condition_id"],
        paired_cell_id=None,
        verdict="FAIL",
        reason_codes=["BYTE_MISMATCH"],
    )
    # Caller diagnostic PASS string cannot override FAIL receipt
    term = s.terminalize(
        IntegrationInputs(
            planned_cell=pc,
            classification=M0TerminalClassification.SCORED,
            score_record=_score(manifest, pc),
            packet_verification_status_diagnostic="pass",
            control_verification_status_diagnostic="pass",
            control_receipt=fail_rec,
            packet_receipt=make_packet_receipt(
                cell_id=pc["cell_id"],
                task_id=pc["task_id"],
                condition_id=pc["condition_id"],
                request_sha256="ab" * 32,
                complete_byte_length=10,
                packet_contract_version="ck.packet_contract.v1",
                verdict="PASS",
            ),
            model_digest="sha256:x",
            runtime_provenance=_full_prov(pc),
            provenance_complete=None,
        )
    )
    assert term["control_verification_status"] == "fail"
    assert term["terminal_classification"] == "CONTROL_CONTRACT_FAILED"
    assert term["primary_score"] is None


def _full_prov(pc):
    return build_runtime_provenance(
        model_tag=pc["model_tag"],
        resolved_model_digest=synthetic_model_digest(pc["model_tag"]),
        runtime_version="test",
        host_architecture="test",
        requested_generation_options=dict(pc["generation_parameters"]),
        confirmed_generation_options=dict(pc["generation_parameters"]),
        packet_request_sha256="aa" * 32,
        raw_response_sha256="bb" * 32,
        started_at="t0",
        ended_at="t1",
        process_id=1,
    )


# --- FIX 9: scientific scope ---


def test_scientific_scope_requires_contract():
    with pytest.raises(Exception):
        require_ratified_experiment_contract("scientific_experiment", None)
    with pytest.raises(CommissioningError) as ei:
        enforce_execution_scope("scientific_experiment", experiment_contract_id=None)
    assert ei.value.reason_code


def test_commissioning_scope_ok():
    enforce_execution_scope("commissioning_validation")


# --- FIX 10: response adapter ---


def test_empty_response_null_score_not_zero(manifest):
    pc = manifest["planned_cells"][0]
    gold = manifest["included_tasks"][0]["gold"]
    p = parse_structured_response("", inference_status="completed")
    assert p["parse_kind"] == "EMPTY_FINAL_RESPONSE"
    s = score_parsed_response(p, planned_cell=pc, gold=gold)
    assert s["primary_score"] is None
    assert s["terminal_classification"] == "NO_FINAL_RESPONSE"


def test_empty_assertion_list_scored_deterministically(manifest):
    pc = manifest["planned_cells"][0]
    gold = manifest["included_tasks"][0]["gold"]
    raw = b'{"continuity_assertions":[]}'
    p = parse_structured_response(raw)
    assert p["parse_kind"] == "EMPTY_ASSERTION_LIST"
    s = score_parsed_response(p, planned_cell=pc, gold=gold)
    assert s["terminal_classification"] == "SCORED"
    assert s["primary_score"] == 0.0


def test_malformed_json_null(manifest):
    pc = manifest["planned_cells"][0]
    gold = manifest["included_tasks"][0]["gold"]
    p = parse_structured_response("{not json")
    s = score_parsed_response(p, planned_cell=pc, gold=gold)
    assert s["primary_score"] is None
    assert s["terminal_classification"] == "MALFORMED_ASSERTIONS"


def test_prose_only_null(manifest):
    pc = manifest["planned_cells"][0]
    gold = manifest["included_tasks"][0]["gold"]
    p = parse_structured_response("The relation remains open between threads.")
    s = score_parsed_response(p, planned_cell=pc, gold=gold)
    assert s["primary_score"] is None
    assert "PROSE_ONLY" in s["reason_codes"] or s["parse_kind"] == "PROSE_ONLY"


def test_raw_response_hash_retained():
    p = parse_structured_response(b'{"continuity_assertions":[]}')
    assert len(p["raw_response_sha256"]) == 64
    assert p["raw_response_byte_length"] > 0


# --- FIX 12: control receipts headline ---


def test_control_receipt_headline_always_false():
    r = make_control_receipt(
        cell_id="c",
        task_id="t",
        condition_id="C3",
        paired_cell_id=None,
        verdict="PASS",
    )
    assert r["headline_eligible"] is False
    assert r["scientific_completion"] is False
    assert r["scientific_status"] == "control_verification_only"


# --- FIX 13: pad marker neutral ---


def test_pad_delimiter_condition_neutral():
    assert "CK_PAD" not in PAD_DELIMITER
    assert "C1" not in PAD_DELIMITER
    assert "C3" not in PAD_DELIMITER


# --- FIX 14: frozen artifact overwrite ---


def test_frozen_manifest_overwrite_refused(tmp_path, manifest):
    write_frozen_artifacts(out_dir=tmp_path)
    # mutate builder inputs indirectly by writing different content
    p = tmp_path / "m0_candidate_v1.json"
    # First write exists; force different bytes via direct edit then rewrite
    other = copy.deepcopy(manifest)
    other["model_tag"] = "other"
    body = {k: v for k, v in other.items() if k != "manifest_sha256"}
    from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

    other["manifest_sha256"] = sha256_hex(canonical_json_bytes(body))
    p.write_text(json.dumps(other, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(FrozenArtifactError) as ei:
        write_frozen_artifacts(out_dir=tmp_path)
    assert ei.value.reason_code == "FROZEN_ARTIFACT_OVERWRITE_REFUSED"


def test_retired_manifest_hash_constant():
    assert (
        RETIRED_MANIFEST_SHA256
        == "9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922"
    )


# --- FIX 16: provenance computed ---


def test_provenance_completeness_computed_not_caller():
    incomplete = {"model_tag": "x"}
    ok, missing = compute_provenance_completeness(incomplete)
    assert ok is False
    assert "MODEL_DIGEST_MISSING" in missing


# --- Executor traces ---


def test_synthetic_executor_all_scored(tmp_path, manifest, gold_map):
    ex = CommissioningExecutor(
        manifest=manifest,
        ledger_dir=tmp_path / "run",
        gold_by_task=gold_map,
        responder=default_perfect_responder(gold_map),
    )
    terms = ex.run_all()
    assert len(terms) == manifest["planned_cell_count"]
    for t in terms:
        assert t["scientific_completion"] is False
        assert t["headline_eligible"] is False
        assert t["m0_authorized"] is False
    # restart duplicate fails
    with pytest.raises(CommissioningError) as ei:
        ex.run_cell(manifest["planned_cells"][0]["cell_id"])
    assert ei.value.reason_code == "DUPLICATE_TERMINALIZATION"
    # new session same path
    ex2 = CommissioningExecutor(
        manifest=manifest,
        ledger_dir=tmp_path / "run",
        gold_by_task=gold_map,
        responder=default_perfect_responder(gold_map),
    )
    with pytest.raises(CommissioningError) as ei2:
        ex2.run_cell(manifest["planned_cells"][0]["cell_id"])
    assert ei2.value.reason_code == "DUPLICATE_TERMINALIZATION"


def test_executor_c1_timeout_trace(tmp_path, manifest, gold_map):
    c1_id = next(c["cell_id"] for c in manifest["planned_cells"] if "C1" in c["condition_id"])

    def resp(planned):
        if planned["cell_id"] == c1_id:
            return {"_inject": "timeout"}
        return default_perfect_responder(gold_map)(planned)

    ex = CommissioningExecutor(
        manifest=manifest,
        ledger_dir=tmp_path / "to",
        gold_by_task=gold_map,
        responder=resp,
    )
    term = ex.run_cell(c1_id)
    assert term["terminal_classification"] == "TIMEOUT"
    assert term["primary_score"] is None


def test_executor_control_fail_trace(tmp_path, manifest, gold_map):
    cid = manifest["planned_cells"][0]["cell_id"]

    def resp(planned):
        if planned["cell_id"] == cid:
            return {"_inject": "control_fail", "body": b'{"continuity_assertions":[]}'}
        return default_perfect_responder(gold_map)(planned)

    ex = CommissioningExecutor(
        manifest=manifest,
        ledger_dir=tmp_path / "cf",
        gold_by_task=gold_map,
        responder=resp,
    )
    term = ex.run_cell(cid)
    assert term["terminal_classification"] == "CONTROL_CONTRACT_FAILED"
    assert term["primary_score"] is None


def test_admission_per_condition_counts(manifest):
    s = M0LedgerSession(copy.deepcopy(manifest))
    terms = []
    for pc in manifest["planned_cells"]:
        terms.append(
            terminalize_synthetic(
                s,
                cell_id=pc["cell_id"],
                classification=M0TerminalClassification.TIMEOUT,
            )
        )
    rep = evaluate_admission(manifest=manifest, terminal_cells=terms)
    assert "per_condition_classification_counts" in rep
    for cond, counts in rep["per_condition_classification_counts"].items():
        assert counts.get("TIMEOUT", 0) in (0, 1)


def test_no_model_import_in_commissioning_modules():
    import inspect
    import conditioned_kernel.commissioning_executor as ce
    import conditioned_kernel.persistent_terminal_ledger as pl
    import conditioned_kernel.response_scoring_adapter as rsa

    for mod in (ce, pl, rsa):
        src = inspect.getsource(mod)
        assert "import ollama" not in src
        assert "httpx" not in src
        assert "requests." not in src
