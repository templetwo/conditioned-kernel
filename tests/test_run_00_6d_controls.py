"""RUN 00.6D — packet sufficiency and mechanically matched controls.

No model invocation. Offline deterministic fixtures only.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from conditioned_kernel.control_contract import (
    CONTRAST_DEFINITIONS,
    CONTROL_CONTRACT_FAILED,
    CompiledPacket,
    ConditionId,
    ControlVerdict,
    PacketCompileError,
    RuntimeSettings,
    TaskDependencyAnnotation,
    assert_no_scientific_completion_in_control_receipt,
    build_matched_c3_c1_pair,
    build_serialized_model_input,
    bytes_nfc_nfd_differ,
    compile_condition_packet,
    hash_without_normalization,
    require_ratified_experiment_contract,
    scan_padding_for_leaks,
    verify_control_pair,
    SHARED_SYSTEM_INSTRUCTIONS,
    OUTPUT_SCHEMA,
    PAD_DELIMITER,
)
from conditioned_kernel.outcomes import (
    ExecutionOutcome,
    ManifestCell,
    TerminalLedger,
    TerminalStatus,
)


FIXTURE = Path(__file__).parent / "fixtures" / "control_task_live_plumbing_01.json"


def _ann() -> TaskDependencyAnnotation:
    return TaskDependencyAnnotation.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _rt(**kwargs) -> RuntimeSettings:
    base = dict(model_tag="qwen2.5:0.5b", temperature=0.3, seed=42, num_ctx=2048)
    base.update(kwargs)
    return RuntimeSettings(**base)


# ---------------------------------------------------------------------------
# Byte equality / drift
# ---------------------------------------------------------------------------


def test_c3_c1_exact_utf8_byte_count_equality():
    c3, c1, receipt = build_matched_c3_c1_pair(_ann(), _rt())
    assert c3.byte_count == c1.byte_count
    assert receipt.verdict is ControlVerdict.PASS
    assert c3.byte_count > 0


def test_equality_measured_after_final_serialization():
    c3, c1, _ = build_matched_c3_c1_pair(_ann(), _rt())
    # Re-serialize independently and compare lengths
    again = build_serialized_model_input(
        condition=c1.condition_id,
        system_text=c1.system_text,
        user_content=c1.user_content,
        runtime=c1.runtime,
        schema=c1.schema,
    )
    assert again == c1.complete_bytes
    assert len(again) == c3.byte_count


def test_one_byte_drift_fails_verification():
    c3, c1, _ = build_matched_c3_c1_pair(_ann(), _rt())
    # One-byte shorter target: either construction fails closed, or pair verify fails
    try:
        short = compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=c3.byte_count - 1,
        )
    except PacketCompileError as e:
        assert e.reason_code in (
            "C1_TARGET_UNREACHABLE",
            "C1_BYTE_MATCH_FAILED",
            "BYTE_BUDGET_OVERFLOW",
        )
        return
    rec = verify_control_pair(
        c3,
        short,
        require_byte_equality=True,
        require_instruction_identity=True,
    )
    assert rec.verdict is ControlVerdict.FAIL
    assert any("BYTE_COUNT_MISMATCH" in x or "ONE_BYTE_DRIFT" in x for x in rec.reason_codes)
    assert CONTROL_CONTRACT_FAILED in rec.reason_codes


def test_task_fact_mismatch_fails():
    c3, c1, _ = build_matched_c3_c1_pair(_ann(), _rt())
    # Mutate right body facts in a fresh compile with altered annotation
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for f in data["fields"]:
        if f["classification"] == "REQUIRED_TASK_FACT":
            f["value"] = f["value"] + " EXTRA_HELPFUL_FACT"
            break
    bad = TaskDependencyAnnotation.from_dict(data)
    # Use C2 (no C1 target required) so the signal under test is fact mismatch
    c2_bad = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL,
        bad,
        _rt(),
    )
    rec = verify_control_pair(
        c3, c2_bad, require_byte_equality=False, require_instruction_identity=True
    )
    assert rec.verdict is ControlVerdict.FAIL
    assert "TASK_FACT_MISMATCH" in rec.prohibited_mismatches


def test_instruction_mismatch_fails_when_required():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    # Break instructions on a clone path via C0 system text comparison
    c0 = compile_condition_packet(ConditionId.C0_BARE, _ann(), _rt())
    rec = verify_control_pair(
        c3, c0, require_byte_equality=False, require_instruction_identity=True,
        require_schema_identity=False, require_task_fact_identity=False,
    )
    assert rec.verdict is ControlVerdict.FAIL
    assert "INSTRUCTION_MISMATCH" in rec.prohibited_mismatches


def test_output_schema_mismatch_fails():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE, _ann(), _rt(),
        target_complete_bytes=c3.byte_count,
    )
    # Manually corrupt schema on a shallow copy receipt path
    bad_schema = dict(c1.schema)
    bad_schema["required"] = ["different_key"]
    bad_bytes = build_serialized_model_input(
        condition=c1.condition_id,
        system_text=c1.system_text,
        user_content=c1.user_content,
        runtime=c1.runtime,
        schema=bad_schema,
    )
    c1_bad = CompiledPacket(
        condition_id=c1.condition_id,
        task_id=c1.task_id,
        system_text=c1.system_text,
        user_content=c1.user_content,
        padding_bytes=c1.padding_bytes,
        schema=bad_schema,
        runtime=c1.runtime,
        body=c1.body,
        complete_bytes=bad_bytes,
        task_dep_version=c1.task_dep_version,
    )
    rec = verify_control_pair(
        c3, c1_bad, require_byte_equality=False, require_instruction_identity=True
    )
    assert "OUTPUT_SCHEMA_MISMATCH" in rec.prohibited_mismatches


def test_model_tag_mismatch_fails():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(model_tag="qwen2.5:0.5b"),
        accepted_relations=[],
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE, _ann(), _rt(model_tag="other:1b"),
        target_complete_bytes=c3.byte_count,
    )
    rec = verify_control_pair(
        c3, c1, require_byte_equality=False, require_instruction_identity=True
    )
    assert "MODEL_TAG_MISMATCH" in rec.prohibited_mismatches


def test_generation_parameter_mismatch_fails():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(seed=1), accepted_relations=[]
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE, _ann(), _rt(seed=2),
        target_complete_bytes=c3.byte_count,
    )
    rec = verify_control_pair(
        c3, c1, require_byte_equality=False, require_instruction_identity=True
    )
    assert "GENERATION_PARAMETER_MISMATCH" in rec.prohibited_mismatches


# ---------------------------------------------------------------------------
# Packet sufficiency
# ---------------------------------------------------------------------------


def test_missing_required_task_fact_fails_compilation():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["fields"] = [
        f for f in data["fields"] if f["classification"] != "REQUIRED_TASK_FACT"
    ]
    ann = TaskDependencyAnnotation.from_dict(data)
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(ConditionId.C3_STATIC_CK, ann, _rt())
    assert "REQUIRED_TASK_FACT" in ei.value.reason_code


def test_missing_required_operational_state_fails_compilation():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["fields"] = [
        f for f in data["fields"]
        if f["classification"] != "REQUIRED_OPERATIONAL_STATE"
    ]
    ann = TaskDependencyAnnotation.from_dict(data)
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(ConditionId.C3_STATIC_CK, ann, _rt())
    assert "OPERATIONAL_STATE" in ei.value.reason_code


def test_forbidden_answer_leakage_fails_compilation():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Inject gold into a required fact value
    for f in data["fields"]:
        if f["field_id"] == "fact_local":
            f["value"] = (
                f["value"]
                + " GOLD_ASSERTION_thread_gamma_receipt_remains_open_question_cold_start"
            )
    ann = TaskDependencyAnnotation.from_dict(data)
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(ConditionId.C3_STATIC_CK, ann, _rt())
    assert ei.value.reason_code == "FORBIDDEN_ANSWER_LEAKAGE"


def test_unknown_field_classification_fails_closed():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["fields"].append(
        {
            "field_id": "weird",
            "classification": "NOT_A_REAL_CLASS",
            "value": "x",
        }
    )
    with pytest.raises(PacketCompileError) as ei:
        TaskDependencyAnnotation.from_dict(data)
    assert ei.value.reason_code == "UNKNOWN_FIELD_CLASSIFICATION"


# ---------------------------------------------------------------------------
# Padding
# ---------------------------------------------------------------------------


def test_padding_cannot_contain_task_identifiers():
    with pytest.raises(PacketCompileError):
        scan_padding_for_leaks(
            PAD_DELIMITER + " thread_gamma_receipt ",
            forbidden_fragments=[],
            relation_names=[],
            identifiers=["thread_gamma_receipt"],
        )


def test_padding_cannot_contain_relation_names():
    with pytest.raises(PacketCompileError):
        scan_padding_for_leaks(
            "xxx remains_open yyy",
            forbidden_fragments=[],
            relation_names=["remains_open"],
            identifiers=[],
        )


def test_padding_cannot_contain_expected_answer_fragments():
    with pytest.raises(PacketCompileError):
        scan_padding_for_leaks(
            "pad GOLD_ASSERTION_thread_gamma_receipt_remains_open_question_cold_start pad",
            forbidden_fragments=[
                "GOLD_ASSERTION_thread_gamma_receipt_remains_open_question_cold_start"
            ],
            relation_names=[],
            identifiers=[],
        )


def test_padding_placement_is_deterministic():
    c3_a, c1_a, _ = build_matched_c3_c1_pair(_ann(), _rt())
    c3_b, c1_b, _ = build_matched_c3_c1_pair(_ann(), _rt())
    assert c1_a.user_content == c1_b.user_content
    assert c1_a.padding_bytes == c1_b.padding_bytes
    assert c1_a.complete_bytes == c1_b.complete_bytes


def test_repeated_compilation_byte_identical():
    a = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(),
        accepted_relations=[{"subject_id": "thread_gamma_receipt",
                             "relation": "remains_open",
                             "object_id": "question_cold_start"}],
    )
    b = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(),
        accepted_relations=[{"subject_id": "thread_gamma_receipt",
                             "relation": "remains_open",
                             "object_id": "question_cold_start"}],
    )
    assert a.complete_bytes == b.complete_bytes
    assert a.input_sha256 == b.input_sha256


def test_reordering_source_fields_does_not_change_canonical_bytes():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fields = list(data["fields"])
    data_rev = dict(data)
    data_rev["fields"] = list(reversed(fields))
    ann1 = TaskDependencyAnnotation.from_dict(data)
    ann2 = TaskDependencyAnnotation.from_dict(data_rev)
    p1 = compile_condition_packet(ConditionId.C3_STATIC_CK, ann1, _rt(), accepted_relations=[])
    p2 = compile_condition_packet(ConditionId.C3_STATIC_CK, ann2, _rt(), accepted_relations=[])
    assert p1.complete_bytes == p2.complete_bytes


# ---------------------------------------------------------------------------
# Contrasts / receipts / ledger
# ---------------------------------------------------------------------------


def test_c0_c1_c2_c3_contrasts_documented():
    assert "C3_vs_C0" in CONTRAST_DEFINITIONS
    assert "C3_vs_C1" in CONTRAST_DEFINITIONS
    assert "C3_vs_C2" in CONTRAST_DEFINITIONS
    for k, v in CONTRAST_DEFINITIONS.items():
        assert v["isolates"]
        assert v["not_isolates"]


def test_failed_verifier_marks_headline_ineligible():
    c3, c1, _ = build_matched_c3_c1_pair(_ann(), _rt())
    # Model-tag mismatch is a reliable prohibited failure without C1 pad issues
    other = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, _ann(), _rt(model_tag="other:1b")
    )
    rec = verify_control_pair(
        c3, other, require_byte_equality=False, require_instruction_identity=True
    )
    assert rec.verdict is ControlVerdict.FAIL
    assert rec.headline_eligible is False
    d = rec.to_dict()
    assert d["headline_eligible"] is False
    assert d["scientific_completion"] is False


def test_control_receipt_never_claims_scientific_completion():
    _, _, rec = build_matched_c3_c1_pair(_ann(), _rt())
    assert rec.scientific_completion is False
    assert_no_scientific_completion_in_control_receipt(rec)


def test_failed_control_retained_in_ledger_denominator():
    """Invalid comparison cells stay in the planned ledger with explicit reason."""
    cells = [
        ManifestCell(run_id="r", task_id="t1", condition_id="C3_vs_C1", episode="cmp"),
        ManifestCell(run_id="r", task_id="t2", condition_id="C3_vs_C1", episode="cmp"),
    ]
    ledger = TerminalLedger(cells)
    # t1 pass
    ledger.record(
        cells[0].cell_id,
        ExecutionOutcome.completed_invalid(
            cell=cells[0],
            output=None,
            decision=None,
            reason_codes=("control_pass",),
        ),
    )
    # t2 control contract failed — retained, not dropped
    ledger.record(
        cells[1].cell_id,
        ExecutionOutcome.from_lifecycle(
            cell=cells[1],
            status=TerminalStatus.COMPLETED_INVALID,
            output=None,
            reason_codes=(CONTROL_CONTRACT_FAILED, "BYTE_COUNT_MISMATCH"),
            error=CONTROL_CONTRACT_FAILED,
        ),
    )
    assert ledger.validate() is True
    assert ledger.terminal_count() == 2
    assert ledger.scientific_completion_count() == 0
    failed = [r for r in ledger.rows() if CONTROL_CONTRACT_FAILED in r.reason_codes]
    assert len(failed) == 1


def test_scientific_experiment_scope_requires_contract_id():
    with pytest.raises(Exception) as ei:
        require_ratified_experiment_contract("scientific_experiment", None)
    assert "experiment_contract" in str(ei.value).lower() or "ratified" in str(ei.value).lower()
    # Non-scientific scopes ok
    require_ratified_experiment_contract("live_plumbing", None)
    require_ratified_experiment_contract("offline_test", None)


# ---------------------------------------------------------------------------
# Adversarial fixtures
# ---------------------------------------------------------------------------


def test_adv_control_missing_decisive_fact():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["fields"] = [f for f in data["fields"] if f["field_id"] != "fact_deliverable"]
    # still has one REQUIRED_TASK_FACT
    ann_missing = TaskDependencyAnnotation.from_dict(data)
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c2 = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, ann_missing, _rt(),
    )
    rec = verify_control_pair(
        c3, c2, require_byte_equality=False, require_instruction_identity=True
    )
    assert rec.verdict is ControlVerdict.FAIL
    assert "TASK_FACT_MISMATCH" in rec.prohibited_mismatches


def test_adv_control_extra_helpful_fact():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["fields"].append(
        {
            "field_id": "extra_help",
            "classification": "REQUIRED_TASK_FACT",
            "value": "The correct relation is remains_open.",
        }
    )
    ann_extra = TaskDependencyAnnotation.from_dict(data)
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c2 = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, ann_extra, _rt(),
    )
    rec = verify_control_pair(
        c3, c2, require_byte_equality=False, require_instruction_identity=True
    )
    assert "TASK_FACT_MISMATCH" in rec.prohibited_mismatches


def test_adv_same_facts_reordered_still_match():
    test_reordering_source_fields_does_not_change_canonical_bytes()


def test_adv_hidden_whitespace_byte_difference():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    # Same visible text idea but trailing space in system
    a = build_serialized_model_input(
        condition=ConditionId.C3_STATIC_CK,
        system_text=SHARED_SYSTEM_INSTRUCTIONS,
        user_content=c3.user_content,
        runtime=_rt(),
        schema=OUTPUT_SCHEMA,
    )
    b = build_serialized_model_input(
        condition=ConditionId.C3_STATIC_CK,
        system_text=SHARED_SYSTEM_INSTRUCTIONS + " ",
        user_content=c3.user_content,
        runtime=_rt(),
        schema=OUTPUT_SCHEMA,
    )
    assert a != b
    assert abs(len(a) - len(b)) >= 1


def test_adv_unicode_normalization_difference_is_explicit():
    # é as composed vs decomposed
    s = "café"
    if not bytes_nfc_nfd_differ(s):
        s = "e\u0301"  # e + combining acute
        s_nfc = unicodedata.normalize("NFC", s)
        assert hash_without_normalization(s) != hash_without_normalization(s_nfc)
    else:
        nfc = unicodedata.normalize("NFC", s)
        nfd = unicodedata.normalize("NFD", s)
        assert hash_without_normalization(nfc) != hash_without_normalization(nfd)


def test_adv_different_output_schema_key():
    test_output_schema_mismatch_fails()


def test_c2_instruction_identical_to_c3_system():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c2 = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, _ann(), _rt()
    )
    assert c2.system_text == c3.system_text == SHARED_SYSTEM_INSTRUCTIONS
    # Byte counts may differ (no forced pad)
    rec = verify_control_pair(
        c3, c2,
        require_byte_equality=False,
        require_instruction_identity=True,
        require_task_fact_identity=True,
    )
    assert rec.verdict is ControlVerdict.PASS


def test_instruction_identical_but_byte_different_disclosed():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(),
        accepted_relations=[{"subject_id": "thread_gamma_receipt",
                             "relation": "remains_open",
                             "object_id": "question_cold_start"}],
    )
    c2 = compile_condition_packet(
        ConditionId.C2_INSTRUCTION_IDENTICAL, _ann(), _rt()
    )
    assert c3.system_text == c2.system_text
    # With accepted relations, C3 is typically larger
    assert c3.byte_count != c2.byte_count or c3.input_sha256 != c2.input_sha256
