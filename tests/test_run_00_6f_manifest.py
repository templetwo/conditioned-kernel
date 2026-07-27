"""RUN 00.6F — M0 candidate manifest freeze.

Offline. No model invocation.
"""

from __future__ import annotations

import inspect
import json

import pytest

from conditioned_kernel.control_contract import ConditionId
from conditioned_kernel.m0_manifest import (
    GENERATION_PARAMETERS,
    MANIFEST_ID,
    MODEL_TAG,
    ManifestError,
    build_candidate_manifest,
    build_dry_plan,
    compute_cell_id,
    planned_cell_identity_payload,
    validate_condition_id,
    write_frozen_artifacts,
)
from conditioned_kernel.m0_admission import verify_manifest_hash
from conditioned_kernel.relational_scorer import SCORER_SCHEMA_VERSION, canonical_json_bytes


@pytest.fixture(scope="module")
def manifest():
    return build_candidate_manifest()


def test_manifest_generation_byte_deterministic():
    a = build_candidate_manifest()
    b = build_candidate_manifest()
    assert canonical_json_bytes(a) == canonical_json_bytes(b)
    assert a["manifest_sha256"] == b["manifest_sha256"]


def test_manifest_hash_stable(manifest):
    assert len(manifest["manifest_sha256"]) == 64
    assert verify_manifest_hash(manifest)


def test_every_eligible_task_produces_c0_c1_c2_c3(manifest):
    for task in manifest["included_tasks"]:
        tid = task["task_id"]
        conds = {
            c["condition_id"]
            for c in manifest["planned_cells"]
            if c["task_id"] == tid
        }
        assert conds == {
            ConditionId.C0_BARE.value,
            ConditionId.C1_BUDGET_MATCHED_BARE.value,
            ConditionId.C2_INSTRUCTION_IDENTICAL.value,
            ConditionId.C3_STATIC_CK.value,
        }


def test_every_excluded_task_in_exclusion_ledger(manifest):
    excluded = manifest["exclusion_ledger"]["tasks"]
    assert len(excluded) >= 1
    for e in excluded:
        assert e["inclusion_verdict"] == "EXCLUDED"
        assert e["exclusion_reasons"]
        assert e["source_path"]
        assert e["source_sha256"]
        assert len(e["source_sha256"]) == 64


def test_every_c3_has_exactly_one_paired_c1(manifest):
    for pair in manifest["planned_primary_pairs"]:
        c1 = next(
            c for c in manifest["planned_cells"] if c["cell_id"] == pair["c1_cell_id"]
        )
        c3 = next(
            c for c in manifest["planned_cells"] if c["cell_id"] == pair["c3_cell_id"]
        )
        assert c1["condition_id"] == ConditionId.C1_BUDGET_MATCHED_BARE.value
        assert c3["condition_id"] == ConditionId.C3_STATIC_CK.value
        assert c3["paired_primary_cell_id"] == c1["cell_id"]
        assert c1["paired_primary_cell_id"] == c3["cell_id"]
        assert c1["task_id"] == c3["task_id"] == pair["task_id"]


def test_no_orphan_primary_control_cells(manifest):
    c1s = [
        c
        for c in manifest["planned_cells"]
        if c["condition_id"] == ConditionId.C1_BUDGET_MATCHED_BARE.value
    ]
    c3s = [
        c
        for c in manifest["planned_cells"]
        if c["condition_id"] == ConditionId.C3_STATIC_CK.value
    ]
    assert len(c1s) == len(c3s) == manifest["planned_primary_pairs_n"]
    paired_c1 = {p["c1_cell_id"] for p in manifest["planned_primary_pairs"]}
    paired_c3 = {p["c3_cell_id"] for p in manifest["planned_primary_pairs"]}
    assert {c["cell_id"] for c in c1s} == paired_c1
    assert {c["cell_id"] for c in c3s} == paired_c3


def test_cell_ids_deterministic(manifest):
    m2 = build_candidate_manifest()
    ids1 = [c["cell_id"] for c in manifest["planned_cells"]]
    ids2 = [c["cell_id"] for c in m2["planned_cells"]]
    assert ids1 == ids2
    assert all(len(i) == 64 for i in ids1)


def test_identity_change_alters_cell_id():
    base = planned_cell_identity_payload(
        manifest_id=MANIFEST_ID,
        task_id="t",
        condition_id=ConditionId.C3_STATIC_CK.value,
        replicate_id="0",
        model_tag=MODEL_TAG,
        seed=0,
        packet_contract_version="ck.packet_contract.v1",
        scorer_schema_version=SCORER_SCHEMA_VERSION,
    )
    a = compute_cell_id(base)
    changed = dict(base)
    changed["seed"] = 1
    b = compute_cell_id(changed)
    assert a != b
    changed2 = dict(base)
    changed2["condition_id"] = ConditionId.C0_BARE.value
    assert compute_cell_id(changed2) != a


def test_json_key_order_does_not_alter_cell_id():
    p1 = {
        "manifest_id": MANIFEST_ID,
        "task_id": "t",
        "condition_id": "C0_bare",
        "replicate_id": "0",
        "model_tag": MODEL_TAG,
        "seed": 0,
        "packet_contract_version": "ck.packet_contract.v1",
        "scorer_schema_version": SCORER_SCHEMA_VERSION,
    }
    # reverse insertion order
    p2 = {k: p1[k] for k in reversed(list(p1.keys()))}
    assert compute_cell_id(p1) == compute_cell_id(p2)


def test_unknown_condition_fails_closed():
    with pytest.raises(ManifestError) as ei:
        validate_condition_id("C9_not_real")
    assert ei.value.reason_code == "UNKNOWN_CONDITION"


def test_missing_task_annotation_excludes(manifest):
    # All excluded corpus tasks lack annotations
    reasons_union = set()
    for e in manifest["exclusion_ledger"]["tasks"]:
        reasons_union.update(e["exclusion_reasons"])
    assert "MISSING_TASK_DEP_ANNOTATION" in reasons_union or (
        "MISSING_CONTINUITY_UNIVERSE" in reasons_union
    )


def test_live_plumbing_m0_v1_included(manifest):
    ids = [t["task_id"] for t in manifest["included_tasks"]]
    assert "live_plumbing_01_m0_v1" in ids
    assert "live_plumbing_01" not in ids


def test_model_and_params_frozen(manifest):
    assert manifest["model_tag"] == "qwen2.5:0.5b"
    assert manifest["generation_parameters"]["temperature"] == 0.0
    assert manifest["generation_parameters"]["seed"] == 0
    assert manifest["retry_policy"]["retries_in_manifest"] == 0
    assert manifest["authorization_status"] == "unratified"
    assert manifest["scientific_completion"] is False
    assert manifest["headline_eligible"] is False
    assert manifest["experiment_contract_id"] is None
    assert manifest["execution_scope"] == "dry_planning_only"


def test_dry_plan_no_model_and_complete(manifest):
    plan = build_dry_plan(manifest)
    assert plan["no_model_execution"] is True
    assert plan["model_client_imported"] is False
    assert plan["planned_cell_count"] == manifest["planned_cell_count"]
    assert len(plan["planned_cell_ids"]) == manifest["planned_cell_count"]
    assert plan["authorization_status"] == "unratified"
    assert plan["scientific_completion"] is False
    assert plan["headline_eligible"] is False


def test_dry_plan_and_manifest_modules_do_not_import_generate():
    import conditioned_kernel.m0_manifest as mm

    src = inspect.getsource(mm)
    assert "from conditioned_kernel.generate" not in src
    assert "import ollama" not in src.lower()
    assert "httpx" not in src


def test_write_frozen_artifacts(tmp_path, manifest):
    paths = write_frozen_artifacts(out_dir=tmp_path)
    assert paths["manifest"].is_file()
    data = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert data["manifest_sha256"] == manifest["manifest_sha256"]
    assert paths["exclusions"].is_file()
    assert paths["plan"].is_file()


def test_planned_cells_headline_and_sci_false(manifest):
    for c in manifest["planned_cells"]:
        assert c["scientific_completion"] is False
        assert c["headline_eligible"] is False
        assert c["model_tag"] == MODEL_TAG
        assert c["generation_parameters"] == GENERATION_PARAMETERS


def test_no_retry_cells_in_manifest(manifest):
    assert all(c["replicate_id"] == "0" for c in manifest["planned_cells"])
    assert manifest["retry_policy"]["replacement_runs"] is False
