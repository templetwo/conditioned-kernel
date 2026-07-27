"""RUN 00.6F.1 — gold-contract alignment and full corpus eligibility."""

from __future__ import annotations

from pathlib import Path

from conditioned_kernel.m0_admission import evaluate_admission
from conditioned_kernel.m0_manifest import (
    GOLD_SEMANTICS_ALL_REQUIRED,
    KNOWN_OUTPUT_SCHEMA_IDS,
    build_candidate_manifest,
    build_corpus_eligibility_rows,
    discover_raw_tasks,
    evaluate_task_eligibility,
)
from conditioned_kernel.relational_scorer import score_cell


ROOT = Path(__file__).resolve().parents[1]


def test_6f1_defect_original_one_relation_scores_half_against_dual_conjunctive_gold():
    """Pre-correction ceiling: one instruction-following relation → primary_score=0.5."""
    # Reconstruct the 00.6F gold shape (two valid_combinations as expected)
    gold = {
        "task_id": "live_plumbing_01",
        "contract_version": "ck.task_rel.v1",
        "subject_universe": ["thread_gamma_receipt"],
        "object_universe": ["question_cold_start"],
        "relation_universe": ["remains_open", "references"],
        "expected_relations": [
            {
                "subject_id": "thread_gamma_receipt",
                "relation": "remains_open",
                "object_id": "question_cold_start",
            },
            {
                "subject_id": "thread_gamma_receipt",
                "relation": "references",
                "object_id": "question_cold_start",
            },
        ],
    }
    one = [
        {
            "subject_id": "thread_gamma_receipt",
            "relation": "remains_open",
            "object_id": "question_cold_start",
        }
    ]
    rec = score_cell(
        task_id="live_plumbing_01",
        condition_id="C3_static_ck",
        gold=gold,
        proposed_assertions=one,
        inference_status="completed",
    )
    assert rec["true_positive_n"] == 1
    assert rec["expected_n"] == 2
    assert rec["false_negative_n"] == 1
    assert rec["primary_score"] == 0.5


def test_6f1_missing_output_schema_id_fails_eligibility():
    ann = {
        "task_id": "t_no_schema",
        "version": "ck.task_dep.v1",
        "fields": [
            {
                "field_id": "fact_a",
                "classification": "REQUIRED_TASK_FACT",
                "value": "A",
            },
            {
                "field_id": "op_a",
                "classification": "REQUIRED_OPERATIONAL_STATE",
                "value": "O",
            },
            {
                "field_id": "leak",
                "classification": "FORBIDDEN_ANSWER_LEAKAGE",
                "value": "X",
            },
            # deliberately no output_schema_id
        ],
    }
    task = {
        "task_id": "t_no_schema",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_no_schema",
            "expected_relation_semantics": "all_required",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
            "episode_a": {
                "prompt": "Return every supported continuity assertion from the permitted closed universe."
            },
        },
    }
    # annotation without output_schema_id
    result = evaluate_task_eligibility(
        task,
        {
            "t_no_schema": {
                "path": "syn",
                "sha256": "1" * 64,
                "data": ann,
            }
        },
    )
    assert result["inclusion_verdict"] == "EXCLUDED"
    assert "MISSING_OUTPUT_SCHEMA_ID" in result["exclusion_reasons"]


def test_6f1_one_of_gold_semantics_excluded():
    task = {
        "task_id": "t_one_of",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_one_of",
            "expected_relation_semantics": "one_of",
            "output_schema_id": "continuity_assertions_v1",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
        },
    }
    r = evaluate_task_eligibility(task, {})
    assert "UNSUPPORTED_GOLD_SEMANTICS" in r["exclusion_reasons"]


def test_6f1_choose_any_excluded():
    task = {
        "task_id": "t_choose",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_choose",
            "expected_relation_semantics": "choose_any",
            "output_schema_id": "continuity_assertions_v1",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
        },
    }
    r = evaluate_task_eligibility(task, {})
    assert "UNSUPPORTED_GOLD_SEMANTICS" in r["exclusion_reasons"]


def test_6f1_unspecified_gold_semantics_excluded():
    task = {
        "task_id": "t_unspec",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_unspec",
            # no expected_relation_semantics
            "output_schema_id": "continuity_assertions_v1",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
        },
    }
    r = evaluate_task_eligibility(task, {})
    assert "UNSUPPORTED_GOLD_SEMANTICS" in r["exclusion_reasons"]


def test_6f1_unknown_gold_semantics_excluded():
    task = {
        "task_id": "t_unk",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_unk",
            "expected_relation_semantics": "max_over_gold",
            "output_schema_id": "continuity_assertions_v1",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
        },
    }
    r = evaluate_task_eligibility(task, {})
    assert "UNSUPPORTED_GOLD_SEMANTICS" in r["exclusion_reasons"]


def test_6f1_all_required_accepted_as_m0_v1_semantic():
    assert GOLD_SEMANTICS_ALL_REQUIRED == "all_required"
    m = build_candidate_manifest()
    for t in m["included_tasks"]:
        assert t["expected_relation_semantics"] == "all_required"
        assert t["gold"]["expected_relation_semantics"] == "all_required"


def test_6f1_one_answer_instruction_cannot_pair_multi_conjunctive():
    rows = build_corpus_eligibility_rows()
    orig = next(r for r in rows if r["task_id"] == "live_plumbing_01")
    assert orig["inclusion_verdict"] == "EXCLUDED"
    assert "INSTRUCTION_GOLD_SEMANTICS_MISMATCH" in orig["exclusion_reasons"] or (
        "AMBIGUOUS_EXPECTED_RELATIONS" in orig["exclusion_reasons"]
    )


def test_6f1_every_supported_instruction_can_pair_multi_conjunctive():
    rows = build_corpus_eligibility_rows()
    m0 = next(r for r in rows if r["task_id"] == "live_plumbing_01_m0_v1")
    assert m0["inclusion_verdict"] == "INCLUDED"
    assert m0["expected_relation_count"] == 2
    assert m0["expected_relation_semantics"] == "all_required"


def test_6f1_corrected_task_perfect_answer_scores_1():
    m = build_candidate_manifest()
    gold = m["included_tasks"][0]["gold"]
    rec = score_cell(
        task_id=gold["task_id"],
        condition_id="C3_static_ck",
        gold=gold,
        proposed_assertions=gold["expected_relations"],
        inference_status="completed",
    )
    assert rec["primary_score"] == 1.0
    assert rec["true_positive_n"] == len(gold["expected_relations"])
    assert rec["exact_relation_set_match"] is True


def test_6f1_unknown_output_schema_fails():
    task = {
        "task_id": "t_bad_schema",
        "source_path": "synthetic",
        "source_sha256": "0" * 64,
        "raw": {
            "id": "t_bad_schema",
            "expected_relation_semantics": "all_required",
            "output_schema_id": "not_a_real_schema",
            "continuity_universe": {
                "subject_ids": ["s"],
                "object_ids": ["o"],
                "relations": ["r"],
            },
            "expected_relations": [
                {"subject_id": "s", "relation": "r", "object_id": "o"}
            ],
            "episode_a": {
                "prompt": "Return every supported continuity assertion from the permitted closed universe."
            },
        },
    }
    ann = {
        "task_id": "t_bad_schema",
        "version": "ck.task_dep.v1",
        "fields": [
            {
                "field_id": "fact_a",
                "classification": "REQUIRED_TASK_FACT",
                "value": "A",
            },
            {
                "field_id": "op_a",
                "classification": "REQUIRED_OPERATIONAL_STATE",
                "value": "O",
            },
            {
                "field_id": "output_schema_id",
                "classification": "REQUIRED_OPERATIONAL_STATE",
                "value": "not_a_real_schema",
            },
            {
                "field_id": "leak",
                "classification": "FORBIDDEN_ANSWER_LEAKAGE",
                "value": "X",
            },
        ],
    }
    r = evaluate_task_eligibility(
        task, {"t_bad_schema": {"path": "x", "sha256": "2" * 64, "data": ann}}
    )
    assert "UNKNOWN_OUTPUT_SCHEMA_ID" in r["exclusion_reasons"]


def test_6f1_every_discovered_task_in_include_or_exclude():
    tasks = discover_raw_tasks()
    rows = build_corpus_eligibility_rows()
    ids_disc = {t["task_id"] for t in tasks}
    ids_rows = {r["task_id"] for r in rows}
    assert ids_disc == ids_rows
    for r in rows:
        assert r["inclusion_verdict"] in ("INCLUDED", "EXCLUDED")


def test_6f1_no_discovered_task_disappears():
    m = build_candidate_manifest()
    disc = {t["task_id"] for t in discover_raw_tasks()}
    seen = {t["task_id"] for t in m["included_tasks"]} | {
        t["task_id"] for t in m["exclusion_ledger"]["tasks"]
    }
    assert disc == seen


def test_6f1_included_task_invariants(manifest_optional=None):
    m = build_candidate_manifest()
    n = len(m["included_tasks"])
    assert m["planned_cell_count"] == 4 * n
    assert m["planned_primary_pairs_n"] == n
    for t in m["included_tasks"]:
        assert t["annotation_path"]
        assert t["annotation_sha256"]
        assert t["gold"] is not None
        assert t["gold"]["expected_relations"]
        assert t["expected_relation_semantics"] == "all_required"
        assert t["output_schema_id"] in KNOWN_OUTPUT_SCHEMA_IDS
        g = t["gold"]
        assert g["subject_universe"]
        assert g["relation_universe"]
        assert g["object_universe"]


def test_6f1_source_order_does_not_alter_manifest():
    a = build_candidate_manifest()
    # reverse source list
    sources = list(reversed(list(__import__(
        "conditioned_kernel.m0_manifest", fromlist=["default_task_sources"]
    ).default_task_sources())))
    b = build_candidate_manifest(sources=sources)
    assert a["manifest_sha256"] == b["manifest_sha256"]
    assert [c["cell_id"] for c in a["planned_cells"]] == [
        c["cell_id"] for c in b["planned_cells"]
    ]


def test_6f1_exclusion_ledger_deterministic():
    a = build_candidate_manifest()
    b = build_candidate_manifest()
    assert a["exclusion_ledger"] == b["exclusion_ledger"]


def test_6f1_headline_cannot_be_true_while_scientifically_incomplete():
    m = build_candidate_manifest()
    # empty terminals → incomplete
    rep = evaluate_admission(manifest=m, terminal_cells=[])
    assert rep["scientific_completion"] is False
    assert rep["headline_eligible"] is False
    # forge violation path is impossible through evaluate_admission
    assert not (rep["headline_eligible"] and not rep["scientific_completion"])


def test_6f1_original_live_plumbing_disposition():
    rows = build_corpus_eligibility_rows()
    orig = next(r for r in rows if r["task_id"] == "live_plumbing_01")
    assert orig["inclusion_verdict"] == "EXCLUDED"
    # Path A: versioned successor included
    m0 = next(r for r in rows if r["task_id"] == "live_plumbing_01_m0_v1")
    assert m0["inclusion_verdict"] == "INCLUDED"
    # Original smoke artifact file still exists unchanged as historical source
    assert (ROOT / "experiments/probes/live_plumbing_task.json").is_file()
