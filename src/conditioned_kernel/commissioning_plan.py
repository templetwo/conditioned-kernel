"""RUN 00.8B — non-scientific commissioning plan (separate from retired M0 candidate).

Does not mutate ck.m0.candidate.v1. Plan is commissioning_validation only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from conditioned_kernel.m0_manifest import (
    RETIRED_MANIFEST_SHA256,
    _repo_root,
    load_json,
)
from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

COMMISSIONING_PLAN_SCHEMA = "ck.commissioning_plan.v1"
COMMISSIONING_PLAN_ID = "ck.run.00.8b.ollama.v1"
EXECUTION_SCOPE = "commissioning_validation"
SCIENTIFIC_STATUS = "commissioning_instrument_test_only"
SOURCE_CANDIDATE_MANIFEST_ID = "ck.m0.candidate.v1"
SOURCE_CANDIDATE_MANIFEST_SHA256 = RETIRED_MANIFEST_SHA256

COMMISSIONING_LABELS: dict[str, Any] = {
    "execution_scope": EXECUTION_SCOPE,
    "scientific_status": SCIENTIFIC_STATUS,
    "scientific_completion": False,
    "headline_eligible": False,
    "m0_authorized": False,
    "efficacy_claim_permitted": False,
}


def load_retired_candidate(path: Path | None = None) -> dict[str, Any]:
    root = _repo_root()
    p = path or (root / "experiments" / "manifests" / "m0_candidate_v1.json")
    data = load_json(p)
    body = {k: v for k, v in data.items() if k != "manifest_sha256"}
    computed = sha256_hex(canonical_json_bytes(body))
    if computed != SOURCE_CANDIDATE_MANIFEST_SHA256:
        raise ValueError(
            f"RETIRED_MANIFEST_HASH_MISMATCH: {computed} != {SOURCE_CANDIDATE_MANIFEST_SHA256}"
        )
    if str(data.get("manifest_sha256")) != SOURCE_CANDIDATE_MANIFEST_SHA256:
        raise ValueError("RETIRED_MANIFEST_EMBEDDED_HASH_MISMATCH")
    return data


def build_commissioning_plan(
    *,
    source: Mapping[str, Any] | None = None,
    repo_head: str | None = None,
) -> dict[str, Any]:
    """Build ck.commissioning_plan.v1 from the retired candidate (read-only source)."""
    cand = dict(source) if source is not None else load_retired_candidate()
    raw_cells = sorted(
        cand["planned_cells"],
        key=lambda c: (
            # C0, C1, C2, C3 fixed execution order
            ["C0_bare", "C1_budget_matched_bare", "C2_instruction_identical", "C3_static_ck"].index(
                c["condition_id"]
            )
            if c["condition_id"]
            in (
                "C0_bare",
                "C1_budget_matched_bare",
                "C2_instruction_identical",
                "C3_static_ck",
            )
            else 99,
            c["task_id"],
            c["cell_id"],
        ),
    )
    # Re-bind cells to commissioning plan identity (preserve cell_id from source freeze)
    cells = []
    for c in raw_cells:
        cc = dict(c)
        cc["manifest_id"] = COMMISSIONING_PLAN_ID
        cc["source_candidate_manifest_id"] = SOURCE_CANDIDATE_MANIFEST_ID
        cc["source_candidate_manifest_sha256"] = SOURCE_CANDIDATE_MANIFEST_SHA256
        cells.append(cc)
    plan: dict[str, Any] = {
        "schema_version": COMMISSIONING_PLAN_SCHEMA,
        "commissioning_plan_id": COMMISSIONING_PLAN_ID,
        "source_candidate_manifest_id": SOURCE_CANDIDATE_MANIFEST_ID,
        "source_candidate_manifest_sha256": SOURCE_CANDIDATE_MANIFEST_SHA256,
        "repository_head": repo_head,
        "model_tag": cand["model_tag"],
        "generation_parameters": dict(cand["generation_parameters"]),
        "condition_set": list(cand["condition_set"]),
        "execution_order": [c["condition_id"] for c in cells],
        "execution_order_note": (
            "Fixed operational order C0→C1→C2→C3; not scientifically randomized"
        ),
        "max_model_invocations": 4,
        "replicates": 1,
        "retries": 0,
        "planned_cells": cells,
        "planned_cell_count": len(cells),
        "planned_primary_pairs": list(cand.get("planned_primary_pairs") or []),
        "included_tasks": list(cand.get("included_tasks") or []),
        "task_gold_leak_disclosure": (
            "Source candidate task contains gold-visible structure in control "
            "packets; this run is instrument validation only and permits no "
            "efficacy or thesis interpretation."
        ),
        **COMMISSIONING_LABELS,
    }
    body = {k: v for k, v in plan.items() if k != "commissioning_plan_sha256"}
    plan["commissioning_plan_sha256"] = sha256_hex(canonical_json_bytes(body))
    return plan


def verify_plan_hash(plan: Mapping[str, Any]) -> bool:
    body = {k: v for k, v in plan.items() if k != "commissioning_plan_sha256"}
    return sha256_hex(canonical_json_bytes(body)) == str(
        plan.get("commissioning_plan_sha256")
    )


def write_plan(plan: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
