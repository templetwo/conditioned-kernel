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
FREEZE_TIMESTAMP = "2026-07-27T12:00:00Z"
REPO_COMMIT_DEFAULT = "a5d8ed03b40373d3c84954da03f942066ed1eaf4"

# M0 v1: only conjunctive gold is eligible.
GOLD_SEMANTICS_ALL_REQUIRED = "all_required"
GOLD_SEMANTICS_REJECTED = frozenset(
    {"one_of", "choose_any", "alternatives", "unspecified", ""}
)
KNOWN_OUTPUT_SCHEMA_IDS = frozenset({"continuity_assertions_v1"})

# Instruction text must require the full conjunctive set when expected_n > 1.
_ALL_REQUIRED_INSTRUCTION_MARKERS = (
    "every supported continuity assertion",
    "all supported continuity assertion",
    "return every supported",
    "emit every supported",
    "full conjunctive set",
    "do not omit any supported relation",
)
_ONE_OF_INSTRUCTION_MARKERS = (
    "select a valid",
    "choose one",
    "choose a valid",
    "one valid",
    "a single valid",
    "pick one",
)

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
    """All discovered task sources (order does not affect manifest identity)."""
    root = _repo_root()
    sources: list[Path] = [
        root / "experiments" / "probes" / "continuity_tasks.json",
        root / "experiments" / "probes" / "live_plumbing_task.json",
    ]
    m0_dir = root / "experiments" / "probes" / "m0_task_contracts"
    if m0_dir.is_dir():
        sources.extend(sorted(m0_dir.glob("*.json")))
    return sources


def default_annotation_dirs() -> list[Path]:
    root = _repo_root()
    return [
        root / "tests" / "fixtures",
        root / "tests" / "fixtures" / "m0_task_dep",
    ]


def default_annotation_dir() -> Path:
    """Primary annotation directory (backward compatible)."""
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
    annotation_dirs: Sequence[Path] | None = None,
) -> dict[str, dict[str, Any]]:
    """Map task_id → annotation payload for ck.task_dep.v1 files."""
    if annotation_dirs is not None:
        dirs = list(annotation_dirs)
    elif annotation_dir is not None:
        dirs = [annotation_dir]
    else:
        dirs = default_annotation_dirs()
    found: dict[str, dict[str, Any]] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.json")):
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
            # Later dirs / paths overwrite earlier only if same tid — last sorted wins
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


def _normalize_expected(items: Sequence[Any]) -> list[dict[str, str]]:
    expected: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, Mapping):
            expected.append(
                {
                    "subject_id": str(item["subject_id"]),
                    "relation": str(item.get("relation") or ""),
                    "object_id": str(item["object_id"]),
                }
            )
        elif isinstance(item, (list, tuple)) and len(item) == 3:
            expected.append(
                {
                    "subject_id": str(item[0]),
                    "relation": str(item[1]),
                    "object_id": str(item[2]),
                }
            )
    expected = [e for e in expected if e["subject_id"] and e["relation"] and e["object_id"]]
    expected.sort(key=lambda t: (t["subject_id"], t["relation"], t["object_id"]))
    return expected


def _expected_from_task(
    raw: Mapping[str, Any], universe: Mapping[str, Any] | None
) -> list[dict[str, str]]:
    """Prefer explicit expected_relations; never silently treat valid_combinations
    as conjunctive gold unless the task also declares all_required semantics and
    provides explicit expected_relations OR m0_contract flag.

    valid_combinations alone without expected_relations → empty (not inventing).
    """
    if "expected_relations" in raw and raw["expected_relations"] is not None:
        return _normalize_expected(list(raw.get("expected_relations") or []))
    # Explicit m0 contracts may still list only valid_combinations when
    # expected_relation_semantics=all_required and instruction_aligned is set.
    if (
        str(raw.get("expected_relation_semantics") or "") == GOLD_SEMANTICS_ALL_REQUIRED
        and bool(raw.get("valid_combinations_are_conjunctive_expected"))
        and universe is not None
    ):
        return _normalize_expected(list(universe.get("valid_combinations") or []))
    return []


def _instruction_text(raw: Mapping[str, Any]) -> str:
    parts: list[str] = []
    ea = raw.get("episode_a") or {}
    eb = raw.get("episode_b") or {}
    if isinstance(ea, Mapping):
        parts.append(str(ea.get("prompt") or ""))
        parts.append(str(ea.get("objective") or ""))
    if isinstance(eb, Mapping):
        parts.append(str(eb.get("prompt") or ""))
    parts.append(str(raw.get("prompt") or ""))
    parts.append(str(raw.get("objective") or ""))
    return " ".join(parts).lower()


def _instruction_requires_all_supported(text: str) -> bool:
    return any(m in text for m in _ALL_REQUIRED_INSTRUCTION_MARKERS)


def _instruction_suggests_one_of(text: str) -> bool:
    return any(m in text for m in _ONE_OF_INSTRUCTION_MARKERS)


def _resolve_gold_semantics(raw: Mapping[str, Any]) -> str:
    """Return normalized semantics string (may be empty/unspecified/unknown)."""
    if "expected_relation_semantics" not in raw:
        # Free-text corpus tasks with answer_key alternatives
        eb = raw.get("episode_b") or {}
        if isinstance(eb, Mapping) and eb.get("answer_key"):
            return "unspecified"
        return "unspecified"
    val = str(raw.get("expected_relation_semantics") or "").strip().lower()
    return val


def _annotation_field_value(ann: Mapping[str, Any], field_id: str) -> str | None:
    for f in ann.get("fields") or []:
        if isinstance(f, Mapping) and str(f.get("field_id")) == field_id:
            v = str(f.get("value") or "").strip()
            return v or None
    return None


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


def _try_packet_compile(ann_data: Mapping[str, Any]) -> str | None:
    """Return reason code if packet compile fails; None if ok."""
    try:
        from conditioned_kernel.control_contract import (
            RuntimeSettings,
            compile_condition_packet,
            validate_annotation,
        )

        tda = TaskDependencyAnnotation.from_dict(ann_data)
        validate_annotation(tda)
        rt = RuntimeSettings(
            model_tag=MODEL_TAG,
            temperature=TEMPERATURE,
            seed=SEED,
            num_ctx=NUM_CTX,
        )
        # Deterministic compile for C3 (includes state) proves packet path.
        compile_condition_packet(ConditionId.C3_STATIC_CK, tda, rt)
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "reason_code", None) or type(e).__name__
        return f"PACKET_COMPILE_FAILED:{code}"
    return None


def evaluate_task_eligibility(
    task: Mapping[str, Any],
    annotations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Static eligibility before any model output exists (RUN 00.6F.1)."""
    tid = str(task["task_id"])
    reasons: list[str] = []
    raw = task["raw"]

    if not tid:
        reasons.append("MISSING_TASK_ID")

    # Free-text continuity corpus (answer_key) cannot supply closed relation gold
    # without redesign — do not invent triples.
    eb = raw.get("episode_b") or {}
    if isinstance(eb, Mapping) and eb.get("answer_key") and not raw.get(
        "continuity_universe"
    ):
        reasons.append("TASK_REQUIRES_REDESIGN")
        reasons.append("AMBIGUOUS_EXPECTED_RELATIONS")

    universe = _universe_from_task(raw)
    if universe is None:
        reasons.append("MISSING_CONTINUITY_UNIVERSE")

    instr_early = _instruction_text(raw)
    # Choose-one instructions + multi valid_combinations without all_required contract
    if universe is not None:
        n_valid = len(universe.get("valid_combinations") or [])
        if n_valid > 1 and (
            _instruction_suggests_one_of(instr_early)
            or "select a valid closed-set" in instr_early
        ):
            if not _instruction_requires_all_supported(instr_early):
                reasons.append("INSTRUCTION_GOLD_SEMANTICS_MISMATCH")

    semantics = _resolve_gold_semantics(raw)
    if semantics in GOLD_SEMANTICS_REJECTED or semantics == "unspecified":
        if semantics in {"one_of", "choose_any", "alternatives"}:
            reasons.append("UNSUPPORTED_GOLD_SEMANTICS")
        elif semantics == "unspecified" or semantics == "":
            reasons.append("UNSUPPORTED_GOLD_SEMANTICS")
        else:
            reasons.append("UNSUPPORTED_GOLD_SEMANTICS")
    elif semantics != GOLD_SEMANTICS_ALL_REQUIRED:
        reasons.append("UNSUPPORTED_GOLD_SEMANTICS")

    ann_entry = annotations.get(tid)
    ann_data = None
    ann_hash = None
    ann_path = None
    ann_version = None
    output_schema_id: str | None = None
    if ann_entry is None:
        reasons.append("MISSING_TASK_DEP_ANNOTATION")
    else:
        ann_data = ann_entry["data"]
        ann_hash = ann_entry["sha256"]
        ann_path = ann_entry["path"]
        ann_version = str(ann_data.get("version") or "")
        if ann_version != TASK_DEP_ANNOTATION_VERSION:
            reasons.append("WRONG_TASK_DEP_VERSION")
        reasons.extend(_annotation_completeness(ann_data))
        output_schema_id = _annotation_field_value(ann_data, "output_schema_id")
        # Task-level override
        if raw.get("output_schema_id"):
            output_schema_id = str(raw["output_schema_id"]).strip() or output_schema_id

    # Task-level output_schema_id if annotation missing field
    if not output_schema_id and raw.get("output_schema_id"):
        output_schema_id = str(raw["output_schema_id"]).strip() or None

    if not output_schema_id:
        reasons.append("MISSING_OUTPUT_SCHEMA_ID")
    elif output_schema_id not in KNOWN_OUTPUT_SCHEMA_IDS:
        reasons.append("UNKNOWN_OUTPUT_SCHEMA_ID")

    expected: list[dict[str, str]] = []
    gold_dict: dict[str, Any] | None = None
    expected_hash: str | None = None
    if universe is not None:
        expected = _expected_from_task(raw, universe)
        if not expected:
            # Do not silently promote valid_combinations
            if universe.get("valid_combinations") and "expected_relations" not in raw:
                reasons.append("AMBIGUOUS_EXPECTED_RELATIONS")
            reasons.append("MISSING_EXPECTED_RELATIONS")
        else:
            instr = _instruction_text(raw)
            if len(expected) > 1:
                if _instruction_suggests_one_of(instr) and not _instruction_requires_all_supported(
                    instr
                ):
                    reasons.append("INSTRUCTION_GOLD_SEMANTICS_MISMATCH")
                elif not _instruction_requires_all_supported(instr):
                    reasons.append("INSTRUCTION_GOLD_SEMANTICS_MISMATCH")
            if semantics == GOLD_SEMANTICS_ALL_REQUIRED and "INSTRUCTION_GOLD_SEMANTICS_MISMATCH" not in reasons:
                gold_dict = {
                    "task_id": tid,
                    "contract_version": "ck.task_rel.v1",
                    "subject_universe": universe["subject_universe"],
                    "object_universe": universe["object_universe"],
                    "relation_universe": universe["relation_universe"],
                    "symmetric_relations": [],
                    "expected_relations": expected,
                    "expected_relation_semantics": GOLD_SEMANTICS_ALL_REQUIRED,
                }
                try:
                    gold = RelationalGold.from_dict(gold_dict)
                    expected_hash = triples_hash(gold.expected_relations)
                except TaskContractError as e:
                    reasons.append(f"INVALID_SCORER_CONTRACT:{e.reason_code}")
                    gold_dict = None
                    expected_hash = None

    # Deterministic packet compilation required for inclusion
    if ann_data is not None and "MISSING_TASK_DEP_ANNOTATION" not in reasons:
        compile_fail = _try_packet_compile(ann_data)
        if compile_fail:
            reasons.append(compile_fail)

    task_contract_hash = sha256_hex(canonical_json_bytes(dict(raw)))

    base_meta = {
        "task_id": tid,
        "annotation_version": ann_version,
        "annotation_path": ann_path,
        "annotation_sha256": ann_hash,
        "source_path": task["source_path"],
        "source_sha256": task["source_sha256"],
        "expected_relation_semantics": semantics or "unspecified",
        "expected_relation_count": len(expected),
        "identifier_universe_count": (
            len(set(universe["subject_universe"]) | set(universe["object_universe"]))
            if universe
            else 0
        ),
        "relation_universe_count": (
            len(universe["relation_universe"]) if universe else 0
        ),
        "output_schema_id": output_schema_id,
        "task_contract_hash": task_contract_hash,
        "dependency_annotation_hash": ann_hash,
    }

    if reasons:
        return {
            **base_meta,
            "inclusion_verdict": InclusionVerdict.EXCLUDED.value,
            "exclusion_reasons": sorted(set(reasons)),
            "gold": None,
            "expected_relation_hash": None,
        }

    return {
        **base_meta,
        "inclusion_verdict": InclusionVerdict.INCLUDED.value,
        "exclusion_reasons": [],
        "gold": gold_dict,
        "expected_relation_hash": expected_hash,
    }


def build_corpus_eligibility_rows(
    *,
    sources: Sequence[Path] | None = None,
    annotation_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """One row per discovered task for human review tables."""
    tasks = discover_raw_tasks(sources)
    annotations = discover_annotations(annotation_dir=annotation_dir)
    rows = [evaluate_task_eligibility(t, annotations) for t in tasks]
    rows.sort(key=lambda r: r["task_id"])
    return rows


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
                "universe, explicit conjunctive expected relations with "
                "expected_relation_semantics=all_required, instruction text that "
                "requires every supported assertion when expected_n>1, "
                "nonempty known output_schema_id, valid ck.task_dep.v1 "
                "annotation (facts/ops/forbidden leakage), deterministic packet "
                "compile, and valid relational scorer contract. Never silently "
                "treat valid_combinations as conjunctive gold. No cherry-picking."
            ),
            "gold_semantics_m0_v1": GOLD_SEMANTICS_ALL_REQUIRED,
            "known_output_schema_ids": sorted(KNOWN_OUTPUT_SCHEMA_IDS),
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
                "expected_relation_semantics": e.get(
                    "expected_relation_semantics"
                ),
                "output_schema_id": e.get("output_schema_id"),
                "task_contract_hash": e.get("task_contract_hash"),
                "gold": e["gold"],
            }
            for e in included
        ],
        "discovery_summary": {
            "discovered_n": len(eligibility),
            "included_n": len(included),
            "excluded_n": len(excluded),
        },
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


class FrozenArtifactError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


# Retired 00.6F.1 candidate — never overwrite; never ratify.
RETIRED_MANIFEST_ID = "ck.m0.candidate.v1"
RETIRED_MANIFEST_SHA256 = (
    "9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922"
)


def write_frozen_artifacts(
    *,
    out_dir: Path | None = None,
    repo_commit: str = REPO_COMMIT_DEFAULT,
    allow_identical_rewrite: bool = True,
    force_supersession: bool = False,
    supersession_id: str | None = None,
) -> dict[str, Path]:
    """Write candidate manifest, exclusions, and dry plan under experiments/manifests.

    RUN 00.8A: refuse silent overwrite when existing bytes differ.
    Identical rewrite of the same content is allowed when allow_identical_rewrite.
    force_supersession writes a new ID/filename and retains the prior artifact.
    """
    root = _repo_root()
    d = out_dir if out_dir is not None else root / "experiments" / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    manifest = build_candidate_manifest(repo_commit=repo_commit)
    plan = build_dry_plan(manifest)
    exclusions = manifest["exclusion_ledger"]

    manifest_name = "m0_candidate_v1.json"
    if force_supersession:
        sid = supersession_id or f"m0_candidate_superseded_{manifest['manifest_sha256'][:12]}"
        manifest_name = f"{sid}.json"
        manifest = dict(manifest)
        manifest["supersedes_manifest_id"] = RETIRED_MANIFEST_ID
        manifest["supersedes_manifest_sha256"] = RETIRED_MANIFEST_SHA256
        # re-hash after supersession fields
        body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        manifest["manifest_sha256"] = sha256_hex(canonical_json_bytes(body))
        plan = build_dry_plan(manifest)

    paths = {
        "manifest": d / manifest_name,
        "exclusions": d / manifest_name.replace(".json", "_exclusions.json"),
        "plan": d / manifest_name.replace(".json", "_plan.json"),
    }

    new_bytes = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    if paths["manifest"].is_file() and not force_supersession:
        old = paths["manifest"].read_bytes()
        if old != new_bytes:
            raise FrozenArtifactError(
                "FROZEN_ARTIFACT_OVERWRITE_REFUSED",
                f"refusing to overwrite {paths['manifest']} with different bytes; "
                "use force_supersession=True to retain prior artifact under a new name",
            )
        if not allow_identical_rewrite:
            raise FrozenArtifactError(
                "FROZEN_ARTIFACT_EXISTS",
                str(paths["manifest"]),
            )
        # identical — no write needed for manifest; still refresh companions
    else:
        paths["manifest"].write_bytes(new_bytes)

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
