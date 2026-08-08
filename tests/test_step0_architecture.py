"""Step 0 architecture: survival profile, think profiles, executable authority."""

from __future__ import annotations

from conditioned_kernel.edge import load_profile
from conditioned_kernel.executable_authority import (
    COMPILE_POLICY_VERSION,
    GATE_VERSION,
    apply_executable_authority,
    coverage_threshold_gate,
    extract_coverage_claim,
    finalize_authority_decision,
)
from conditioned_kernel.pipeline import run_turn


def test_macbook_survival_profile_runtime_tuple():
    p = load_profile("macbook_survival_9b")
    assert p.model == "sovereign-survival-9b-q4-ctx32k"
    assert p.base_model == "qwen3.5:9b-q4_K_M"
    assert p.quant == "Q4_K_M"
    assert p.digest_prefix.startswith("6488c96fa5fa")
    assert p.num_ctx == 32768
    assert p.think is False
    assert p.think_profile == "ordinary"
    rt = p.runtime_tuple()
    assert rt["model"] == p.model
    assert rt["quant"] == "Q4_K_M"
    assert rt["gate_version"] == GATE_VERSION
    assert rt["compile_policy"] == COMPILE_POLICY_VERSION


def test_think_profile_does_not_change_model():
    p = load_profile("macbook_survival_9b")
    d = p.with_think_profile("deliberate")
    assert d.model == p.model
    assert d.base_model == p.base_model
    assert d.quant == p.quant
    assert d.digest_prefix == p.digest_prefix
    assert d.num_ctx == p.num_ctx
    assert d.think is True
    assert d.think_profile == "deliberate"
    o = d.with_think_profile("ordinary")
    assert o.think is False
    assert o.model == p.model


def test_coverage_gate_fail_outranks_model_pass():
    gate = coverage_threshold_gate(coverage=0.78, threshold=0.80)
    assert gate["result"] == "FAIL"
    claim = extract_coverage_claim(
        "RESULT: PASS\nCLAUSE: retry overrides the initial miss so coverage is fine."
    )
    assert claim == "PASS"

    packet = {
        "compile_policy": COMPILE_POLICY_VERSION,
        "gate_version": GATE_VERSION,
        "executable_authority": {
            "coverage": {
                "coverage": 0.78,
                "threshold": 0.80,
                "exclusions_documented": True,
            }
        },
    }
    candidate = {
        "answer": "RESULT: PASS\nThe retry means we can treat coverage as meeting threshold."
    }
    receipt = {
        "decision": "accept",
        "violations": [],
        "receipt_id": "test",
    }
    receipt = apply_executable_authority(receipt, candidate, packet)
    assert receipt.get("_force_reject_for_authority") is True
    assert "executable_authority_override" in receipt["violations"]
    receipt["decision"] = "accept"  # simulate assess still accepting
    receipt = finalize_authority_decision(receipt)
    assert receipt["decision"] == "reject"
    assert receipt["accepted_contradiction"] is False
    assert receipt["system_state"] == "FAIL"
    assert receipt["kernel_final"] == "FAIL"


def test_coverage_gate_agree_fail_not_forced():
    packet = {
        "executable_authority": {"coverage": {"coverage": 0.78, "threshold": 0.80}}
    }
    candidate = {"answer": "RESULT: FAIL\nClause: coverage 0.78 < 0.80"}
    receipt = {"decision": "accept", "violations": []}
    receipt = apply_executable_authority(receipt, candidate, packet)
    assert not receipt.get("_force_reject_for_authority")
    receipt = finalize_authority_decision(receipt)
    assert receipt["decision"] == "accept"


def test_pipeline_stamps_op_and_blocks_authority_override(tmp_path):
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()
    from conditioned_kernel.state import SubstrateState

    st = SubstrateState.load(state_dir=state_dir, logs_dir=logs_dir)
    st.current["executable_authority"] = {
        "coverage": {"coverage": 0.78, "threshold": 0.80, "exclusions_documented": True}
    }
    st.current["goal"] = "demonstrate conditioned-kernel substrate gain"
    st.save_current()

    dry = (
        "{"
        '"answer": "RESULT: PASS. CLAUSE FIRED: coverage >= 0.80 '
        '(retry overrides initial timeout). '
        "The goal is to demonstrate conditioned-kernel substrate gain.\","
        '"evidence_used": [],'
        '"next_state": {},'
        '"self_report": {"goal_referenced": true}'
        "}"
    )
    result = run_turn(
        "Score the experiment under the frozen rule.",
        profile_id="macbook_survival_9b",
        state_dir=state_dir,
        logs_dir=logs_dir,
        dry_candidate_text=dry,
        acceptance_mode="companion",
    )
    op = result.receipt.get("operating_point") or {}
    assert op.get("profile_id") == "macbook_survival_9b"
    assert op.get("quant") == "Q4_K_M"
    assert op.get("num_ctx") == 32768
    assert result.receipt.get("gate_version") == GATE_VERSION
    assert result.receipt.get("compile_policy") == COMPILE_POLICY_VERSION
    gates = result.receipt.get("executable_gates") or []
    assert gates, "coverage gate should have run"
    assert gates[0]["result"] == "FAIL"
    assert gates[0].get("model_claim") == "PASS"
    assert result.decision != "accept"
    assert result.receipt.get("accepted_contradiction") is False
    assert result.receipt.get("system_state") == "FAIL"
