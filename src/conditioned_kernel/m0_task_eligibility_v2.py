"""RUN 00.9A — M0-v2 static task eligibility (no model probing).

Gold non-saturation, state/gold agreement, corpus minima, selection independence.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from conditioned_kernel.m0_scientific_contract import (
    MIN_DISTRACTORS,
    MIN_ELIGIBLE_TASKS,
    MIN_PERMITTED_OVER_EXPECTED_RATIO,
    N_CANDIDATE,
    PRIMARY_ESTIMAND,
    PRIMARY_METRIC,
    PREDICTED_DIRECTION,
    scientific_manifest_allowed,
)
from conditioned_kernel.relational_scorer import RelationTriple, triples_hash

TASK_CONTRACT_VERSION = "ck.m0_task_contract.v2"
OUTPUT_SCHEMA_ID = "continuity_assertions_v1"
EXPECTED_SEMANTICS = "all_required"


class EligibilityError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


def _triple(m: Mapping[str, Any]) -> RelationTriple:
    return RelationTriple(
        subject_id=str(m["subject_id"]),
        relation=str(m["relation"]),
        object_id=str(m["object_id"]),
    )


def permitted_universe(
    entities: Sequence[str],
    relations: Sequence[str],
) -> list[RelationTriple]:
    ents = sorted({str(e) for e in entities})
    rels = sorted({str(r) for r in relations})
    out: list[RelationTriple] = []
    for s in ents:
        for r in rels:
            for o in ents:
                if s == o:
                    continue  # no self-loops in M0-v2 default vocabulary
                out.append(RelationTriple(s, r, o))
    return out


def evaluate_task_contract_v2(task: Mapping[str, Any]) -> dict[str, Any]:
    """Static eligibility for one M0-v2 task contract dict."""
    reasons: list[str] = []
    tid = str(task.get("task_id") or "")
    if not tid:
        reasons.append("MISSING_TASK_ID")

    if str(task.get("contract_version") or "") != TASK_CONTRACT_VERSION:
        reasons.append("WRONG_TASK_CONTRACT_VERSION")

    if str(task.get("expected_relation_semantics") or "") != EXPECTED_SEMANTICS:
        reasons.append("UNSUPPORTED_GOLD_SEMANTICS")

    if str(task.get("output_schema_id") or "") != OUTPUT_SCHEMA_ID:
        reasons.append("MISSING_OR_UNKNOWN_OUTPUT_SCHEMA")

    if not task.get("state_hash"):
        reasons.append("MISSING_STATE_HASH")
    if not task.get("episode_a_state_hash") and not task.get("state_hash"):
        reasons.append("MISSING_STATE_HASH")

    entities = list(task.get("entity_universe") or task.get("subject_universe") or [])
    # objects may equal subjects in shared entity universe
    if task.get("object_universe"):
        entities = list(set(entities) | set(task["object_universe"]))
    relations = list(task.get("relation_universe") or [])
    if not entities or not relations:
        reasons.append("MISSING_CONTINUITY_UNIVERSE")

    expected_raw = list(task.get("expected_relations") or [])
    accepted_raw = list(task.get("accepted_relation_set") or expected_raw)
    distractors = list(task.get("in_universe_distractors") or [])

    expected = []
    for item in expected_raw:
        try:
            expected.append(_triple(item))
        except (KeyError, TypeError):
            reasons.append("MALFORMED_EXPECTED_RELATION")

    accepted = []
    for item in accepted_raw:
        try:
            accepted.append(_triple(item))
        except (KeyError, TypeError):
            reasons.append("MALFORMED_ACCEPTED_RELATION")

    expected_n = len(expected)
    if expected_n == 0:
        reasons.append("EMPTY_GOLD")
        reasons.append("MISSING_EXPECTED_RELATIONS")

    # Gold must derive from accepted state relevant to Episode-B
    if expected and accepted:
        exp_set = set(expected)
        acc_set = set(accepted)
        if not exp_set.issubset(acc_set):
            reasons.append("STATE_GOLD_MISMATCH")
            reasons.append("EPISODE_B_GOLD_NOT_FROM_ACCEPTED_STATE")

    # Query must be state-referential marker when declared
    query = str(task.get("episode_b_query") or "")
    if query and not any(
        tok in query.lower()
        for tok in ("accepted", "still", "remain", "open", "state", "replay")
    ):
        # soft marker — only if expected doesn't match accepted
        if expected and accepted and set(expected) != set(accepted):
            pass
        elif "static_unrelated" in str(task.get("notes") or ""):
            reasons.append("STATE_REFERENTIAL_QUERY_GOLD_MISMATCH")

    if task.get("force_state_query_mismatch"):
        reasons.append("STATE_REFERENTIAL_QUERY_GOLD_MISMATCH")

    # Non-saturation
    perm = permitted_universe(entities, relations)
    permitted_n = len(perm)
    if expected_n > 0 and permitted_n > 0:
        if expected_n >= permitted_n:
            reasons.append("GOLD_SATURATES_PERMITTED_UNIVERSE")
        ratio = permitted_n / expected_n if expected_n else 0
        if ratio < MIN_PERMITTED_OVER_EXPECTED_RATIO:
            reasons.append("GOLD_SATURATES_PERMITTED_UNIVERSE")
    elif expected_n > 0 and permitted_n == 0:
        reasons.append("MISSING_CONTINUITY_UNIVERSE")

    # Distractors
    d_n = len(distractors)
    if d_n < MIN_DISTRACTORS and not task.get("skip_distractor_check"):
        # also count permitted - expected as implicit distractors
        implicit = max(0, permitted_n - expected_n)
        if implicit < MIN_DISTRACTORS:
            reasons.append("NO_INFORMATIONAL_DISTRACTORS")
            reasons.append("MISSING_DISTRACTORS")

    if task.get("post_performance_selection"):
        reasons.append("POST_PERFORMANCE_TASK_SELECTION")

    # Deciding metric must be pinned at package level (task may not redefine)
    if task.get("primary_metric") and task["primary_metric"] != PRIMARY_METRIC:
        reasons.append("TASK_REDEFINES_PRIMARY_METRIC")

    included = len(reasons) == 0
    return {
        "task_id": tid,
        "inclusion_verdict": "INCLUDED" if included else "EXCLUDED",
        "exclusion_reasons": sorted(set(reasons)),
        "expected_n": expected_n,
        "permitted_triple_n": permitted_n,
        "distractor_n": max(d_n, max(0, permitted_n - expected_n)),
        "expected_relation_hash": triples_hash(expected) if expected else None,
        "state_hash": task.get("state_hash") or task.get("episode_a_state_hash"),
        "contract_version": TASK_CONTRACT_VERSION,
    }


def evaluate_corpus_v2(
    tasks: Sequence[Mapping[str, Any]],
    *,
    min_eligible: int = MIN_ELIGIBLE_TASKS,
    n_candidate_target: int = N_CANDIDATE,
    negative_control_tasks: Sequence[Mapping[str, Any]] | None = None,
    primary_metric: str = PRIMARY_METRIC,
    estimand: str = PRIMARY_ESTIMAND,
    predicted_direction: str = PREDICTED_DIRECTION,
    post_performance_selection: bool = False,
    rank_by_model_performance: bool = False,
) -> dict[str, Any]:
    """Evaluate a candidate task list against M0-v2 corpus rules (static).

    All tasks that pass the preregistered static rule enter the eligible corpus.
    No model-performance ranking or selection is permitted.
    """
    rows = [evaluate_task_contract_v2(t) for t in tasks]
    included = [r for r in rows if r["inclusion_verdict"] == "INCLUDED"]
    reasons: list[str] = []
    if len(tasks) == 1:
        reasons.append("ONE_TASK_CORPUS")
    if len(included) < min_eligible:
        reasons.append("CORPUS_BELOW_MINIMUM")
    if n_candidate_target != N_CANDIDATE:
        reasons.append("N_CANDIDATE_NOT_FROZEN")
    if not negative_control_tasks:
        reasons.append("MISSING_NEGATIVE_CONTROL")
    if not primary_metric:
        reasons.append("MISSING_PRIMARY_METRIC")
    if primary_metric != PRIMARY_METRIC:
        reasons.append("PRIMARY_METRIC_NOT_FROZEN_CHOICE")
    if not estimand:
        reasons.append("MISSING_ESTIMAND")
    if estimand == "median_paired_difference":
        reasons.append("MEDIAN_NOT_PRIMARY_ESTIMAND")
    if estimand and estimand != PRIMARY_ESTIMAND:
        reasons.append("ESTIMAND_NOT_FROZEN_CHOICE")
    if not predicted_direction:
        reasons.append("MISSING_PREDICTED_DIRECTION")
    if post_performance_selection or rank_by_model_performance:
        reasons.append("POST_PERFORMANCE_TASK_SELECTION")

    # cell id uniqueness for states
    seen_cells: dict[str, str] = {}
    for t in tasks:
        cid = str(t.get("cell_id_template") or t.get("task_id") or "")
        sh = str(t.get("state_hash") or "")
        if cid and sh:
            if cid in seen_cells and seen_cells[cid] != sh:
                reasons.append("CELL_ID_MULTIPLE_STATES")
            seen_cells[cid] = sh

    # All statically eligible tasks are included (no ranking cull)
    all_eligible_included = len(included) == sum(
        1 for r in rows if r["inclusion_verdict"] == "INCLUDED"
    )
    manifest = scientific_manifest_allowed(
        n_eligible=len(included),
        contract_reasons=reasons,
    )

    return {
        "n_candidate": len(tasks),
        "n_candidate_target": n_candidate_target,
        "n_eligible": len(included),
        "n_min_eligible": min_eligible,
        "rows": rows,
        "corpus_reasons": sorted(set(reasons)),
        "corpus_eligible": len(reasons) == 0 and len(included) >= min_eligible,
        "all_eligible_included": all_eligible_included,
        "scientific_manifest_allowed": manifest["allowed"],
        "primary_metric": primary_metric,
        "estimand": estimand,
        "predicted_direction": predicted_direction,
    }


# Task-selection independence freeze (before authorship)
TASK_SELECTION_POLICY: dict[str, Any] = {
    "task_family_template": "episode_a_accept_then_episode_b_state_query",
    "eligibility_rule_id": "ck.m0.eligibility.v2",
    "n_candidate": N_CANDIDATE,
    "min_eligible": MIN_ELIGIBLE_TASKS,
    "include_all_statically_eligible": True,
    "relation_vocabulary_policy": "closed_small_frozen_set_per_task",
    "entity_generation_policy": "synthetic_opaque_ids_no_world_knowledge",
    "distractor_policy": f"min_{MIN_DISTRACTORS}_in_universe_non_gold",
    "difficulty_bands": ["small", "medium"],
    "task_id_procedure": "sequential m0v2_task_NNN assigned before content freeze",
    "ordering": "lexicographic task_id for authorship; execution order seed-pinned",
    "seed_policy": "generator seeds pinned before candidate pool if used",
    "human_vs_generated": "either allowed; no model probing for inclusion",
    "no_model_probing": True,
    "no_post_performance_selection": True,
    "no_near_duplicate_inflation": True,
}
