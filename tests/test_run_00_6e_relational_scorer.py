"""RUN 00.6E — closed-set relational scorer.

Offline, fixture-driven, test-first intent. No model invocation.
Scientific status: scorer_validation_only. headline_eligible=false.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from conditioned_kernel.relational_scorer import (
    HEADLINE_INELIGIBLE_REASON,
    SCIENTIFIC_STATUS,
    SCORER_SCHEMA_VERSION,
    RelationClass,
    RelationTriple,
    RelationalGold,
    ScoringStatus,
    TaskContractError,
    classify_proposal,
    primary_score_formula,
    score_cell,
    score_planned_cells,
    score_record_canonical_bytes,
    score_record_hash,
    triples_hash,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "relational_scorer_cases.json"
REPO_COMMIT = "02a002773fb17e4939abca8612a4038c74a1d163"


@pytest.fixture(scope="module")
def fx() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _gold(fx: dict[str, Any], key: str) -> dict[str, Any]:
    return copy.deepcopy(fx[key])


def _resolve_gold(fx: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    if "gold_inline" in case:
        return copy.deepcopy(case["gold_inline"])
    return _gold(fx, case["gold"])


def _score(
    fx: dict[str, Any],
    case: dict[str, Any],
    *,
    condition_id: str = "C3",
) -> dict[str, Any]:
    gold = _resolve_gold(fx, case)
    return score_cell(
        task_id=str(gold["task_id"]),
        condition_id=condition_id,
        gold=gold,
        proposed_assertions=case.get("proposed_assertions"),
        inference_status=str(case.get("inference_status") or "completed"),
        model_provenance={"model_tag": "fixture-none", "runtime": "offline"},
        repo_commit=REPO_COMMIT,
        malformed=bool(case.get("malformed", False)),
    )


def _case(fx: dict[str, Any], name: str) -> dict[str, Any]:
    for c in fx["cases"]:
        if c["name"] == name:
            return c
    raise KeyError(name)


# ---------------------------------------------------------------------------
# Critical test-first cases (shotgun / wrong-rel / reverse / extra / timeout)
# ---------------------------------------------------------------------------


def test_01_exact_triple_earns_one_true_positive(fx):
    rec = _score(fx, _case(fx, "perfect_one_relation"))
    assert rec["scoring_status"] == ScoringStatus.SCORED.value
    assert rec["true_positive_n"] == 1
    assert rec["false_negative_n"] == 0
    assert rec["primary_score"] == 1.0
    assert rec["exact_relation_set_match"] is True


def test_02_identifier_overlap_alone_no_true_positive(fx):
    """Shotgun of all identifiers into false triples → zero TP."""
    rec = _score(fx, _case(fx, "shotgun_all_identifiers_false_triples"))
    assert rec["true_positive_n"] == 0
    assert rec["false_negative_n"] == 1
    assert rec["primary_score"] == 0.0
    assert rec["exact_relation_set_match"] is False
    assert rec["unsupported_assertion_n"] + rec["wrong_relation_n"] > 0


def test_03_wrong_relation_not_scored_correct(fx):
    rec = _score(fx, _case(fx, "wrong_relation_correct_subject_object"))
    assert rec["true_positive_n"] == 0
    assert rec["wrong_relation_n"] == 1
    assert rec["false_negative_n"] == 1
    assert rec["primary_score"] == 0.0
    assert rec["exact_relation_set_match"] is False


def test_04_reversed_direction_not_scored_correct(fx):
    rec = _score(fx, _case(fx, "reversed_subject_object"))
    assert rec["true_positive_n"] == 0
    assert rec["reversed_direction_n"] == 1
    assert rec["false_negative_n"] == 1
    assert rec["primary_score"] == 0.0


def test_05_missing_expected_is_false_negative(fx):
    rec = _score(fx, _case(fx, "one_correct_one_missing"))
    assert rec["true_positive_n"] == 1
    assert rec["false_negative_n"] == 2
    assert rec["expected_n"] == 3
    assert rec["exact_relation_set_match"] is False


def test_06_unsupported_assertion_counted(fx):
    rec = _score(fx, _case(fx, "unsupported_in_universe"))
    assert rec["unsupported_assertion_n"] == 1
    assert rec["true_positive_n"] == 0
    assert rec["false_negative_n"] == 1


def test_07_out_of_universe_explicitly_counted(fx):
    for name in (
        "out_of_universe_subject",
        "out_of_universe_object",
        "out_of_universe_relation",
    ):
        rec = _score(fx, _case(fx, name))
        assert rec["out_of_universe_assertion_n"] == 1, name
        assert rec["true_positive_n"] == 0, name
        assert rec["false_negative_n"] == 1, name


def test_08_duplicate_correct_no_extra_credit(fx):
    clean = _score(fx, _case(fx, "perfect_one_relation"))
    dup = _score(fx, _case(fx, "duplicate_only_correct"))
    assert dup["true_positive_n"] == 1
    assert dup["duplicate_assertion_n"] == 2
    assert dup["primary_score"] == clean["primary_score"] == 1.0
    assert dup["exact_relation_set_match"] is False
    assert clean["exact_relation_set_match"] is True


def test_09_duplicate_incorrect_no_extra_credit(fx):
    once = _score(fx, _case(fx, "wrong_relation_correct_subject_object"))
    dups = _score(fx, _case(fx, "duplicate_only_incorrect"))
    assert dups["wrong_relation_n"] == 1
    assert dups["duplicate_assertion_n"] == 1
    assert dups["true_positive_n"] == 0
    assert dups["primary_score"] == once["primary_score"] == 0.0


def test_10_proposal_ordering_does_not_change_results(fx):
    a = _score(fx, _case(fx, "same_proposal_order_a"))
    b = _score(fx, _case(fx, "same_proposal_order_b"))
    # Canonical score fields independent of proposal order
    keys = (
        "primary_score",
        "true_positive_n",
        "false_negative_n",
        "exact_relation_set_match",
        "expected_relation_hash",
        "proposed_assertion_hash",
        "precision",
        "recall",
        "f1",
    )
    for k in keys:
        assert a[k] == b[k], k
    assert a["proposed_assertion_hash"] == b["proposed_assertion_hash"]
    assert score_record_hash(
        {k: a[k] for k in keys}
    ) == score_record_hash({k: b[k] for k in keys})


def test_11_expected_ordering_does_not_change_results(fx):
    g1 = _gold(fx, "multi_gold")
    g2 = _gold(fx, "multi_gold")
    g2["expected_relations"] = list(reversed(g2["expected_relations"]))
    props = [
        {"subject_id": "ent_A", "relation": "remains_open", "object_id": "ent_B"},
        {"subject_id": "ent_B", "relation": "depends_on", "object_id": "ent_C"},
    ]
    r1 = score_cell(
        task_id=g1["task_id"],
        condition_id="C3",
        gold=g1,
        proposed_assertions=props,
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    r2 = score_cell(
        task_id=g2["task_id"],
        condition_id="C3",
        gold=g2,
        proposed_assertions=props,
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert r1["expected_relation_hash"] == r2["expected_relation_hash"]
    assert r1["primary_score"] == r2["primary_score"]
    assert r1["true_positive_n"] == r2["true_positive_n"]
    assert r1["false_negative_n"] == r2["false_negative_n"]


def test_12_adding_non_true_assertion_never_improves_primary_score(fx):
    base = _score(fx, _case(fx, "perfect_one_relation"))
    extra = _score(fx, _case(fx, "exact_plus_unsupported"))
    assert extra["primary_score"] is not None
    assert base["primary_score"] is not None
    assert extra["primary_score"] <= base["primary_score"]
    assert extra["primary_score"] < base["primary_score"]


def test_13_correct_plus_unsupported_below_clean(fx):
    clean = _score(fx, _case(fx, "perfect_one_relation"))
    dirty = _score(fx, _case(fx, "exact_plus_unsupported"))
    assert dirty["primary_score"] < clean["primary_score"]
    assert dirty["exact_relation_set_match"] is False


def test_14_shotgun_below_minimal_correct(fx):
    clean = _score(fx, _case(fx, "perfect_one_relation"))
    shotgun = _score(fx, _case(fx, "shotgun_all_identifiers_false_triples"))
    assert shotgun["primary_score"] < clean["primary_score"]
    assert shotgun["primary_score"] == 0.0


def test_15_shotgun_cannot_exact_match(fx):
    shotgun = _score(fx, _case(fx, "shotgun_all_identifiers_false_triples"))
    assert shotgun["exact_relation_set_match"] is False
    plus_extra = _score(fx, _case(fx, "exact_plus_unsupported"))
    assert plus_extra["exact_relation_set_match"] is False


def test_16_empty_assertion_list_scored_deterministically(fx):
    rec = _score(fx, _case(fx, "empty_assertion_list"))
    assert rec["scoring_status"] == ScoringStatus.SCORED.value
    assert rec["true_positive_n"] == 0
    assert rec["false_negative_n"] == 1
    assert rec["primary_score"] == 0.0
    assert rec["proposed_raw_n"] == 0
    assert rec["proposed_unique_n"] == 0
    h1 = score_record_hash(rec)
    h2 = score_record_hash(_score(fx, _case(fx, "empty_assertion_list")))
    assert h1 == h2


def test_17_malformed_assertions_null_primary_score(fx):
    rec = _score(fx, _case(fx, "malformed_json_proxy"))
    assert rec["scoring_status"] == ScoringStatus.MALFORMED_ASSERTIONS.value
    assert rec["primary_score"] is None
    assert rec["exact_relation_set_match"] is False


def test_18_timeout_null_primary_score(fx):
    rec = _score(fx, _case(fx, "timeout"))
    assert rec["scoring_status"] == ScoringStatus.TIMEOUT.value
    assert rec["primary_score"] is None
    assert rec["invalid_reason"] is not None
    # Remains visible: expected_n retained for coverage
    assert rec["expected_n"] == 1
    assert rec["false_negative_n"] == 1


def test_19_transport_error_null_primary_score(fx):
    rec = _score(fx, _case(fx, "transport_error"))
    assert rec["scoring_status"] == ScoringStatus.TRANSPORT_ERROR.value
    assert rec["primary_score"] is None


def test_20_no_final_response_null_primary_score(fx):
    rec = _score(fx, _case(fx, "no_final_response"))
    assert rec["scoring_status"] == ScoringStatus.NO_FINAL_RESPONSE.value
    assert rec["primary_score"] is None


def test_21_failed_inference_records_remain_in_coverage(fx):
    cells = [
        {
            "task_id": "rel_task_01",
            "condition_id": "C0",
            "gold": _gold(fx, "base_gold"),
            "inference_status": "timeout",
            "proposed_assertions": None,
            "repo_commit": REPO_COMMIT,
        },
        {
            "task_id": "rel_task_01",
            "condition_id": "C1",
            "gold": _gold(fx, "base_gold"),
            "inference_status": "transport_error",
            "proposed_assertions": None,
            "repo_commit": REPO_COMMIT,
        },
        {
            "task_id": "rel_task_01",
            "condition_id": "C3",
            "gold": _gold(fx, "base_gold"),
            "inference_status": "completed",
            "proposed_assertions": [
                {
                    "subject_id": "ent_A",
                    "relation": "remains_open",
                    "object_id": "ent_B",
                }
            ],
            "repo_commit": REPO_COMMIT,
        },
    ]
    records = score_planned_cells(cells)
    assert len(records) == 3
    assert records[0]["scoring_status"] == ScoringStatus.TIMEOUT.value
    assert records[1]["scoring_status"] == ScoringStatus.TRANSPORT_ERROR.value
    assert records[2]["scoring_status"] == ScoringStatus.SCORED.value
    assert records[0]["primary_score"] is None
    assert records[2]["primary_score"] == 1.0


def test_22_every_planned_cell_one_terminal_record(fx):
    cells = []
    for i, case in enumerate(fx["cases"]):
        if "gold_inline" in case:
            # Contract-error cases still produce a terminal record
            gold = case["gold_inline"]
        else:
            gold = _gold(fx, case["gold"])
        cells.append(
            {
                "task_id": gold["task_id"],
                "condition_id": f"cell_{i}",
                "gold": gold,
                "inference_status": case.get("inference_status", "completed"),
                "proposed_assertions": case.get("proposed_assertions"),
                "malformed": bool(case.get("malformed", False)),
                "repo_commit": REPO_COMMIT,
            }
        )
    records = score_planned_cells(cells)
    assert len(records) == len(fx["cases"])
    assert len({(r["task_id"], r["condition_id"]) for r in records}) == len(records)
    for r in records:
        assert r["schema_version"] == SCORER_SCHEMA_VERSION
        assert r["scoring_status"] is not None
        assert "primary_score" in r


def test_23_duplicate_expected_fails_task_contract(fx):
    rec = _score(fx, _case(fx, "task_contract_duplicate_expected"))
    assert rec["scoring_status"] == ScoringStatus.TASK_CONTRACT_ERROR.value
    assert rec["invalid_reason"] == "DUPLICATE_EXPECTED_RELATION"
    assert rec["primary_score"] is None


def test_24_unknown_expected_identifier_fails_task_contract(fx):
    rec = _score(fx, _case(fx, "task_contract_unknown_identifier"))
    assert rec["scoring_status"] == ScoringStatus.TASK_CONTRACT_ERROR.value
    assert rec["invalid_reason"] == "UNKNOWN_EXPECTED_SUBJECT"
    assert rec["primary_score"] is None


def test_25_unknown_expected_relation_fails_task_contract(fx):
    bad = {
        "task_id": "rel_bad_rel",
        "contract_version": "ck.task_rel.v1",
        "subject_universe": ["ent_A"],
        "object_universe": ["ent_B"],
        "relation_universe": ["remains_open"],
        "expected_relations": [
            {
                "subject_id": "ent_A",
                "relation": "not_a_relation",
                "object_id": "ent_B",
            }
        ],
    }
    rec = score_cell(
        task_id="rel_bad_rel",
        condition_id="C3",
        gold=bad,
        proposed_assertions=[],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert rec["scoring_status"] == ScoringStatus.TASK_CONTRACT_ERROR.value
    assert rec["invalid_reason"] == "UNKNOWN_EXPECTED_RELATION"


def test_26_canonical_repeated_scoring_byte_identical(fx):
    case = _case(fx, "perfect_multi_relation")
    r1 = _score(fx, case)
    r2 = _score(fx, case)
    b1 = score_record_canonical_bytes(r1)
    b2 = score_record_canonical_bytes(r2)
    assert b1 == b2
    assert score_record_hash(r1) == score_record_hash(r2)


def test_27_canonical_score_hash_stable(fx):
    rec = _score(fx, _case(fx, "perfect_one_relation"))
    h = score_record_hash(rec)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
    # Order-independent expected hash
    g = RelationalGold.from_dict(_gold(fx, "base_gold"))
    assert rec["expected_relation_hash"] == triples_hash(g.expected_relations)


def test_28_exact_match_requires_no_extras_or_duplicates(fx):
    assert _score(fx, _case(fx, "perfect_one_relation"))["exact_relation_set_match"]
    assert not _score(fx, _case(fx, "exact_plus_unsupported"))[
        "exact_relation_set_match"
    ]
    assert not _score(fx, _case(fx, "exact_plus_duplicate"))[
        "exact_relation_set_match"
    ]
    assert not _score(fx, _case(fx, "empty_assertion_list"))[
        "exact_relation_set_match"
    ]


def test_29_zero_denominator_metric_behavior_explicit():
    # Empty unique proposals → precision undefined
    score, reason = primary_score_formula(
        true_positive_n=0,
        expected_n=0,
        wrong_relation_n=0,
        reversed_direction_n=0,
        unsupported_assertion_n=0,
        out_of_universe_assertion_n=0,
    )
    assert score is None
    assert reason == "ZERO_DENOMINATOR"

    gold = {
        "task_id": "empty_ok",
        "contract_version": "ck.task_rel.v1",
        "subject_universe": ["a"],
        "object_universe": ["b"],
        "relation_universe": ["r"],
        "expected_relations": [],
        "allow_empty_expected": True,
    }
    rec = score_cell(
        task_id="empty_ok",
        condition_id="C3",
        gold=gold,
        proposed_assertions=[],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert rec["scoring_status"] == ScoringStatus.SCORED.value
    assert rec["primary_score"] is None
    assert rec["primary_score_undefined_reason"] == "ZERO_DENOMINATOR"
    assert rec["precision"] is None
    assert rec["precision_undefined_reason"] == "ZERO_DENOMINATOR_PRECISION"
    assert rec["recall"] is None
    assert rec["recall_undefined_reason"] == "ZERO_DENOMINATOR_RECALL"
    assert rec["f1"] is None
    assert rec["f1_undefined_reason"] == "UNDEFINED_COMPONENT"


def test_30_scorer_records_headline_ineligible(fx):
    rec = _score(fx, _case(fx, "perfect_one_relation"))
    assert rec["headline_eligible"] is False
    assert rec["headline_ineligible_reason"] == HEADLINE_INELIGIBLE_REASON


def test_31_scorer_records_scientifically_incomplete(fx):
    rec = _score(fx, _case(fx, "perfect_one_relation"))
    assert rec["scientific_completion"] is False
    assert rec["scientific_status"] == SCIENTIFIC_STATUS


def test_invalid_response_null_score(fx):
    rec = _score(fx, _case(fx, "invalid_response"))
    assert rec["scoring_status"] == ScoringStatus.INVALID_RESPONSE.value
    assert rec["primary_score"] is None


def test_wrong_schema_key_malformed(fx):
    rec = _score(fx, _case(fx, "wrong_output_schema_key"))
    assert rec["scoring_status"] == ScoringStatus.MALFORMED_ASSERTIONS.value
    assert rec["primary_score"] is None


def test_prose_identifiers_no_structured_is_empty_score(fx):
    """Correct ids in prose only — scorer never re-parses prose."""
    rec = _score(fx, _case(fx, "prose_identifiers_no_structured"))
    assert rec["true_positive_n"] == 0
    assert rec["primary_score"] == 0.0


def test_every_relation_on_pair_wrong_relation_and_tp(fx):
    rec = _score(fx, _case(fx, "every_relation_on_one_pair"))
    assert rec["true_positive_n"] == 1
    assert rec["wrong_relation_n"] == 2
    assert rec["exact_relation_set_match"] is False
    # score = 1 / (1 + 2) = 1/3
    assert abs(rec["primary_score"] - (1.0 / 3.0)) < 1e-12


def test_symmetric_reverse_is_true_positive(fx):
    rec = _score(fx, _case(fx, "symmetric_relation_reverse_is_tp"))
    assert rec["true_positive_n"] == 1
    assert rec["reversed_direction_n"] == 0
    assert rec["false_negative_n"] == 0
    assert rec["primary_score"] == 1.0
    assert rec["exact_relation_set_match"] is True


def test_asymmetric_reverse_is_not_tp(fx):
    rec = _score(fx, _case(fx, "asymmetric_relation_incorrectly_reversed"))
    assert rec["reversed_direction_n"] == 1
    assert rec["true_positive_n"] == 0
    assert rec["false_negative_n"] == 1


def test_perfect_multi_relation(fx):
    rec = _score(fx, _case(fx, "perfect_multi_relation"))
    assert rec["true_positive_n"] == 3
    assert rec["false_negative_n"] == 0
    assert rec["primary_score"] == 1.0
    assert rec["exact_relation_set_match"] is True
    assert rec["precision"] == 1.0
    assert rec["recall"] == 1.0
    assert rec["f1"] == 1.0


def test_relation_classification_precedence_duplicate_first():
    gold = RelationalGold.from_dict(
        {
            "task_id": "t",
            "contract_version": "v1",
            "subject_universe": ["a"],
            "object_universe": ["b"],
            "relation_universe": ["r"],
            "expected_relations": [
                {"subject_id": "a", "relation": "r", "object_id": "b"}
            ],
        }
    )
    t = RelationTriple("a", "r", "b")
    remaining = set(gold.expected_relations)
    seen: set[RelationTriple] = set()
    c1 = classify_proposal(
        t, gold=gold, remaining_expected=remaining, seen_unique=seen
    )
    assert c1 is RelationClass.TRUE_POSITIVE
    seen.add(t)
    remaining.discard(t)
    c2 = classify_proposal(
        t, gold=gold, remaining_expected=remaining, seen_unique=seen
    )
    assert c2 is RelationClass.DUPLICATE_ASSERTION


def test_malformed_symmetry_metadata_fails():
    with pytest.raises(TaskContractError) as ei:
        RelationalGold.from_dict(
            {
                "task_id": "t",
                "contract_version": "v1",
                "subject_universe": ["a"],
                "object_universe": ["b"],
                "relation_universe": ["r"],
                "symmetric_relations": ["not_in_universe"],
                "expected_relations": [
                    {"subject_id": "a", "relation": "r", "object_id": "b"}
                ],
            }
        )
    assert ei.value.reason_code == "MALFORMED_SYMMETRY_METADATA"


def test_missing_task_id_fails():
    with pytest.raises(TaskContractError) as ei:
        RelationalGold.from_dict(
            {
                "contract_version": "v1",
                "subject_universe": ["a"],
                "object_universe": ["b"],
                "relation_universe": ["r"],
                "expected_relations": [
                    {"subject_id": "a", "relation": "r", "object_id": "b"}
                ],
            }
        )
    assert ei.value.reason_code == "MISSING_TASK_ID"


def test_missing_contract_version_fails():
    with pytest.raises(TaskContractError) as ei:
        RelationalGold.from_dict(
            {
                "task_id": "t",
                "subject_universe": ["a"],
                "object_universe": ["b"],
                "relation_universe": ["r"],
                "expected_relations": [
                    {"subject_id": "a", "relation": "r", "object_id": "b"}
                ],
            }
        )
    assert ei.value.reason_code == "MISSING_CONTRACT_VERSION"


def test_empty_expected_fails_closed():
    with pytest.raises(TaskContractError) as ei:
        RelationalGold.from_dict(
            {
                "task_id": "t",
                "contract_version": "v1",
                "subject_universe": ["a"],
                "object_universe": ["b"],
                "relation_universe": ["r"],
                "expected_relations": [],
            }
        )
    assert ei.value.reason_code == "EMPTY_EXPECTED_RELATIONS"


def test_assertion_missing_fields_malformed(fx):
    gold = _gold(fx, "base_gold")
    rec = score_cell(
        task_id=gold["task_id"],
        condition_id="C3",
        gold=gold,
        proposed_assertions=[{"subject_id": "ent_A", "object_id": "ent_B"}],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert rec["scoring_status"] == ScoringStatus.MALFORMED_ASSERTIONS.value
    assert rec["primary_score"] is None


def test_uppercase_inference_status_timeout(fx):
    gold = _gold(fx, "base_gold")
    rec = score_cell(
        task_id=gold["task_id"],
        condition_id="C3",
        gold=gold,
        proposed_assertions=None,
        inference_status="TIMEOUT",
        repo_commit=REPO_COMMIT,
    )
    assert rec["scoring_status"] == ScoringStatus.TIMEOUT.value
    assert rec["primary_score"] is None


def test_provenance_and_versions_pass_through(fx):
    rec = _score(fx, _case(fx, "perfect_one_relation"))
    assert rec["repo_commit"] == REPO_COMMIT
    assert rec["task_contract_version"] == "ck.task_rel.v1"
    assert rec["scorer_schema_version"] == SCORER_SCHEMA_VERSION
    assert rec["model_runtime_provenance"]["model_tag"] == "fixture-none"


def test_fixture_scientific_policy_fields(fx):
    assert fx["scientific_status"] == SCIENTIFIC_STATUS
    assert fx["scientific_completion"] is False
    assert fx["headline_eligible"] is False


# ---------------------------------------------------------------------------
# Property / bounded exhaustive shotgun-resistance proof
# ---------------------------------------------------------------------------


def test_property_shotgun_monotonicity_over_frozen_universe(fx):
    """For every proposal set P and non-true assertion x ∉ P:
    primary_score(P ∪ {x}) <= primary_score(P)

    Universe: 2 subjects × 2 objects × 2 relations = 8 triples.
    Expected: one fixed triple. Exhaustive over all 2^8 proposal subsets
    and every non-true x not already in P.
    """
    gold_dict = _gold(fx, "property_universe")
    gold = RelationalGold.from_dict(gold_dict)
    subjects = sorted(gold.subject_universe)
    objects = sorted(gold.object_universe)
    relations = sorted(gold.relation_universe)
    universe = [
        RelationTriple(s, r, o)
        for s in subjects
        for r in relations
        for o in objects
    ]
    assert len(universe) == 8
    expected = next(iter(gold.expected_relations))
    non_true = [t for t in universe if t != expected]

    def score_of(proposal: list[RelationTriple]) -> float | None:
        rec = score_cell(
            task_id=gold.task_id,
            condition_id="PROP",
            gold=gold_dict,
            proposed_assertions=[t.as_dict() for t in proposal],
            inference_status="completed",
            repo_commit=REPO_COMMIT,
        )
        return rec["primary_score"]

    violations: list[str] = []
    # All subsets of universe (2^8 = 256)
    for bits in range(2 ** len(universe)):
        p = [universe[i] for i in range(len(universe)) if bits & (1 << i)]
        p_score = score_of(p)
        for x in non_true:
            if x in p:
                continue
            p_x = p + [x]
            px_score = score_of(p_x)
            # When both defined, monotonicity; null only when both empty-like
            if p_score is None and px_score is None:
                continue
            if p_score is None and px_score is not None:
                # Adding noise should not create a defined better score from null
                # with expected_n>0 p_score is always defined (denom >= expected_n)
                violations.append(f"null_base_defined_extra: {x}")
                continue
            if px_score is None:
                # defined → null would be decrease if we treat null as worse; skip
                continue
            if px_score > p_score + 1e-15:
                violations.append(
                    f"P={sorted(p)} x={x}: {p_score} -> {px_score}"
                )

    assert not violations, f"monotonicity violations ({len(violations)}): {violations[:5]}"


def test_property_duplicates_cannot_improve_score(fx):
    gold_dict = _gold(fx, "base_gold")
    correct = {
        "subject_id": "ent_A",
        "relation": "remains_open",
        "object_id": "ent_B",
    }
    wrong = {
        "subject_id": "ent_A",
        "relation": "depends_on",
        "object_id": "ent_B",
    }
    base_correct = score_cell(
        task_id=gold_dict["task_id"],
        condition_id="C3",
        gold=gold_dict,
        proposed_assertions=[correct],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    multi_correct = score_cell(
        task_id=gold_dict["task_id"],
        condition_id="C3",
        gold=gold_dict,
        proposed_assertions=[correct, correct, correct],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert multi_correct["primary_score"] == base_correct["primary_score"]
    assert multi_correct["true_positive_n"] == base_correct["true_positive_n"]

    base_wrong = score_cell(
        task_id=gold_dict["task_id"],
        condition_id="C3",
        gold=gold_dict,
        proposed_assertions=[wrong],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    multi_wrong = score_cell(
        task_id=gold_dict["task_id"],
        condition_id="C3",
        gold=gold_dict,
        proposed_assertions=[wrong, wrong, wrong],
        inference_status="completed",
        repo_commit=REPO_COMMIT,
    )
    assert multi_wrong["primary_score"] == base_wrong["primary_score"]


def test_all_fixture_cases_emit_terminal_record(fx):
    """Adversarial fixture sweep: every frozen case yields one record."""
    results = []
    for case in fx["cases"]:
        rec = _score(fx, case, condition_id=f"fix_{case['id']}")
        results.append((case["name"], rec["scoring_status"], rec["primary_score"]))
        assert rec["headline_eligible"] is False
        assert rec["scientific_completion"] is False
        assert rec["scientific_status"] == SCIENTIFIC_STATUS
    assert len(results) == 30
    # Spot-check expected terminal classes
    by_name = {n: (s, p) for n, s, p in results}
    assert by_name["timeout"][0] == ScoringStatus.TIMEOUT.value
    assert by_name["timeout"][1] is None
    assert by_name["perfect_one_relation"][0] == ScoringStatus.SCORED.value
    assert by_name["perfect_one_relation"][1] == 1.0
    assert by_name["task_contract_duplicate_expected"][0] == (
        ScoringStatus.TASK_CONTRACT_ERROR.value
    )


def test_no_model_invocation_marker():
    """Static guarantee: this module never imports generate/ollama paths for scoring."""
    import conditioned_kernel.relational_scorer as rs
    import inspect

    src = inspect.getsource(rs)
    assert "ollama" not in src.lower()
    assert "httpx" not in src
    assert "requests." not in src
    assert "ExecutionScope" not in src
