"""RUN 00.6D.1 — C1 construction-time byte-match enforcement.

Test-first amendment: C1 without a target must fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conditioned_kernel.control_contract import (
    ConditionId,
    ControlVerdict,
    PacketCompileError,
    RuntimeSettings,
    TaskDependencyAnnotation,
    build_matched_c3_c1_pair,
    compile_condition_packet,
    verify_control_pair,
)

FIXTURE = Path(__file__).parent / "fixtures" / "control_task_live_plumbing_01.json"


def _ann() -> TaskDependencyAnnotation:
    return TaskDependencyAnnotation.from_dict(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _rt() -> RuntimeSettings:
    return RuntimeSettings(model_tag="qwen2.5:0.5b", temperature=0.3, seed=42, num_ctx=2048)


# ---------------------------------------------------------------------------
# 1–7 Target required / invalid / unreachable
# ---------------------------------------------------------------------------


def test_c1_without_target_fails_closed():
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            # no target_complete_bytes
        )
    assert ei.value.reason_code == "C1_TARGET_REQUIRED"


def test_c1_target_zero_fails():
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=0,
        )
    assert ei.value.reason_code == "C1_TARGET_INVALID"


def test_c1_target_negative_fails():
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=-1,
        )
    assert ei.value.reason_code == "C1_TARGET_INVALID"


def test_c1_target_non_integer_fails():
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=1000.5,  # type: ignore[arg-type]
        )
    assert ei.value.reason_code == "C1_TARGET_INVALID"


def test_c1_target_bool_fails():
    # bool is a subclass of int in Python — must still be rejected
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=True,  # type: ignore[arg-type]
        )
    assert ei.value.reason_code == "C1_TARGET_INVALID"


def test_c1_unreachable_target_returns_no_packet():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    # Unreachable: smaller than unpadded C1 base
    with pytest.raises(PacketCompileError) as ei:
        compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=max(1, c3.byte_count // 10),
        )
    assert ei.value.reason_code in (
        "C1_TARGET_UNREACHABLE",
        "BYTE_BUDGET_OVERFLOW",
        "C1_BYTE_MATCH_FAILED",
    )


def test_c1_unreachable_does_not_return_mislabeled_object():
    try:
        pkt = compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=1,
        )
    except PacketCompileError:
        return
    # Must not succeed with a C1 label
    raise AssertionError(
        f"unexpected C1 packet returned: {pkt.condition_id} verified={pkt.byte_match_verified}"
    )


# ---------------------------------------------------------------------------
# 8–11 Valid direct C1 construction
# ---------------------------------------------------------------------------


def test_valid_c1_verifies_exact_byte_length():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(),
        accepted_relations=[
            {
                "subject_id": "thread_gamma_receipt",
                "relation": "remains_open",
                "object_id": "question_cold_start",
            }
        ],
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE,
        _ann(),
        _rt(),
        target_complete_bytes=c3.byte_count,
    )
    assert len(c1.complete_bytes) == c3.byte_count
    assert c1.actual_complete_bytes == c3.byte_count
    assert c1.target_complete_bytes == c3.byte_count


def test_valid_c1_records_match_metadata():
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE,
        _ann(),
        _rt(),
        target_complete_bytes=c3.byte_count,
    )
    assert c1.byte_match_verified is True
    assert c1.target_complete_bytes == c3.byte_count
    assert c1.actual_complete_bytes == c3.byte_count
    assert c1.paired_condition == ConditionId.C3_STATIC_CK.value
    assert c1.padding_bytes >= 0
    receipt = c1.to_receipt_dict()
    assert receipt["byte_match_verified"] is True
    assert receipt["target_complete_bytes"] == c3.byte_count
    assert receipt["actual_complete_bytes"] == c3.byte_count
    assert receipt["paired_condition"] == "C3_static_ck"
    assert receipt["padding_bytes_n"] == c1.padding_bytes
    assert receipt["input_sha256"] == c1.input_sha256
    assert receipt["scientific_completion"] is False
    assert receipt.get("headline_eligible") is not True


# ---------------------------------------------------------------------------
# 12–14 Pair builder + mutation + no unverified C1
# ---------------------------------------------------------------------------


def test_pair_builder_retains_independent_equality_verification():
    c3, c1, rec = build_matched_c3_c1_pair(_ann(), _rt())
    assert c3.byte_count == c1.byte_count
    assert c1.byte_match_verified is True
    assert rec.verdict is ControlVerdict.PASS


def test_one_byte_post_compilation_mutation_fails_verification():
    c3, c1, _ = build_matched_c3_c1_pair(_ann(), _rt())
    try:
        short = compile_condition_packet(
            ConditionId.C1_BUDGET_MATCHED_BARE,
            _ann(),
            _rt(),
            target_complete_bytes=c3.byte_count - 1,
        )
    except PacketCompileError as e:
        # Construction-time fail-closed is acceptable and preferred
        assert e.reason_code in (
            "C1_TARGET_UNREACHABLE",
            "C1_BYTE_MATCH_FAILED",
        )
        return
    rec = verify_control_pair(
        c3, short, require_byte_equality=True, require_instruction_identity=True
    )
    assert rec.verdict is ControlVerdict.FAIL


def test_no_unverified_packet_carries_c1_label():
    # Without target: exception, no object
    with pytest.raises(PacketCompileError):
        compile_condition_packet(ConditionId.C1_BUDGET_MATCHED_BARE, _ann(), _rt())
    # With valid target: must be verified
    c3 = compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )
    c1 = compile_condition_packet(
        ConditionId.C1_BUDGET_MATCHED_BARE,
        _ann(),
        _rt(),
        target_complete_bytes=c3.byte_count,
    )
    assert c1.condition_id is ConditionId.C1_BUDGET_MATCHED_BARE
    assert c1.byte_match_verified is True


# ---------------------------------------------------------------------------
# 15–17 Other conditions / dead code
# ---------------------------------------------------------------------------


def test_c0_c2_c3_do_not_require_c1_target():
    compile_condition_packet(ConditionId.C0_BARE, _ann(), _rt())
    compile_condition_packet(ConditionId.C2_INSTRUCTION_IDENTICAL, _ann(), _rt())
    compile_condition_packet(
        ConditionId.C3_STATIC_CK, _ann(), _rt(), accepted_relations=[]
    )


def test_apply_space_padding_symbol_removed():
    import conditioned_kernel.control_contract as cc

    assert not hasattr(cc, "apply_space_padding")
    assert hasattr(cc, "_pad_user_to_complete_target")


def test_one_authoritative_padding_path():
    import inspect
    import conditioned_kernel.control_contract as cc

    src = inspect.getsource(cc)
    # Only the private pad-to-target helper should implement padding search
    assert "_pad_user_to_complete_target" in src
    assert "def apply_space_padding" not in src
