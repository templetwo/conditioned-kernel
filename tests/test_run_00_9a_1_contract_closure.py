"""RUN 00.9A.1 — fail-closed leakage and statistical contract closure.

No models. No corpus authorship. No Ollama.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from conditioned_kernel.m0_leakage_analysis import (
    LeakageAnalysisError,
    analyze_condition_packets,
    gold_derivable_from_control,
    require_permitted_combinations,
    treatment_is_output_ready,
)
from conditioned_kernel.m0_preregistration_v2 import (
    PREREGISTRATION_SCHEMA,
    seal_template_hash,
)
from conditioned_kernel.m0_scientific_contract import (
    DELTA_M0,
    MIN_ELIGIBLE_TASKS,
    N_CANDIDATE,
    PRIMARY_ESTIMAND,
    PRIMARY_METRIC,
    PRIMARY_NEGATIVE_CONTROL,
    SECONDARY_INTEGRITY_CONTROL,
    SECONDARY_METRIC,
    ClaimLevel,
    DecisionOutcome,
    classify_mean_d_c3,
    counterbalanced_condition_order,
    evaluate_decision,
    licensed_claim_for_outcome,
    max_claim_level,
    mean_paired_difference,
    median_paired_difference,
    scientific_contract_freeze_dict,
    scientific_manifest_allowed,
    validate_order_counterbalance,
    validate_scientific_contract_package,
)
from conditioned_kernel.m0_task_eligibility_v2 import (
    TASK_SELECTION_POLICY,
    evaluate_corpus_v2,
    evaluate_task_contract_v2,
)

REPO = Path(__file__).resolve().parents[1]
C1_PACKET = (
    REPO
    / "experiments/runs/commissioning_00_8b/cells/C1_budget_matched_bare/packet_body.json"
)
FIX = Path(__file__).parent / "fixtures" / "m0_v2_static_cases.json"

REAL_GOLD = [
    {
        "subject_id": "thread_gamma_receipt",
        "relation": "references",
        "object_id": "question_cold_start",
    },
    {
        "subject_id": "thread_gamma_receipt",
        "relation": "remains_open",
        "object_id": "question_cold_start",
    },
]
# Saturated permitted universe for the real v1 task (= gold only)
REAL_PERMITTED = [
    [g["subject_id"], g["relation"], g["object_id"]] for g in REAL_GOLD
]


def _pass_task(**overrides):
    base = {
        "task_id": "t_ok",
        "contract_version": "ck.m0_task_contract.v2",
        "entity_universe": ["e1", "e2", "e3", "e4"],
        "relation_universe": ["rel_a", "rel_b", "rel_c"],
        "expected_relation_semantics": "all_required",
        "output_schema_id": "continuity_assertions_v1",
        "state_hash": "s1",
        "episode_a_state_hash": "s1",
        "episode_b_query": "Which relations remain accepted?",
        "accepted_relation_set": [
            {"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}
        ],
        "expected_relations": [
            {"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}
        ],
        "in_universe_distractors": [
            {"subject_id": "e1", "relation": "rel_b", "object_id": "e2"},
            {"subject_id": "e2", "relation": "rel_a", "object_id": "e3"},
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fail-open reproduction + fail-closed API
# ---------------------------------------------------------------------------

def test_permitted_combinations_cannot_be_omitted():
    sig = inspect.signature(analyze_condition_packets)
    assert "permitted_combinations" in sig.parameters
    p = sig.parameters["permitted_combinations"]
    assert p.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        analyze_condition_packets(  # type: ignore[call-arg]
            gold=REAL_GOLD,
            packets={"C1_budget_matched_bare": {}},
        )


def test_permitted_combinations_none_fails_closed():
    with pytest.raises(LeakageAnalysisError) as ei:
        require_permitted_combinations(None)
    assert ei.value.reason_code == "PERMITTED_COMBINATIONS_REQUIRED"

    with pytest.raises(LeakageAnalysisError) as ei2:
        gold_derivable_from_control(
            control_visible={"x": 1},
            gold=REAL_GOLD,
            permitted_combinations=None,  # type: ignore[arg-type]
        )
    assert ei2.value.reason_code == "PERMITTED_COMBINATIONS_REQUIRED"

    an = analyze_condition_packets(
        gold=REAL_GOLD,
        packets={"C1_budget_matched_bare": {"noise": True}},
        permitted_combinations=None,  # type: ignore[arg-type]
    )
    assert an["analysis_complete"] is False
    assert an["leakage_detected"] is not False
    assert an["leakage_detected"] is True
    assert "PERMITTED_COMBINATIONS_REQUIRED" in an["exclusion_reasons"]
    assert "LEAKAGE_ANALYSIS_INCOMPLETE" in an["exclusion_reasons"]


def test_empty_permitted_universe_fails_closed():
    with pytest.raises(LeakageAnalysisError) as ei:
        require_permitted_combinations([])
    assert ei.value.reason_code == "PERMITTED_COMBINATIONS_EMPTY"
    an = analyze_condition_packets(
        gold=REAL_GOLD,
        packets={"C1_budget_matched_bare": {"noise": True}},
        permitted_combinations=[],
    )
    assert an["leakage_detected"] is True
    assert an["analysis_complete"] is False
    assert "PERMITTED_COMBINATIONS_EMPTY" in an["exclusion_reasons"]


def test_real_008b_c1_packet_still_yields_gold_derivable():
    assert C1_PACKET.is_file(), "commissioning C1 packet must be present"
    c1 = json.loads(C1_PACKET.read_text(encoding="utf-8"))
    assert gold_derivable_from_control(
        control_visible=c1,
        gold=REAL_GOLD,
        permitted_combinations=REAL_PERMITTED,
    )
    an = analyze_condition_packets(
        gold=REAL_GOLD,
        packets={"C1_budget_matched_bare": c1},
        permitted_combinations=REAL_PERMITTED,
    )
    assert "GOLD_DERIVABLE_FROM_CONTROL" in an["exclusion_reasons"]
    assert an["leakage_detected"] is True


def test_missing_leakage_inputs_never_return_clean_false():
    # incomplete result must not claim clean
    an = analyze_condition_packets(
        gold=REAL_GOLD,
        packets={"C1_budget_matched_bare": {}},
        permitted_combinations=None,  # type: ignore[arg-type]
    )
    assert an.get("leakage_detected") is not False
    assert an["task_eligible"] is False


# ---------------------------------------------------------------------------
# Metric / estimand / delta
# ---------------------------------------------------------------------------

def test_exact_relation_set_match_sole_primary():
    d = scientific_contract_freeze_dict()
    assert d["primary_metric"] == "exact_relation_set_match"
    assert PRIMARY_METRIC == "exact_relation_set_match"


def test_primary_score_is_secondary_only():
    d = scientific_contract_freeze_dict()
    assert d["secondary_metric"] == "primary_score"
    assert SECONDARY_METRIC == "primary_score"
    assert d["primary_metric"] != SECONDARY_METRIC


def test_primary_aggregate_is_mean_paired_d():
    assert PRIMARY_ESTIMAND == "mean_paired_difference"
    d = scientific_contract_freeze_dict()
    assert d["estimand"]["corpus_aggregate"] == "mean_paired_difference"


def test_median_not_accepted_as_primary_aggregate():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand="median_paired_difference",
        predicted_direction="C3_greater_than_C1",
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
        ordering_seed=1,
    )
    assert "MEDIAN_NOT_PRIMARY_ESTIMAND" in r or "ESTIMAND_NOT_FROZEN_CHOICE" in r


def test_median_discards_net_positive_configuration():
    # 4 C3 wins, 1 C1 win, 7 ties → mean > 0 but median == 0
    d_vals = [1, 1, 1, 1, -1, 0, 0, 0, 0, 0, 0, 0]
    assert len(d_vals) == 12
    assert mean_paired_difference(d_vals) == pytest.approx(3 / 12)
    assert median_paired_difference(d_vals) == 0.0
    # median alone would call this null; mean captures net wins


def test_delta_m0_is_exactly_quarter():
    assert DELTA_M0 == 0.25
    assert scientific_contract_freeze_dict()["delta_m0"] == 0.25


def test_one_net_win_of_twelve_inconclusive():
    # old >0 rule would support; new threshold does not
    mean_d = 1 / 12
    assert mean_d > 0
    assert mean_d < DELTA_M0
    assert classify_mean_d_c3(mean_d) == DecisionOutcome.INCONCLUSIVE.value


def test_three_net_wins_of_twelve_reach_continuation_threshold():
    mean_d = 3 / 12
    assert mean_d == DELTA_M0
    assert classify_mean_d_c3(mean_d) == DecisionOutcome.SUPPORT_CONTINUATION.value


def test_mean_d_le_neg_delta_weakens():
    assert classify_mean_d_c3(-0.25) == DecisionOutcome.WEAKEN_HYPOTHESIS.value
    assert classify_mean_d_c3(-0.5) == DecisionOutcome.WEAKEN_HYPOTHESIS.value


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------

def test_scrambled_state_is_primary_negative_control():
    assert PRIMARY_NEGATIVE_CONTROL == "scrambled_state"
    d = scientific_contract_freeze_dict()
    assert d["primary_negative_control"] == "scrambled_state"
    assert SECONDARY_INTEGRITY_CONTROL == "aa_serialization"


def test_mean_d_nc_ge_delta_invalidates():
    res = evaluate_decision(
        mean_d_c3=0.5,
        mean_d_nc=0.25,
        aa_discrepancy_count=0,
        primary_pair_coverage=1.0,
        negative_control_coverage=1.0,
    )
    assert res["continuation_licensed"] is False
    assert res["outcome"] == DecisionOutcome.PIPELINE_ARTIFACT.value
    assert "NEGATIVE_CONTROL_GAIN_AT_THRESHOLD" in res["reasons"]


def test_mean_d_nc_ge_mean_d_c3_invalidates():
    res = evaluate_decision(
        mean_d_c3=0.3,
        mean_d_nc=0.3,
        aa_discrepancy_count=0,
        primary_pair_coverage=1.0,
        negative_control_coverage=1.0,
    )
    assert res["continuation_licensed"] is False
    assert "NEGATIVE_CONTROL_GAIN_MATCHES_OR_EXCEEDS_C3" in res["reasons"]


def test_any_aa_discrepancy_invalidates():
    res = evaluate_decision(
        mean_d_c3=0.5,
        mean_d_nc=0.0,
        aa_discrepancy_count=1,
        primary_pair_coverage=1.0,
        negative_control_coverage=1.0,
    )
    assert res["continuation_licensed"] is False
    assert "AA_DISCREPANCY" in res["reasons"]


def test_continuation_requires_all_gates():
    res = evaluate_decision(
        mean_d_c3=0.25,
        mean_d_nc=0.0,
        aa_discrepancy_count=0,
        primary_pair_coverage=1.0,
        negative_control_coverage=1.0,
        validity_gates_pass=True,
        runtime_qualified=True,
    )
    assert res["continuation_licensed"] is True
    assert res["outcome"] == DecisionOutcome.SUPPORT_CONTINUATION.value


# ---------------------------------------------------------------------------
# C3 representation invariant
# ---------------------------------------------------------------------------

def test_c3_output_schema_equivalent_state_rejected():
    gold = [{"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}]
    assert treatment_is_output_ready(
        treatment_visible={"continuity_assertions": gold},
        gold=gold,
    )
    an = analyze_condition_packets(
        gold=gold,
        packets={"C3_static_ck": {"continuity_assertions": gold}},
        permitted_combinations=[
            ["e1", "rel_a", "e2"],
            ["e1", "rel_b", "e2"],
        ],
    )
    assert "GOLD_OUTPUT_READY_IN_TREATMENT" in an["exclusion_reasons"]


def test_valid_non_output_ready_structured_state_passes():
    gold = [{"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}]
    packets = {
        "C0_bare": {"query": "what remains accepted?"},
        "C1_budget_matched_bare": {
            "candidates": ["e1-rel_a-e2", "e1-rel_b-e2"],
            "status_symbols": ["?", "?"],
        },
        "C3_static_ck": {
            "representation": "structured_state_v1",
            "state_graph": {"accepted": ["e1|rel_a|e2"]},
        },
    }
    an = analyze_condition_packets(
        gold=gold,
        packets=packets,
        permitted_combinations=[
            ["e1", "rel_a", "e2"],
            ["e1", "rel_b", "e2"],
            ["e2", "rel_a", "e1"],
        ],
    )
    assert "GOLD_OUTPUT_READY_IN_TREATMENT" not in an["exclusion_reasons"]
    assert "GOLD_VISIBLE_IN_CONTROL" not in an["exclusion_reasons"]
    assert an["analysis_complete"] is True


# ---------------------------------------------------------------------------
# Corpus counts / inclusion
# ---------------------------------------------------------------------------

def test_n_candidate_is_24():
    assert N_CANDIDATE == 24
    assert scientific_contract_freeze_dict()["n_candidate"] == 24
    assert TASK_SELECTION_POLICY["n_candidate"] == 24


def test_n_min_eligible_is_12():
    assert MIN_ELIGIBLE_TASKS == 12


def test_all_statically_eligible_tasks_included():
    tasks = [_pass_task(task_id=f"t{i}") for i in range(12)]
    corp = evaluate_corpus_v2(
        tasks,
        negative_control_tasks=[{"task_id": "nc1"}],
    )
    assert corp["all_eligible_included"] is True
    assert corp["n_eligible"] == 12


def test_eligible_below_12_blocks_manifest():
    tasks = [_pass_task(task_id=f"t{i}") for i in range(5)]
    corp = evaluate_corpus_v2(
        tasks,
        negative_control_tasks=[{"task_id": "nc1"}],
    )
    assert "CORPUS_BELOW_MINIMUM" in corp["corpus_reasons"]
    assert corp["scientific_manifest_allowed"] is False
    m = scientific_manifest_allowed(n_eligible=5)
    assert m["allowed"] is False


# ---------------------------------------------------------------------------
# Replicate / order / runtime
# ---------------------------------------------------------------------------

def test_replicate_count_one_no_replication_claim():
    d = scientific_contract_freeze_dict()
    assert d["replicate_count"] == 1
    assert d["retries"] == 0
    assert d["no_independent_replication_claim"] is True


def test_condition_order_counterbalanced_and_seed_pinned():
    tasks = [f"t{i:02d}" for i in range(12)]
    plan_a = counterbalanced_condition_order(tasks, seed=42)
    plan_b = counterbalanced_condition_order(tasks, seed=42)
    assert plan_a == plan_b  # seed-pinned
    assert validate_order_counterbalance(plan_a) == []
    c1_first = sum(1 for p in plan_a if p["c1_before_c3"])
    assert c1_first == 6
    # scrambled + A/A in each block
    for p in plan_a:
        assert "scrambled_state" in p["condition_block"]
        assert "aa_serialization" in p["condition_block"]


def test_unqualified_runtime_blocks_authorization():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction="C3_greater_than_C1",
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
        runtime_qualified=False,
        ordering_seed=7,
    )
    assert "RUNTIME_CONTRACT_UNQUALIFIED" in r
    res = evaluate_decision(
        mean_d_c3=0.5,
        mean_d_nc=0.0,
        aa_discrepancy_count=0,
        primary_pair_coverage=1.0,
        negative_control_coverage=1.0,
        runtime_qualified=False,
    )
    assert res["continuation_licensed"] is False


# ---------------------------------------------------------------------------
# Legacy / toys / claims
# ---------------------------------------------------------------------------

def test_existing_v1_saturated_task_remains_rejected():
    # Reproduce original saturation class: expected == full non-self permitted
    # universe (2 entities × 1 relation → 2 triples).
    gold_full = [
        {"subject_id": "a", "relation": "r", "object_id": "b"},
        {"subject_id": "b", "relation": "r", "object_id": "a"},
    ]
    t2 = _pass_task(
        task_id="live_plumbing_01_m0_v1_saturated_shape",
        entity_universe=["a", "b"],
        relation_universe=["r"],
        expected_relations=gold_full,
        accepted_relation_set=gold_full,
        in_universe_distractors=[],
    )
    r = evaluate_task_contract_v2(t2)
    assert "GOLD_SATURATES_PERMITTED_UNIVERSE" in r["exclusion_reasons"]


def test_both_passing_toy_fixtures_still_pass():
    data = json.loads(FIX.read_text(encoding="utf-8"))
    for t in data["passing_toy_contracts"]:
        t = dict(t)
        t["state_hash"] = (t.get("state_hash") or "x") * 32
        t["episode_a_state_hash"] = t["state_hash"]
        r = evaluate_task_contract_v2(t)
        assert r["inclusion_verdict"] == "INCLUDED", (t["task_id"], r["exclusion_reasons"])
        # Stricter leakage API with full permitted universe still allows clean C3
        gold = t["expected_relations"]
        ents = t["entity_universe"]
        rels = t["relation_universe"]
        perm = [
            [s, r, o]
            for s in ents
            for r in rels
            for o in ents
            if s != o
        ]
        an = analyze_condition_packets(
            gold=gold,
            packets={
                "C1_budget_matched_bare": {
                    "candidates": [f"{x[0]}-{x[1]}-{x[2]}" for x in perm[:4]],
                    "status_symbols": ["?"] * min(4, len(perm)),
                },
                "C3_static_ck": {
                    "representation": "structured_state_v1",
                    "state_graph": {"nodes": ents, "edges": "encoded"},
                },
            },
            permitted_combinations=perm,
        )
        assert an["analysis_complete"] is True
        assert "GOLD_OUTPUT_READY_IN_TREATMENT" not in an["exclusion_reasons"]


def test_positive_claim_uses_mean_not_median():
    pos = licensed_claim_for_outcome("positive_primary")
    assert "mean paired exact-set-match" in pos
    assert "median" not in pos.lower()
    assert "Conditioned Kernel works" not in pos
    assert "continuation" in pos.lower() or "threshold" in pos.lower()
    assert max_claim_level() == ClaimLevel.D_CORPUS_M0.value


def test_preregistration_template_updated():
    t = seal_template_hash()
    assert t["schema"] == PREREGISTRATION_SCHEMA
    assert t["primary_estimand"] == "mean_paired_difference"
    assert t["delta_m0"] == 0.25
    assert t["n_candidate"] == 24
    assert t["negative_control_rule"]["primary"] == "scrambled_state"
    assert t["ratified"] is False
    assert t["m0_authorized"] is False


def test_no_model_invoked_marker():
    # Static-only suite: no ollama import side effects required
    import conditioned_kernel.m0_leakage_analysis as la
    import conditioned_kernel.m0_scientific_contract as sc

    src = Path(la.__file__).read_text(encoding="utf-8") + Path(sc.__file__).read_text(
        encoding="utf-8"
    )
    assert "ollama" not in src.lower() or "no model" in src.lower()
