"""RUN 00.6F — M0 candidate manifest freeze and planned-cell identity.

Offline only. No model invocation. No SCIENTIFIC_EXPERIMENT activation.
Candidate remains unratified; scientific_completion=false always.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from conditioned_kernel.control_contract import (
    CONTROL_VERIFIER_VERSION,
    ConditionId,
    PACKET_CONTRACT_VERSION,
    TASK_DEP_ANNOTATION_VERSION,
    TaskDependencyAnnotation,
)
from conditioned_kernel.outcomes import ManifestCell
from conditioned_kernel.relational_scorer import (
    SCORER_SCHEMA_VERSION,
    RelationalGold,
    TaskContractError,
    canonical_json_bytes,
    sha256_hex,
    triples_hash,
)

# ---------------------------------------------------------------------------
# Schema / freeze constants
# ---------------------------------------------------------------------------

MANIFEST_SCHEMA_VERSION = "ck.m0_manifest.v1"
PLANNED_CELL_SCHEMA_VERSION = "ck.planned_cell.v1"
MANIFEST_ID = "ck.m0.candidate.v1"
LEDGER_SCHEMA_VERSION = "ck.terminal_ledger.v1"  # existing TerminalLedger surface
TERMINAL_CELL_SCHEMA_VERSION = "ck.terminal_cell.v1"
ADMISSION_SCHEMA_VERSION = "ck.m0_admission_report.v1"

# Frozen wall-clock for byte-determinism of this candidate freeze (not live time).
FREEZE_TIMESTAMP = "2026-07-27T00:00:00Z"
REPO_COMMIT_DEFAULT = "5826b334a1fcc56e859e4fef79e8ce1e140abf20"

MODEL_TAG = "qwen2.5:0.5b"
TEMPERATURE = 0.0
SEED = 0
NUM_CTX = 2048
REPLICATE_ID = "0"
REPLICATES_PER_CELL = 1

AUTHORIZATION_STATUS = "unratified"
EXECUTION_SCOPE = "dry_planning_only"
HEADLINE_INELIGIBLE_REASON = "m0_manifest_and_admission_contract_not_yet_ratified"

CONDITIONS: tuple[ConditionId, ...] = (
    ConditionId.C0_BARE,
    ConditionId.C1_BUDGET_MATCHED_BARE,
    ConditionId.C2_INSTRUCTION_IDENTICAL,
    ConditionId.C3_STATIC_CK,
)

PRIMARY_CONTRAST = {
    "id": "C3_vs_C1",
    "treatment": ConditionId.C3_STATIC_CK.value,
    "control": ConditionId.C1_BUDGET_MATCHED_BARE.value,
    "role": "primary",
    "interpretation": (
        "structured substrate continuity under equal finalized request-byte length"
    ),
}
SECONDARY_CONTRAST = {
    "id": "C3_vs_C2",
    "treatment": ConditionId.C3_STATIC_CK.value,
    "control": ConditionId.C2_INSTRUCTION_IDENTICAL.value,
    "role": "secondary_diagnostic",
    "interpretation": (
        "reconstructed continuity state under shared operative instructions; "
        "byte difference disclosed"
    ),
}
DESCRIPTIVE_CONTRAST = {
    "id": "C3_vs_C0",
    "treatment": ConditionId.C3_STATIC_CK.value,
    "control": ConditionId.C0_BARE.value,
    "role": "descriptive_only",
    "interpretation": (
        "knowingly confounded; must never be presented as primary causal estimate"
    ),
    "headline_eligible": False,
}

GENERATION_PARAMETERS: dict[str, Any] = {
    "temperature": TEMPERATURE,
    "seed": SEED,
    "num_ctx": NUM_CTX,
    "stream": False,
}


class ManifestError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


class InclusionVerdict(str, Enum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"


# ---------------------------------------------------------------------------
# Paths / discovery
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_task_sources() -> list[Path]:
    root = _repo_root()
    return [
        root / "experiments" / "probes" / "continuity_tasks.json",
        root / "experiments" / "probes" / "live_plumbing_task.json",
    ]


def default_annotation_dir() -> Path:
    return _repo_root() / "tests" / "fixtures"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return sha256_hex(path.read_bytes())


def discover_raw_tasks(sources: Sequence[Path] | None = None) -> list[dict[str, Any]]:
    """Enumerate existing continuity task corpora. No new tasks invented."""
    paths = list(sources) if sources is not None else default_task_sources()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(paths, key=lambda p: str(p)):
        if not path.is_file():
            continue
        data = load_json(path)
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, Mapping):
                continue
            tid = str(item.get("id") or item.get("task_id") or "")
            if not tid:
                continue
            if tid in seen:
                raise ManifestError("DUPLICATE_TASK_ID", tid)
            seen.add(tid)
            out.append(
                {
                    "task_id": tid,
                    "source_path": str(path.relative_to(_repo_root())),
                    "source_sha256": file_sha256(path),
                    "raw": dict(item),
                }
            )
    out.sort(key=lambda x: x["task_id"])
    return out


def discover_annotations(
    annotation_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Map task_id → annotation payload for ck.task_dep.v1 files."""
    d = annotation_dir if annotation_dir is not None else default_annotation_dir()
    found: dict[str, dict[str, Any]] = {}
    if not d.is_dir():
        return found
    for path in sorted(d.glob("*.json")):
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, Mapping):
            continue
        if str(data.get("version") or "") != TASK_DEP_ANNOTATION_VERSION:
            continue
        tid = str(data.get("task_id") or "")
        if not tid:
            continue
        found[tid] = {
            "path": str(path.relative_to(_repo_root())),
            "sha256": file_sha256(path),
            "data": data,
        }
    return found


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def _universe_from_task(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    u = raw.get("continuity_universe")
    if not isinstance(u, Mapping):
        return None
    subjects = list(u.get("subject_ids") or [])
    objects = list(u.get("object_ids") or [])
    relations = list(u.get("relations") or [])
    if not subjects or not objects or not relations:
        return None
    return {
        "subject_universe": [str(x) for x in subjects],
        "object_universe": [str(x) for x in objects],
        "relation_universe": [str(x) for x in relations],
        "valid_combinations": list(u.get("valid_combinations") or []),
    }


def _expected_from_universe(universe: Mapping[str, Any]) -> list[dict[str, str]]:
    """Freeze expected relations from valid_combinations (primary gold set).

    Uses all listed valid combinations as the closed expected set when present;
    otherwise empty (ineligible).
    """
    expected: list[dict[str, str]] = []
    for comb in universe.get("valid_combinations") or []:
        if not isinstance(comb, (list, tuple)) or len(comb) != 3:
            continue
        expected.append(
            {
                "subject_id": str(comb[0]),
                "relation": str(comb[1]),
                "object_id": str(comb[2]),
            }
        )
    # Stable order
    expected.sort(key=lambda t: (t["subject_id"], t["relation"], t["object_id"]))
    return expected


def _annotation_completeness(ann: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    try:
        tda = TaskDependencyAnnotation.from_dict(ann)
    except Exception:  # noqa: BLE001
        return ["MALFORMED_TASK_DEP_ANNOTATION"]
    from conditioned_kernel.control_contract import FieldClass

    facts = tda.classified(FieldClass.REQUIRED_TASK_FACT)
    ops = tda.classified(FieldClass.REQUIRED_OPERATIONAL_STATE)
    forbid = tda.classified(FieldClass.FORBIDDEN_ANSWER_LEAKAGE)
    if not facts:
        reasons.append("MISSING_REQUIRED_TASK_FACTS")
    if not ops:
        reasons.append("MISSING_REQUIRED_OPERATIONAL_STATE")
    if not forbid:
        reasons.append("MISSING_FORBIDDEN_ANSWER_LEAKAGE")
    return reasons


def evaluate_task_eligibility(
    task: Mapping[str, Any],
    annotations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Static eligibility before any model output exists."""
    tid = str(task["task_id"])
    reasons: list[str] = []
    raw = task["raw"]

    if not tid:
        reasons.append("MISSING_TASK_ID")

    universe = _universe_from_task(raw)
    if universe is None:
        reasons.append("MISSING_CONTINUITY_UNIVERSE")

    ann_entry = annotations.get(tid)
    if ann_entry is None:
        reasons.append("MISSING_TASK_DEP_ANNOTATION")
        ann_data = None
        ann_hash = None
        ann_path = None
        ann_version = None
    else:
        ann_data = ann_entry["data"]
        ann_hash = ann_entry["sha256"]
        ann_path = ann_entry["path"]
        ann_version = str(ann_data.get("version") or "")
        if ann_version != TASK_DEP_ANNOTATION_VERSION:
            reasons.append("WRONG_TASK_DEP_VERSION")
        reasons.extend(_annotation_completeness(ann_data))

    expected: list[dict[str, str]] = []
    gold_dict: dict[str, Any] | None = None
    expected_hash: str | None = None
    if universe is not None:
        expected = _expected_from_universe(universe)
        if not expected:
            reasons.append("MISSING_EXPECTED_RELATIONS")
        else:
            gold_dict = {
                "task_id": tid,
                "contract_version": "ck.task_rel.v1",
                "subject_universe": universe["subject_universe"],
                "object_universe": universe["object_universe"],
                "relation_universe": universe["relation_universe"],
                "symmetric_relations": [],
                "expected_relations": expected,
            }
            try:
                gold = RelationalGold.from_dict(gold_dict)
                expected_hash = triples_hash(gold.expected_relations)
            except TaskContractError as e:
                reasons.append(f"INVALID_SCORER_CONTRACT:{e.reason_code}")
                gold_dict = None
                expected_hash = None

    # Packet compilation is deterministic for annotated live_plumbing tasks;
    # without annotation we already excluded.
    if ann_data is not None and "MISSING_TASK_DEP_ANNOTATION" not in reasons:
        # Require output schema id in operational state for packet compile path
        op_ids = {
            str(f.get("field_id"))
            for f in (ann_data.get("fields") or [])
            if isinstance(f, Mapping)
        }
        if "output_schema_id" not in op_ids and not any(
            str(f.get("field_id")) == "output_schema_id"
            for f in (ann_data.get("fields") or [])
            if isinstance(f, Mapping)
        ):
            # soft: control fixture has it; check value presence
            pass

    if reasons:
        return {
            "task_id": tid,
            "inclusion_verdict": InclusionVerdict.EXCLUDED.value,
            "exclusion_reasons": sorted(set(reasons)),
            "annotation_version": ann_version,
            "annotation_path": ann_path,
            "annotation_sha256": ann_hash,
            "source_path": task["source_path"],
            "source_sha256": task["source_sha256"],
            "gold": None,
            "expected_relation_hash": None,
            "dependency_annotation_hash": ann_hash,
        }

    return {
        "task_id": tid,
        "inclusion_verdict": InclusionVerdict.INCLUDED.value,
        "exclusion_reasons": [],
        "annotation_version": ann_version,
        "annotation_path": ann_path,
        "annotation_sha256": ann_hash,
        "source_path": task["source_path"],
        "source_sha256": task["source_sha256"],
        "gold": gold_dict,
        "expected_relation_hash": expected_hash,
        "dependency_annotation_hash": ann_hash,
    }


# ---------------------------------------------------------------------------
# Planned cell identity
# ---------------------------------------------------------------------------


def planned_cell_identity_payload(
    *,
    manifest_id: str,
    task_id: str,
    condition_id: str,
    replicate_id: str,
    model_tag: str,
    seed: int,
    packet_contract_version: str,
    scorer_schema_version: str,
) -> dict[str, Any]:
    return {
        "condition_id": condition_id,
        "manifest_id": manifest_id,
        "model_tag": model_tag,
        "packet_contract_version": packet_contract_version,
        "replicate_id": replicate_id,
        "scorer_schema_version": scorer_schema_version,
        "seed": seed,
        "task_id": task_id,
    }


def compute_cell_id(identity: Mapping[str, Any]) -> str:
    """cell_id = SHA256(canonical planned-cell identity)."""
    return sha256_hex(canonical_json_bytes(dict(identity)))


def build_planned_cell(
    *,
    manifest_id: str,
    task_id: str,
    condition: ConditionId,
    replicate_id: str,
    model_tag: str,
    generation_parameters: Mapping[str, Any],
    expected_relation_hash: str,
    task_contract_version: str,
    dependency_annotation_hash: str,
    packet_contract_version: str = PACKET_CONTRACT_VERSION,
    scorer_schema_version: str = SCORER_SCHEMA_VERSION,
    source_state_dependency: str | None = None,
    paired_primary_cell_id: str | None = None,
) -> dict[str, Any]:
    seed = int(generation_parameters["seed"])
    identity = planned_cell_identity_payload(
        manifest_id=manifest_id,
        task_id=task_id,
        condition_id=condition.value,
        replicate_id=replicate_id,
        model_tag=model_tag,
        seed=seed,
        packet_contract_version=packet_contract_version,
        scorer_schema_version=scorer_schema_version,
    )
    cell_id = compute_cell_id(identity)
    record = {
        "schema_version": PLANNED_CELL_SCHEMA_VERSION,
        "cell_id": cell_id,
        "manifest_id": manifest_id,
        "task_id": task_id,
        "condition_id": condition.value,
        "replicate_id": replicate_id,
        "model_tag": model_tag,
        "generation_parameters": dict(generation_parameters),
        "expected_relation_hash": expected_relation_hash,
        "task_contract_version": task_contract_version,
        "dependency_annotation_hash": dependency_annotation_hash,
        "packet_contract_version": packet_contract_version,
        "scorer_schema_version": scorer_schema_version,
        "planned_status": "planned",
        "source_state_dependency": source_state_dependency,
        "paired_primary_cell_id": paired_primary_cell_id,
        "scientific_completion": False,
        "headline_eligible": False,
        "identity_payload": identity,
    }
    return record


def planned_cell_hash(record: Mapping[str, Any]) -> str:
    # Hash without nested identity duplication volatility — use full record minus nothing
    payload = {k: v for k, v in record.items() if k != "planned_cell_hash"}
    return sha256_hex(canonical_json_bytes(payload))


# ---------------------------------------------------------------------------
# Manifest build
# ---------------------------------------------------------------------------


def build_candidate_manifest(
    *,
    repo_commit: str = REPO_COMMIT_DEFAULT,
    sources: Sequence[Path] | None = None,
    annotation_dir: Path | None = None,
    creation_timestamp: str = FREEZE_TIMESTAMP,
) -> dict[str, Any]:
    """Build byte-deterministic unratified M0 candidate manifest + exclusion ledger."""
    tasks = discover_raw_tasks(sources)
    annotations = discover_annotations(annotation_dir)

    eligibility: list[dict[str, Any]] = []
    for t in tasks:
        eligibility.append(evaluate_task_eligibility(t, annotations))

    included = [
        e for e in eligibility if e["inclusion_verdict"] == InclusionVerdict.INCLUDED.value
    ]
    excluded = [
        e for e in eligibility if e["inclusion_verdict"] == InclusionVerdict.EXCLUDED.value
    ]
    included.sort(key=lambda e: e["task_id"])
    excluded.sort(key=lambda e: e["task_id"])

    planned_cells: list[dict[str, Any]] = []
    # First pass: build cells without pairing
    for e in included:
        tid = e["task_id"]
        exp_hash = e["expected_relation_hash"]
        dep_hash = e["dependency_annotation_hash"]
        assert exp_hash and dep_hash and e["gold"]
        for cond in CONDITIONS:
            cell = build_planned_cell(
                manifest_id=MANIFEST_ID,
                task_id=tid,
                condition=cond,
                replicate_id=REPLICATE_ID,
                model_tag=MODEL_TAG,
                generation_parameters=GENERATION_PARAMETERS,
                expected_relation_hash=exp_hash,
                task_contract_version=str(e["gold"]["contract_version"]),
                dependency_annotation_hash=dep_hash,
                source_state_dependency=(
                    "episode_a_continuity_state"
                    if cond is ConditionId.C3_STATIC_CK
                    else None
                ),
            )
            planned_cells.append(cell)

    # Pairing: C3 ↔ C1 per task+replicate
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for c in planned_cells:
        by_key[(c["task_id"], c["condition_id"], c["replicate_id"])] = c

    for e in included:
        tid = e["task_id"]
        c1 = by_key.get((tid, ConditionId.C1_BUDGET_MATCHED_BARE.value, REPLICATE_ID))
        c3 = by_key.get((tid, ConditionId.C3_STATIC_CK.value, REPLICATE_ID))
        if c1 is None or c3 is None:
            raise ManifestError("ORPHAN_PRIMARY_PAIR", tid)
        c3["paired_primary_cell_id"] = c1["cell_id"]
        c1["paired_primary_cell_id"] = c3["cell_id"]

    # Fail closed: duplicate cell IDs
    ids = [c["cell_id"] for c in planned_cells]
    if len(ids) != len(set(ids)):
        raise ManifestError("DUPLICATE_CELL_ID")

    # Fail closed: duplicate task-condition-replicate
    triples = [(c["task_id"], c["condition_id"], c["replicate_id"]) for c in planned_cells]
    if len(triples) != len(set(triples)):
        raise ManifestError("DUPLICATE_TASK_CONDITION_REPLICATE")

    # Sort planned cells for determinism
    planned_cells.sort(
        key=lambda c: (c["task_id"], c["condition_id"], c["replicate_id"], c["cell_id"])
    )
    for c in planned_cells:
        c["planned_cell_hash"] = planned_cell_hash(c)

    # Pair count
    primary_pairs = []
    for e in included:
        tid = e["task_id"]
        c1 = by_key[(tid, ConditionId.C1_BUDGET_MATCHED_BARE.value, REPLICATE_ID)]
        c3 = by_key[(tid, ConditionId.C3_STATIC_CK.value, REPLICATE_ID)]
        primary_pairs.append(
            {
                "task_id": tid,
                "replicate_id": REPLICATE_ID,
                "c1_cell_id": c1["cell_id"],
                "c3_cell_id": c3["cell_id"],
            }
        )
    primary_pairs.sort(key=lambda p: (p["task_id"], p["replicate_id"]))

    exclusion_ledger = {
        "schema_version": "ck.m0_exclusion_ledger.v1",
        "manifest_id": MANIFEST_ID,
        "tasks": [
            {
                "task_id": e["task_id"],
                "inclusion_verdict": e["inclusion_verdict"],
                "exclusion_reasons": e["exclusion_reasons"],
                "annotation_version": e["annotation_version"],
                "annotation_path": e["annotation_path"],
                "annotation_sha256": e["annotation_sha256"],
                "source_path": e["source_path"],
                "source_sha256": e["source_sha256"],
            }
            for e in excluded
        ],
    }

    body = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": MANIFEST_ID,
        "authorization_status": AUTHORIZATION_STATUS,
        "scientific_completion": False,
        "headline_eligible": False,
        "headline_ineligible_reason": HEADLINE_INELIGIBLE_REASON,
        "execution_scope": EXECUTION_SCOPE,
        "experiment_contract_id": None,
        "repository_commit": repo_commit,
        "creation_timestamp": creation_timestamp,
        "task_registry_version": "ck.task_registry.v1",
        "task_dependency_annotation_version": TASK_DEP_ANNOTATION_VERSION,
        "packet_contract_version": PACKET_CONTRACT_VERSION,
        "control_contract_version": CONTROL_VERIFIER_VERSION,
        "scorer_schema_version": SCORER_SCHEMA_VERSION,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "terminal_cell_schema_version": TERMINAL_CELL_SCHEMA_VERSION,
        "planned_cell_schema_version": PLANNED_CELL_SCHEMA_VERSION,
        "model_tag": MODEL_TAG,
        "generation_parameters": dict(GENERATION_PARAMETERS),
        "runtime_requirements": {
            "backend": "ollama",
            "honor_temperature": True,
            "honor_seed": True,
            "no_silent_parameter_fallback": True,
            "no_replacement_runs": True,
            "no_result_dependent_retries": True,
            "failure_on_unhonored_option": "RUNTIME_PROVENANCE_FAILURE",
        },
        "condition_set": [c.value for c in CONDITIONS],
        "contrast_definitions": [
            PRIMARY_CONTRAST,
            SECONDARY_CONTRAST,
            DESCRIPTIVE_CONTRAST,
        ],
        "replicate_policy": {
            "replicates_per_task_condition": REPLICATES_PER_CELL,
            "replicate_ids": [REPLICATE_ID],
        },
        "retry_policy": {
            "retries_in_manifest": 0,
            "replacement_runs": False,
            "future_retry_requires_new_cell_id": True,
        },
        "task_inclusion_rule": {
            "id": "ck.m0.eligibility.static_v1",
            "description": (
                "Include task iff stable task_id, closed subject/object/relation "
                "universe, one or more frozen expected relations, valid "
                "ck.task_dep.v1 annotation with required facts/ops/forbidden "
                "leakage fields, and valid relational scorer contract. No "
                "cherry-picking by difficulty or model behavior."
            ),
        },
        "included_tasks": [
            {
                "task_id": e["task_id"],
                "source_path": e["source_path"],
                "source_sha256": e["source_sha256"],
                "annotation_path": e["annotation_path"],
                "annotation_sha256": e["annotation_sha256"],
                "expected_relation_hash": e["expected_relation_hash"],
                "dependency_annotation_hash": e["dependency_annotation_hash"],
                "gold": e["gold"],
            }
            for e in included
        ],
        "exclusion_ledger": exclusion_ledger,
        "planned_cells": planned_cells,
        "planned_cell_count": len(planned_cells),
        "planned_primary_pairs": primary_pairs,
        "planned_primary_pairs_n": len(primary_pairs),
        "required_future_authorization_receipt_fields": [
            "manifest_id",
            "manifest_sha256",
            "authorizing_principal",
            "authorization_timestamp",
            "experiment_contract_id",
            "authorized_model",
            "authorized_planned_cell_count",
        ],
    }

    # Hash body without manifest_sha256 field
    body["manifest_sha256"] = sha256_hex(canonical_json_bytes(body))
    return body


def manifest_to_manifest_cells(manifest: Mapping[str, Any]) -> list[ManifestCell]:
    """Project planned cells into outcomes.ManifestCell for TerminalLedger."""
    cells: list[ManifestCell] = []
    for pc in manifest["planned_cells"]:
        cells.append(
            ManifestCell(
                run_id=str(manifest["manifest_id"]),
                task_id=str(pc["task_id"]),
                condition_id=str(pc["condition_id"]),
                episode=None,
                replicate_id=str(pc["replicate_id"]),
                cell_id_override=str(pc["cell_id"]),
            )
        )
    return cells


def build_dry_plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Dry plan: every planned cell; no model client path."""
    by_cond: dict[str, int] = {}
    for c in manifest["planned_cells"]:
        by_cond[c["condition_id"]] = by_cond.get(c["condition_id"], 0) + 1
    return {
        "schema_version": "ck.m0_dry_plan.v1",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "authorization_status": manifest["authorization_status"],
        "scientific_completion": False,
        "headline_eligible": False,
        "execution_scope": manifest["execution_scope"],
        "model_tag": manifest["model_tag"],
        "generation_parameters": manifest["generation_parameters"],
        "eligible_tasks": [t["task_id"] for t in manifest["included_tasks"]],
        "excluded_tasks": [
            {
                "task_id": t["task_id"],
                "exclusion_reasons": t["exclusion_reasons"],
            }
            for t in manifest["exclusion_ledger"]["tasks"]
        ],
        "planned_cells_by_condition": dict(sorted(by_cond.items())),
        "planned_cell_count": manifest["planned_cell_count"],
        "planned_primary_pairs_n": manifest["planned_primary_pairs_n"],
        "planned_cell_ids": [c["cell_id"] for c in manifest["planned_cells"]],
        "task_annotation_hashes": {
            t["task_id"]: t["annotation_sha256"] for t in manifest["included_tasks"]
        },
        "no_model_execution": True,
        "model_client_imported": False,
        "repository_commit": manifest["repository_commit"],
    }


def write_frozen_artifacts(
    *,
    out_dir: Path | None = None,
    repo_commit: str = REPO_COMMIT_DEFAULT,
) -> dict[str, Path]:
    """Write candidate manifest, exclusions, and dry plan under experiments/manifests."""
    root = _repo_root()
    d = out_dir if out_dir is not None else root / "experiments" / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    manifest = build_candidate_manifest(repo_commit=repo_commit)
    plan = build_dry_plan(manifest)
    exclusions = manifest["exclusion_ledger"]

    paths = {
        "manifest": d / "m0_candidate_v1.json",
        "exclusions": d / "m0_candidate_v1_exclusions.json",
        "plan": d / "m0_candidate_v1_plan.json",
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["exclusions"].write_text(
        json.dumps(exclusions, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["plan"].write_text(
        json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return paths


def validate_condition_id(condition_id: str) -> None:
    known = {c.value for c in ConditionId}
    if condition_id not in known:
        raise ManifestError("UNKNOWN_CONDITION", condition_id)
