"""RUN 00.9A — M0-v2 scientific contract static freeze tests. No models."""

from __future__ import annotations

import json
from pathlib import Path

from conditioned_kernel.m0_leakage_analysis import (
    analyze_condition_packets,
    gold_derivable_from_control,
    information_match_check,
    treatment_is_output_ready,
)
from conditioned_kernel.m0_preregistration_v2 import (
    PREREGISTRATION_SCHEMA,
    seal_template_hash,
)
from conditioned_kernel.m0_scientific_contract import (
    CONDITION_DEFINITIONS_V2,
    FALSIFICATION_TABLE,
    MIN_ELIGIBLE_TASKS,
    PRIMARY_ESTIMAND,
    PRIMARY_METRIC,
    PREDICTED_DIRECTION,
    ClaimLevel,
    DecisionOutcome,
    licensed_claim_for_outcome,
    max_claim_level,
    scientific_contract_freeze_dict,
    validate_scientific_contract_package,
)
from conditioned_kernel.m0_task_eligibility_v2 import (
    TASK_SELECTION_POLICY,
    evaluate_corpus_v2,
    evaluate_task_contract_v2,
    permitted_universe,
)

FIX = Path(__file__).parent / "fixtures" / "m0_v2_static_cases.json"


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


def test_gold_saturation_rejected():
    ents = ["e1", "e2"]
    rels = ["r"]
    # only non-self pairs: e1-r-e2, e2-r-e1
    gold = [
        {"subject_id": "e1", "relation": "r", "object_id": "e2"},
        {"subject_id": "e2", "relation": "r", "object_id": "e1"},
    ]
    t = _pass_task(
        entity_universe=ents,
        relation_universe=rels,
        expected_relations=gold,
        accepted_relation_set=gold,
        in_universe_distractors=[],
    )
    r = evaluate_task_contract_v2(t)
    assert "GOLD_SATURATES_PERMITTED_UNIVERSE" in r["exclusion_reasons"]


def test_empty_gold_rejected():
    t = _pass_task(expected_relations=[], accepted_relation_set=[])
    r = evaluate_task_contract_v2(t)
    assert "EMPTY_GOLD" in r["exclusion_reasons"]


def test_missing_distractors_rejected():
    t = _pass_task(
        entity_universe=["e1", "e2"],
        relation_universe=["r"],
        expected_relations=[
            {"subject_id": "e1", "relation": "r", "object_id": "e2"}
        ],
        accepted_relation_set=[
            {"subject_id": "e1", "relation": "r", "object_id": "e2"}
        ],
        in_universe_distractors=[],
    )
    # permitted has 2 triples, expected 1 → ratio 2 ok, distractors implicit 1 < 2
    r = evaluate_task_contract_v2(t)
    assert (
        "NO_INFORMATIONAL_DISTRACTORS" in r["exclusion_reasons"]
        or "MISSING_DISTRACTORS" in r["exclusion_reasons"]
        or "GOLD_SATURATES_PERMITTED_UNIVERSE" in r["exclusion_reasons"]
    )


def test_gold_visible_in_control_rejected():
    gold = [{"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}]
    packets = {
        "C1_budget_matched_bare": {
            "accepted_relations": gold,
            "facts": ["noise"],
        },
        "C3_static_ck": {"structured_state_not_output_schema": True, "representation": "structured_state_v1"},
    }
    # fix C3 so not also flagged
    packets["C3_static_ck"] = {
        "representation": "structured_state_v1",
        "state_graph": {"nodes": ["e1", "e2"], "edge_status": "accepted_rel_a"},
    }
    an = analyze_condition_packets(gold=gold, packets=packets)
    assert "GOLD_VISIBLE_IN_CONTROL" in an["exclusion_reasons"]


def test_gold_derivable_from_control_rejected():
    gold = [{"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}]
    assert gold_derivable_from_control(
        control_visible={"permitted": "only gold"},
        gold=gold,
        permitted_combinations=[["e1", "rel_a", "e2"]],
    )


def test_output_ready_treatment_leakage_rejected():
    gold = [{"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}]
    assert treatment_is_output_ready(
        treatment_visible={"continuity_assertions": gold},
        gold=gold,
    )
    an = analyze_condition_packets(
        gold=gold,
        packets={"C3_static_ck": {"continuity_assertions": gold}},
    )
    assert "GOLD_OUTPUT_READY_IN_TREATMENT" in an["exclusion_reasons"]


def test_valid_structured_state_treatment_accepted():
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
    an = analyze_condition_packets(gold=gold, packets=packets)
    assert "GOLD_OUTPUT_READY_IN_TREATMENT" not in an["exclusion_reasons"]
    assert "GOLD_VISIBLE_IN_CONTROL" not in an["exclusion_reasons"]


def test_condition_identity_leak_rejected():
    an = analyze_condition_packets(
        gold=[{"subject_id": "e1", "relation": "r", "object_id": "e2"}],
        packets={"C1_budget_matched_bare": {"condition": "C1_budget_matched_bare"}},
    )
    assert "CONDITION_IDENTITY_MODEL_VISIBLE" in an["exclusion_reasons"]


def test_information_matching_mismatch_rejected():
    rs = information_match_check(c3_candidate_count=4, c1_candidate_count=2)
    assert "INFORMATION_MATCHING_FAILED" in rs


def test_missing_state_hash_rejected():
    t = _pass_task()
    del t["state_hash"]
    del t["episode_a_state_hash"]
    r = evaluate_task_contract_v2(t)
    assert "MISSING_STATE_HASH" in r["exclusion_reasons"]


def test_state_gold_mismatch_rejected():
    t = _pass_task(
        accepted_relation_set=[
            {"subject_id": "e1", "relation": "rel_a", "object_id": "e2"}
        ],
        expected_relations=[
            {"subject_id": "e9", "relation": "rel_a", "object_id": "e2"}
        ],
    )
    r = evaluate_task_contract_v2(t)
    assert "STATE_GOLD_MISMATCH" in r["exclusion_reasons"]


def test_same_cell_id_different_state_rejected():
    t1 = _pass_task(task_id="t1", cell_id_template="cellA", state_hash="s1")
    t2 = _pass_task(task_id="t2", cell_id_template="cellA", state_hash="s2")
    corp = evaluate_corpus_v2(
        [t1, t2] + [_pass_task(task_id=f"t{i}") for i in range(3, 15)],
        negative_control_tasks=[{"task_id": "nc1"}],
    )
    assert "CELL_ID_MULTIPLE_STATES" in corp["corpus_reasons"]


def test_missing_negative_control_rejected():
    tasks = [_pass_task(task_id=f"t{i}") for i in range(MIN_ELIGIBLE_TASKS)]
    corp = evaluate_corpus_v2(tasks, negative_control_tasks=None)
    assert "MISSING_NEGATIVE_CONTROL" in corp["corpus_reasons"]


def test_failed_negative_control_invalidates_interpretation():
    # Design rule presence in falsification table
    assert any(
        "Negative-control" in f["outcome"] or "negative" in f["outcome"].lower()
        for f in FALSIFICATION_TABLE
    )
    assert any(
        f["classification"] == DecisionOutcome.PIPELINE_ARTIFACT.value
        for f in FALSIFICATION_TABLE
    )


def test_missing_estimand_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=None,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
    )
    assert "MISSING_ESTIMAND" in r


def test_multiple_primary_metrics_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        secondary_metrics=[PRIMARY_METRIC],
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
    )
    assert "MULTIPLE_PRIMARY_METRICS" in r


def test_missing_predicted_direction_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=None,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
    )
    assert "MISSING_PREDICTED_DIRECTION" in r


def test_missing_falsification_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement=None,
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
    )
    assert "MISSING_FALSIFICATION_STATEMENT" in r


def test_one_task_corpus_rejected():
    corp = evaluate_corpus_v2(
        [_pass_task()],
        min_eligible=MIN_ELIGIBLE_TASKS,
        negative_control_tasks=[{"task_id": "nc"}],
    )
    assert "ONE_TASK_CORPUS" in corp["corpus_reasons"]


def test_below_minimum_corpus_rejected():
    tasks = [_pass_task(task_id=f"t{i}") for i in range(3)]
    corp = evaluate_corpus_v2(
        tasks,
        min_eligible=MIN_ELIGIBLE_TASKS,
        negative_control_tasks=[{"task_id": "nc"}],
    )
    assert "CORPUS_BELOW_MINIMUM" in corp["corpus_reasons"]


def test_post_performance_selection_rejected():
    t = _pass_task(post_performance_selection=True)
    r = evaluate_task_contract_v2(t)
    assert "POST_PERFORMANCE_TASK_SELECTION" in r["exclusion_reasons"]


def test_missing_model_digest_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest=None,
        runtime_policy_present=True,
    )
    assert "MISSING_MODEL_DIGEST" in r


def test_missing_runtime_policy_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=False,
    )
    assert "MISSING_RUNTIME_POLICY" in r


def test_conflicting_c1_definition_rejected():
    r = validate_scientific_contract_package(
        primary_metric=PRIMARY_METRIC,
        estimand=PRIMARY_ESTIMAND,
        predicted_direction=PREDICTED_DIRECTION,
        falsification_statement="x",
        min_task_count=MIN_ELIGIBLE_TASKS,
        negative_controls_defined=True,
        model_digest="sha256:x",
        runtime_policy_present=True,
        c1_definition_conflicts=True,
    )
    assert "CONFLICTING_C1_DEFINITION" in r


def test_positive_claim_stays_within_d():
    assert max_claim_level() == ClaimLevel.D_CORPUS_M0.value
    pos = licensed_claim_for_outcome("positive_primary")
    assert "Conditioned Kernel works" not in pos
    assert "frozen M0-v2" in pos


def test_null_result_claim_explicit():
    null = licensed_claim_for_outcome("null_result")
    assert "No paired advantage" in null or "zero" in null.lower()


def test_negative_result_weakens_hypothesis():
    neg = licensed_claim_for_outcome("negative_result")
    assert "weakens" in neg.lower()


def test_leakage_after_freeze_invalidates():
    assert any("Leakage" in f["outcome"] for f in FALSIFICATION_TABLE)


def test_two_passing_toy_contracts():
    data = json.loads(FIX.read_text(encoding="utf-8"))
    for t in data["passing_toy_contracts"]:
        # pad state hashes to look real
        t = dict(t)
        t["state_hash"] = (t.get("state_hash") or "x") * 32
        t["episode_a_state_hash"] = t["state_hash"]
        r = evaluate_task_contract_v2(t)
        assert r["inclusion_verdict"] == "INCLUDED", (t["task_id"], r["exclusion_reasons"])


def test_primary_metric_and_estimand_frozen():
    d = scientific_contract_freeze_dict()
    assert d["primary_metric"] == "exact_relation_set_match"
    assert d["estimand"]["corpus_aggregate"] == "median_paired_difference"
    assert d["secondary_metric"] == "primary_score"


def test_condition_supersession_present():
    assert "C1_budget_matched_bare" in CONDITION_DEFINITIONS_V2
    assert "supersedes" in CONDITION_DEFINITIONS_V2["C1_budget_matched_bare"]


def test_preregistration_schema_template():
    t = seal_template_hash()
    assert t["schema"] == PREREGISTRATION_SCHEMA
    assert t["ratified"] is False
    assert t["candidate_manifest_sha256"] is None
    assert t["preregistration_sha256"]
    assert t["m0_authorized"] is False


def test_task_selection_independence_policy():
    assert TASK_SELECTION_POLICY["no_model_probing"] is True
    assert TASK_SELECTION_POLICY["no_post_performance_selection"] is True
    assert TASK_SELECTION_POLICY["min_eligible"] == MIN_ELIGIBLE_TASKS


def test_permitted_universe_nonsaturation_math():
    u = permitted_universe(["a", "b", "c"], ["r1", "r2"])
    # 3 entities * 2 rel * 2 others = 12
    assert len(u) == 12


def test_retired_candidate_never_ratify_marker():
    d = scientific_contract_freeze_dict()
    assert d["retired_candidate_id"] == "ck.m0.candidate.v1"
    assert d["m0_authorized"] is False
