"""RUN 00.9A.1 — M0-v2 scientific contract (static freeze; no model execution).

Fail-closed leakage companion; mean paired estimand; delta_m0; NC decision rule.
Does not authorize M0 execution or corpus construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

CONTRACT_VERSION = "ck.m0_scientific_contract.v2.1"
CONTRACT_AMENDMENT = "RUN_00_9A_1"
RETIRED_CANDIDATE_ID = "ck.m0.candidate.v1"
RETIRED_CANDIDATE_SHA256 = (
    "9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922"
)

# Frozen primary metric (single deciding metric — no post-run switching)
PRIMARY_METRIC = "exact_relation_set_match"
SECONDARY_METRIC = "primary_score"
# Mean of paired exact-match differences (descriptive; not asymptotic)
PRIMARY_ESTIMAND = "mean_paired_difference"
LEGACY_MEDIAN_ESTIMAND = "median_paired_difference"  # rejected as primary
PREDICTED_DIRECTION = "C3_greater_than_C1"
DELTA_M0 = 0.25  # minimally relevant effect; at N=12 → 3 net task-pair wins
N_CANDIDATE = 24
MIN_ELIGIBLE_TASKS = 12
N_MIN_ELIGIBLE = MIN_ELIGIBLE_TASKS
MIN_DISTRACTORS = 2
MIN_PERMITTED_OVER_EXPECTED_RATIO = 2.0  # permitted_triple_n >= 2 * expected_n
REPLICATE_COUNT = 1
RETRIES = 0
PRIMARY_NEGATIVE_CONTROL = "scrambled_state"
SECONDARY_INTEGRITY_CONTROL = "aa_serialization"
C3_REQUIRED_REPRESENTATION = "structured_state_v1"
ORDERING_SEED_REQUIRED = True
COUNTERBALANCE_C1_BEFORE_C3_FRACTION = 0.5


class ClaimLevel(str, Enum):
    A_INSTRUMENT = "A_instrument"
    B_CELL_OBSERVATION = "B_cell_observation"
    C_TASK_PAIR = "C_task_pair"
    D_CORPUS_M0 = "D_corpus_m0"
    E_GENERAL_THESIS = "E_general_thesis"


class DecisionOutcome(str, Enum):
    SUPPORT_CONTINUATION = "support_continuation"
    INCONCLUSIVE = "inconclusive"
    WEAKEN_HYPOTHESIS = "weaken_hypothesis"
    INVALIDATE_EXPERIMENT = "invalidate_experiment"
    PIPELINE_ARTIFACT = "pipeline_artifact"


class ContractError(ValueError):
    def __init__(self, reason_code: str, message: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


# ---------------------------------------------------------------------------
# Claim ladder
# ---------------------------------------------------------------------------

CLAIM_LADDER: dict[str, dict[str, str]] = {
    ClaimLevel.A_INSTRUMENT.value: {
        "statement": (
            "The governed execution pipeline runs and retains truthful evidence."
        ),
        "status": "established_by_commissioning",
        "m0_v2_tests": "no",
    },
    ClaimLevel.B_CELL_OBSERVATION.value: {
        "statement": (
            "A particular C3 cell scored differently from its paired control."
        ),
        "status": "descriptive_only",
        "m0_v2_tests": "diagnostic",
    },
    ClaimLevel.C_TASK_PAIR.value: {
        "statement": (
            "Structured replay changed performance on one frozen task pair under "
            "one model snapshot."
        ),
        "status": "task_level",
        "m0_v2_tests": "yes",
    },
    ClaimLevel.D_CORPUS_M0.value: {
        "statement": (
            "Across the preregistered frozen task corpus, the mean paired "
            "exact-set-match difference met the preregistered continuation "
            "threshold under the frozen model/runtime contract and validity gates."
        ),
        "status": "max_licensed_by_m0_v2",
        "m0_v2_tests": "yes_primary",
    },
    ClaimLevel.E_GENERAL_THESIS.value: {
        "statement": (
            "Broader claim about substrate-owned continuity as a general mechanism."
        ),
        "status": "not_licensed_by_m0_v2",
        "m0_v2_tests": "no",
        "requires_for_E": (
            "Independent multi-model replication, multi-host runtime, multi-corpus "
            "families, and preregistered cross-lab replications beyond D."
        ),
    },
}


# ---------------------------------------------------------------------------
# Condition supersession
# ---------------------------------------------------------------------------

CONDITION_DEFINITIONS_V2: dict[str, dict[str, Any]] = {
    "C0_bare": {
        "name": "Natural baseline",
        "supplies": "Episode-B task instructions and current query only.",
        "must_not": "prior accepted state, accepted_relations, gold triples",
        "role": "descriptive_baseline_confounded",
    },
    "C1_budget_matched_bare": {
        "name": "Flat state-mass control",
        "supplies": (
            "Same candidate state items and comparable non-answer informational mass "
            "as C3, with structure that identifies accepted relations destroyed "
            "(deterministic noninformative reassignment or permutation)."
        ),
        "must_not": (
            "canonical gold triples; mechanically complete recipe whose only "
            "possible result is the gold set; model-visible condition identity"
        ),
        "role": "primary_paired_control",
        "supersedes": [
            "RUN 00.6D/00.6F C1 as mere byte-matched bare without state-mass content",
            "any C1 definition that exposes accepted relations",
        ],
    },
    "C2_instruction_identical": {
        "name": "Instruction and serialization control",
        "supplies": (
            "Operational instructions, schema, packet envelope, formatting, and "
            "non-state metadata of C3 without accepted relational state."
        ),
        "must_not": "accepted relation set",
        "role": "secondary_diagnostic_control",
    },
    "C3_static_ck": {
        "name": "Structured verified continuity",
        "supplies": (
            "Replay-derived structured representation of the actually accepted "
            "Episode-A state under representation=structured_state_v1, distinct "
            "from the required output schema; model must transform state into "
            "the requested answer."
        ),
        "must_not": (
            "byte-identical scorer triples; output-schema serialization of gold; "
            "copy-ready expected_relations field; complete output-ready rendering"
        ),
        "role": "treatment",
        "required_representation": C3_REQUIRED_REPRESENTATION,
        "hard_invariant": "GOLD_OUTPUT_READY_IN_TREATMENT is mandatory exclusion",
    },
    "scrambled_state": {
        "name": "Primary negative control (scrambled-state)",
        "supplies": (
            "Same structure, mass, vocabulary, candidate count, status-symbol mass, "
            "packet depth, and byte target as C3 where enforceable; accepted-state "
            "mapping deterministically permuted so it does not match Episode A."
        ),
        "role": "primary_negative_control",
        "diagnoses": "format/structure benefit independent of true accepted state",
    },
    "aa_serialization": {
        "name": "A/A serialization integrity control",
        "supplies": "Two independently compiled but semantically identical controls.",
        "role": "secondary_integrity_control",
        "diagnoses": "unexplained pipeline/runtime asymmetry",
    },
}

PRIMARY_CONTRAST = {
    "treatment": "C3_static_ck",
    "control": "C1_budget_matched_bare",
    "isolates": (
        "structured accepted-state mapping vs flat state-mass without that mapping"
    ),
    "primary_negative_control": PRIMARY_NEGATIVE_CONTROL,
    "secondary_integrity_control": SECONDARY_INTEGRITY_CONTROL,
}


# ---------------------------------------------------------------------------
# Estimand and decision rule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EstimandContract:
    """Frozen primary estimand for M0-v2 (descriptive paired corpus estimand)."""

    unit_of_analysis: str = "eligible_task"
    treatment: str = "C3_static_ck"
    paired_control: str = "C1_budget_matched_bare"
    task_level_outcome: str = PRIMARY_METRIC  # exact_relation_set_match as 0/1
    paired_difference: str = "D_i = Y_i(C3) - Y_i(C1)"
    d_i_range: str = "{-1, 0, 1}"
    corpus_aggregate: str = PRIMARY_ESTIMAND  # mean_paired_difference
    delta_m0: float = DELTA_M0
    predicted_direction: str = PREDICTED_DIRECTION
    missing_pair_handling: str = (
        "exclude task from primary estimand; block scientific headline "
        "if primary_pair_coverage < 1.0"
    )
    failure_handling: str = (
        "null Y when terminal not SCORED; D_i undefined → task excluded from "
        "mean; incomplete coverage invalidates primary claim"
    )
    replicate_handling: str = (
        f"exactly {REPLICATE_COUNT} replicate per task-condition; no retries; "
        "no independent-replication claim from identical deterministic reruns"
    )
    min_tasks_for_meaningful_statistic: int = MIN_ELIGIBLE_TASKS
    uncertainty_policy: str = (
        "descriptive only: report mean D and exact task-level table; "
        "not an asymptotic estimate; no p-values as primary decision"
    )
    justification: str = (
        "Because D_i ∈ {-1,0,1}, mean_i(D_i) equals the net fraction of "
        "task-pair wins for C3 over C1. Descriptive paired corpus estimand. "
        "Median is rejected as primary: it can discard a net-positive "
        "configuration (e.g. 4 wins, 1 loss, 7 ties → median 0)."
    )


@dataclass(frozen=True)
class DecisionRule:
    primary_metric: str = PRIMARY_METRIC
    secondary_metric: str = SECONDARY_METRIC
    estimand: str = PRIMARY_ESTIMAND
    delta_m0: float = DELTA_M0
    direction: str = PREDICTED_DIRECTION
    primary_negative_control: str = PRIMARY_NEGATIVE_CONTROL
    secondary_integrity_control: str = SECONDARY_INTEGRITY_CONTROL
    support_continuation_if: str = (
        "mean_D_C3 >= +0.25 AND mean_D_NC < +0.25 AND mean_D_C3 > mean_D_NC "
        "AND aa_discrepancy_count == 0 AND primary_pair_coverage==1.0 "
        "AND negative_control_coverage==1.0 AND all scientific validity gates pass"
    )
    inconclusive_if: str = (
        "-0.25 < mean_D_C3 < +0.25 under valid full coverage "
        "(any positive value below delta_m0 is NOT support)"
    )
    weaken_if: str = (
        "mean_D_C3 <= -0.25 under full coverage and valid controls"
    )
    invalidate_if: str = (
        "leakage after freeze; gold saturation; incomplete coverage; "
        "provenance failure; scorer-contract failure; "
        "mean_D_NC >= +0.25 OR mean_D_NC >= mean_D_C3; "
        "any A/A exact-match discrepancy; runtime/load unqualified"
    )


# ---------------------------------------------------------------------------
# Decision arithmetic (descriptive)
# ---------------------------------------------------------------------------

def paired_d(y_treatment: int | bool, y_control: int | bool) -> int:
    """D_i = Y(treatment) - Y(control) with Y in {0,1}."""
    return int(bool(y_treatment)) - int(bool(y_control))


def mean_paired_difference(d_values: Sequence[int | float]) -> float:
    if not d_values:
        raise ContractError("EMPTY_D_VECTOR", "no paired differences to aggregate")
    return float(sum(d_values)) / float(len(d_values))


def median_paired_difference(d_values: Sequence[int | float]) -> float:
    """Legacy diagnostic only — not the primary aggregate."""
    if not d_values:
        raise ContractError("EMPTY_D_VECTOR")
    xs = sorted(float(x) for x in d_values)
    n = len(xs)
    mid = n // 2
    if n % 2:
        return xs[mid]
    return 0.5 * (xs[mid - 1] + xs[mid])


def classify_mean_d_c3(mean_d: float) -> str:
    """Primary C3 vs C1 direction classification (before NC/AA gates)."""
    if mean_d >= DELTA_M0:
        return DecisionOutcome.SUPPORT_CONTINUATION.value
    if mean_d <= -DELTA_M0:
        return DecisionOutcome.WEAKEN_HYPOTHESIS.value
    return DecisionOutcome.INCONCLUSIVE.value


def evaluate_decision(
    *,
    mean_d_c3: float,
    mean_d_nc: float,
    aa_discrepancy_count: int,
    primary_pair_coverage: float,
    negative_control_coverage: float,
    validity_gates_pass: bool = True,
    runtime_qualified: bool = True,
) -> dict[str, Any]:
    """Full M0-v2 decision including negative-control and A/A gates."""
    reasons: list[str] = []
    if not runtime_qualified:
        reasons.append("RUNTIME_CONTRACT_UNQUALIFIED")
    if primary_pair_coverage < 1.0:
        reasons.append("INCOMPLETE_PRIMARY_PAIR_COVERAGE")
    if negative_control_coverage < 1.0:
        reasons.append("INCOMPLETE_NEGATIVE_CONTROL_COVERAGE")
    if aa_discrepancy_count != 0:
        reasons.append("AA_DISCREPANCY")
    if mean_d_nc >= DELTA_M0:
        reasons.append("NEGATIVE_CONTROL_GAIN_AT_THRESHOLD")
    if mean_d_nc >= mean_d_c3:
        reasons.append("NEGATIVE_CONTROL_GAIN_MATCHES_OR_EXCEEDS_C3")
    if not validity_gates_pass:
        reasons.append("VALIDITY_GATE_FAILED")

    direction = classify_mean_d_c3(mean_d_c3)

    if reasons:
        # NC/AA failures are pipeline_artifact; coverage/runtime are invalidate
        if any(
            r in reasons
            for r in (
                "NEGATIVE_CONTROL_GAIN_AT_THRESHOLD",
                "NEGATIVE_CONTROL_GAIN_MATCHES_OR_EXCEEDS_C3",
                "AA_DISCREPANCY",
            )
        ):
            outcome = DecisionOutcome.PIPELINE_ARTIFACT.value
        else:
            outcome = DecisionOutcome.INVALIDATE_EXPERIMENT.value
        continuation = False
    elif direction == DecisionOutcome.SUPPORT_CONTINUATION.value:
        # All NC gates already passed (mean_d_nc < delta and mean_d_nc < mean_d_c3)
        outcome = DecisionOutcome.SUPPORT_CONTINUATION.value
        continuation = True
    else:
        outcome = direction
        continuation = False

    return {
        "mean_d_c3": mean_d_c3,
        "mean_d_nc": mean_d_nc,
        "delta_m0": DELTA_M0,
        "direction_class": direction,
        "outcome": outcome,
        "continuation_licensed": continuation,
        "reasons": sorted(set(reasons)),
        "primary_metric": PRIMARY_METRIC,
        "primary_estimand": PRIMARY_ESTIMAND,
        "primary_negative_control": PRIMARY_NEGATIVE_CONTROL,
        "max_claim_level": ClaimLevel.D_CORPUS_M0.value,
        "general_thesis_licensed": False,
    }


def counterbalanced_condition_order(
    task_ids: Sequence[str],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    """Pin C1-before-C3 vs C3-before-C1 order under a frozen seed.

    At least half of eligible tasks execute C1 before C3; remaining C3 before C1.
    Includes scrambled-state and A/A controls in each task block.
    """
    import random

    if not task_ids:
        return []
    ids = list(task_ids)
    rng = random.Random(int(seed))
    shuffled = list(ids)
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_c1_first = max(1, int(round(n * COUNTERBALANCE_C1_BEFORE_C3_FRACTION)))
    if n >= 2:
        n_c1_first = min(n_c1_first, n - 1)  # ensure both arms when possible
    plan: list[dict[str, Any]] = []
    for i, tid in enumerate(shuffled):
        c1_first = i < n_c1_first
        if c1_first:
            primary_order = ["C1_budget_matched_bare", "C3_static_ck"]
        else:
            primary_order = ["C3_static_ck", "C1_budget_matched_bare"]
        block = [
            "C0_bare",
            *primary_order,
            "C2_instruction_identical",
            PRIMARY_NEGATIVE_CONTROL,
            SECONDARY_INTEGRITY_CONTROL,
        ]
        plan.append(
            {
                "task_id": tid,
                "c1_before_c3": c1_first,
                "condition_block": block,
            }
        )
    return plan


def validate_order_counterbalance(plan: Sequence[Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if not plan:
        reasons.append("ORDER_PLAN_EMPTY")
        return reasons
    c1_first = sum(1 for p in plan if p.get("c1_before_c3"))
    c3_first = len(plan) - c1_first
    if len(plan) >= 2 and (c1_first == 0 or c3_first == 0):
        reasons.append("ORDER_NOT_COUNTERBALANCED")
    # half requirement (allow rounding)
    frac = c1_first / len(plan)
    if abs(frac - COUNTERBALANCE_C1_BEFORE_C3_FRACTION) > 0.5 / max(len(plan), 1) + 1e-9:
        # allow one-task rounding slack of 0.5/n
        if not (0.25 <= frac <= 0.75) and len(plan) >= 4:
            reasons.append("ORDER_NOT_COUNTERBALANCED")
    return reasons


# ---------------------------------------------------------------------------
# Falsification outcomes
# ---------------------------------------------------------------------------

FALSIFICATION_TABLE: list[dict[str, str]] = [
    {
        "outcome": "mean_D_C3 <= -0.25 on deciding metric",
        "classification": DecisionOutcome.WEAKEN_HYPOTHESIS.value,
        "licensed_claim": "paired structured replay underperformed flat control",
    },
    {
        "outcome": "-0.25 < mean_D_C3 < +0.25",
        "classification": DecisionOutcome.INCONCLUSIVE.value,
        "licensed_claim": "no minimally relevant paired advantage under frozen rule",
    },
    {
        "outcome": "mean_D_NC >= +0.25 (scrambled-state)",
        "classification": DecisionOutcome.PIPELINE_ARTIFACT.value,
        "licensed_claim": "structure/format artifact; substrate interpretation not licensed",
    },
    {
        "outcome": "mean_D_NC >= mean_D_C3",
        "classification": DecisionOutcome.PIPELINE_ARTIFACT.value,
        "licensed_claim": "apparent C3 benefit not attributable to accepted-state mapping",
    },
    {
        "outcome": "A/A exact-match discrepancy count > 0",
        "classification": DecisionOutcome.PIPELINE_ARTIFACT.value,
        "licensed_claim": "pipeline artifact suspected; no substrate claim",
    },
    {
        "outcome": "Condition-specific parser or provenance failures",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "measurement invalid; no efficacy comparison",
    },
    {
        "outcome": "Leakage discovered after freeze",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "experiment invalid; results uninterpretable",
    },
    {
        "outcome": "Incomplete primary-pair or negative-control coverage",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "primary estimand not estimable",
    },
    {
        "outcome": "Runtime provenance failure or unqualified load contract",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "runtime contract broken; no scientific claim",
    },
    {
        "outcome": "Gold-contract or scorer-contract failure",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "task or scoring contract invalid",
    },
]


# ---------------------------------------------------------------------------
# Claim licensing language
# ---------------------------------------------------------------------------

CLAIM_LICENSING: dict[str, str] = {
    "positive_primary": (
        "Under the frozen M0-v2 corpus, model snapshot, runtime contract, and paired "
        "control design, the mean paired exact-set-match difference for structured "
        "replay versus the flat control met the preregistered continuation threshold, "
        "while the scrambled-state and A/A validity gates passed."
    ),
    "null_result": (
        "Under the frozen M0-v2 contract, the mean paired exact-set-match difference "
        "fell strictly inside (-0.25, +0.25). No minimally relevant paired advantage "
        "of structured replay over the flat control is claimed."
    ),
    "negative_result": (
        "Under the frozen M0-v2 contract, the mean paired exact-set-match difference "
        "was <= -0.25: structured replay underperformed the flat control on the "
        "deciding metric. This materially weakens the M0-v2 hypothesis for this "
        "frozen corpus, model snapshot, and runtime contract."
    ),
    "negative_control_failure": (
        "The preregistered scrambled-state negative control produced mean_D_NC "
        ">= +0.25 or mean_D_NC >= mean_D_C3; the intended substrate interpretation "
        "is not licensed."
    ),
    "aa_failure": (
        "An A/A exact-match discrepancy was observed; unresolved pipeline/runtime "
        "asymmetry invalidates the M0-v2 interpretation."
    ),
    "incomplete_coverage": (
        "Primary-pair or negative-control coverage was incomplete; no corpus-level "
        "scientific claim is licensed."
    ),
    "provenance_failure": (
        "Runtime or model-identity provenance failed; no scientific claim is licensed."
    ),
    "leakage_after_freeze": (
        "Post-freeze leakage detection invalidated the experiment; no efficacy claim."
    ),
    "mixed_families": (
        "Task-family outcomes were mixed; only the preregistered aggregate rule applies; "
        "no cherry-picked family claim is licensed."
    ),
    "forbidden_overclaim": "Conditioned Kernel works.",
    "max_claim_level": ClaimLevel.D_CORPUS_M0.value,
    "continuation_only": (
        "A positive primary result licenses continuation only; it does not establish "
        "the general Conditioned Kernel thesis."
    ),
}


# ---------------------------------------------------------------------------
# Invalidation gates (pre-execution)
# ---------------------------------------------------------------------------

INVALIDATION_GATES: tuple[str, ...] = (
    "GOLD_IN_CONTROL_OR_DETERMINES_GOLD",
    "GOLD_SATURATES_UNIVERSE",
    "CONDITION_IDENTITY_MODEL_VISIBLE",
    "STATE_HASHES_MISSING",
    "INFORMATION_MATCHING_FAILED",
    "NEGATIVE_CONTROL_CELLS_ABSENT",
    "DECIDING_METRIC_UNSPECIFIED",
    "ESTIMAND_OR_DIRECTION_UNSPECIFIED",
    "CORPUS_BELOW_MINIMUM",
    "TASK_EXCLUSIONS_INCOMPLETE",
    "MODEL_DIGEST_MISSING",
    "RUNTIME_CONTRACT_UNRESOLVED",
    "RUNTIME_CONTRACT_UNQUALIFIED",
    "AUTHORIZATION_DOES_NOT_BIND_MANIFEST",
    "PERMITTED_COMBINATIONS_REQUIRED",
    "LEAKAGE_ANALYSIS_INCOMPLETE",
    "GOLD_OUTPUT_READY_IN_TREATMENT",
)


def validate_scientific_contract_package(
    *,
    primary_metric: str | None,
    secondary_metrics: Sequence[str] | None = None,
    estimand: str | None = None,
    predicted_direction: str | None = None,
    falsification_statement: str | None = None,
    min_task_count: int | None = None,
    n_candidate: int | None = None,
    negative_controls_defined: bool = False,
    primary_negative_control: str | None = None,
    model_digest: str | None = None,
    runtime_policy_present: bool = False,
    runtime_qualified: bool = True,
    c1_definition_conflicts: bool = False,
    post_performance_task_selection: bool = False,
    ordering_seed: int | None = None,
) -> list[str]:
    """Return reason codes if the package fails static scientific contract gates."""
    reasons: list[str] = []
    if not primary_metric:
        reasons.append("MISSING_PRIMARY_METRIC")
    if primary_metric and primary_metric != PRIMARY_METRIC:
        if primary_metric not in (PRIMARY_METRIC, SECONDARY_METRIC):
            reasons.append("UNKNOWN_PRIMARY_METRIC")
        elif primary_metric != PRIMARY_METRIC:
            reasons.append("PRIMARY_METRIC_NOT_FROZEN_CHOICE")
    secs = list(secondary_metrics or [])
    if primary_metric and primary_metric in secs:
        reasons.append("MULTIPLE_PRIMARY_METRICS")
    if len([m for m in [primary_metric] + secs if m == PRIMARY_METRIC]) > 1:
        reasons.append("MULTIPLE_PRIMARY_METRICS")
    if primary_metric == PRIMARY_METRIC and SECONDARY_METRIC in secs and PRIMARY_METRIC in secs:
        reasons.append("MULTIPLE_PRIMARY_METRICS")

    if not estimand:
        reasons.append("MISSING_ESTIMAND")
    elif estimand == LEGACY_MEDIAN_ESTIMAND:
        reasons.append("MEDIAN_NOT_PRIMARY_ESTIMAND")
        reasons.append("ESTIMAND_NOT_FROZEN_CHOICE")
    elif estimand != PRIMARY_ESTIMAND:
        reasons.append("ESTIMAND_NOT_FROZEN_CHOICE")
    if not predicted_direction:
        reasons.append("MISSING_PREDICTED_DIRECTION")
    if not falsification_statement:
        reasons.append("MISSING_FALSIFICATION_STATEMENT")
    if min_task_count is None:
        reasons.append("MISSING_MIN_TASK_COUNT")
    elif min_task_count < MIN_ELIGIBLE_TASKS:
        reasons.append("CORPUS_BELOW_MINIMUM")
    if n_candidate is not None and n_candidate != N_CANDIDATE:
        reasons.append("N_CANDIDATE_NOT_FROZEN")
    if not negative_controls_defined:
        reasons.append("MISSING_NEGATIVE_CONTROL")
    if primary_negative_control is not None and (
        primary_negative_control != PRIMARY_NEGATIVE_CONTROL
    ):
        reasons.append("PRIMARY_NEGATIVE_CONTROL_NOT_FROZEN")
    if not model_digest:
        reasons.append("MISSING_MODEL_DIGEST")
    if not runtime_policy_present:
        reasons.append("MISSING_RUNTIME_POLICY")
    if not runtime_qualified:
        reasons.append("RUNTIME_CONTRACT_UNQUALIFIED")
    if c1_definition_conflicts:
        reasons.append("CONFLICTING_C1_DEFINITION")
    if post_performance_task_selection:
        reasons.append("POST_PERFORMANCE_TASK_SELECTION")
    if ORDERING_SEED_REQUIRED and ordering_seed is None:
        reasons.append("ORDERING_SEED_MISSING")
    return reasons


def scientific_manifest_allowed(
    *,
    n_eligible: int,
    contract_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    """No scientific manifest may be created below N_min_eligible."""
    reasons = list(contract_reasons or [])
    if n_eligible < MIN_ELIGIBLE_TASKS:
        reasons.append("CORPUS_BELOW_MINIMUM")
    allowed = len(reasons) == 0 and n_eligible >= MIN_ELIGIBLE_TASKS
    return {
        "allowed": allowed,
        "n_eligible": n_eligible,
        "n_min_eligible": MIN_ELIGIBLE_TASKS,
        "n_candidate": N_CANDIDATE,
        "reasons": sorted(set(reasons)),
        "m0_authorized": False,
        "scientific_completion": False,
    }


def licensed_claim_for_outcome(outcome_key: str) -> str:
    return CLAIM_LICENSING.get(outcome_key, "")


def max_claim_level() -> str:
    return ClaimLevel.D_CORPUS_M0.value


def scientific_contract_freeze_dict() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "contract_amendment": CONTRACT_AMENDMENT,
        "retired_candidate_id": RETIRED_CANDIDATE_ID,
        "retired_candidate_sha256": RETIRED_CANDIDATE_SHA256,
        "claim_ladder": CLAIM_LADDER,
        "max_claim_level": max_claim_level(),
        "primary_metric": PRIMARY_METRIC,
        "secondary_metric": SECONDARY_METRIC,
        "estimand": EstimandContract().__dict__,
        "decision_rule": DecisionRule().__dict__,
        "delta_m0": DELTA_M0,
        "predicted_direction": PREDICTED_DIRECTION,
        "falsification_table": FALSIFICATION_TABLE,
        "condition_definitions_v2": CONDITION_DEFINITIONS_V2,
        "primary_contrast": PRIMARY_CONTRAST,
        "primary_negative_control": PRIMARY_NEGATIVE_CONTROL,
        "secondary_integrity_control": SECONDARY_INTEGRITY_CONTROL,
        "c3_required_representation": C3_REQUIRED_REPRESENTATION,
        "claim_licensing": CLAIM_LICENSING,
        "invalidation_gates": list(INVALIDATION_GATES),
        "n_candidate": N_CANDIDATE,
        "min_eligible_tasks": MIN_ELIGIBLE_TASKS,
        "n_min_eligible": N_MIN_ELIGIBLE,
        "min_distractors": MIN_DISTRACTORS,
        "min_permitted_over_expected_ratio": MIN_PERMITTED_OVER_EXPECTED_RATIO,
        "replicate_count": REPLICATE_COUNT,
        "retries": RETRIES,
        "no_independent_replication_claim": True,
        "counterbalance_c1_before_c3_fraction": COUNTERBALANCE_C1_BEFORE_C3_FRACTION,
        "ordering_seed_required": ORDERING_SEED_REQUIRED,
        "scientific_completion": False,
        "m0_authorized": False,
        "headline_eligible": False,
    }
