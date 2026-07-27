"""RUN 00.9A — M0-v2 scientific contract (static freeze; no model execution).

Defines claim ladder, estimand, deciding metric, condition supersession,
falsification, and invalidation gates. Does not authorize M0 execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

CONTRACT_VERSION = "ck.m0_scientific_contract.v2"
RETIRED_CANDIDATE_ID = "ck.m0.candidate.v1"
RETIRED_CANDIDATE_SHA256 = (
    "9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922"
)

# Frozen primary metric (single deciding metric — no post-run switching)
PRIMARY_METRIC = "exact_relation_set_match"
SECONDARY_METRIC = "primary_score"
PRIMARY_ESTIMAND = "median_paired_difference"
PREDICTED_DIRECTION = "C3_greater_than_C1"
MIN_ELIGIBLE_TASKS = 12
MIN_DISTRACTORS = 2
MIN_PERMITTED_OVER_EXPECTED_RATIO = 2.0  # permitted_triple_n >= 2 * expected_n
REPLICATE_COUNT = 1  # scientific policy: still 1 until load-state limitations addressed
RETRIES = 0


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
            "Across the preregistered frozen task corpus, the paired outcome moved "
            "in the predicted direction under the frozen model/runtime contract."
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
            "Episode-A state in a form distinct from the required output schema "
            "when possible; model must transform state into the requested answer."
        ),
        "must_not": (
            "mere copy-ready scorer triples as the sole treatment unless "
            "copy-ready state is explicitly narrowed as the construct"
        ),
        "role": "treatment",
    },
}

PRIMARY_CONTRAST = {
    "treatment": "C3_static_ck",
    "control": "C1_budget_matched_bare",
    "isolates": (
        "structured accepted-state mapping vs flat state-mass without that mapping"
    ),
}


# ---------------------------------------------------------------------------
# Estimand and decision rule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EstimandContract:
    """Frozen primary estimand for M0-v2."""

    unit_of_analysis: str = "eligible_task"
    treatment: str = "C3_static_ck"
    paired_control: str = "C1_budget_matched_bare"
    task_level_outcome: str = PRIMARY_METRIC  # exact_relation_set_match as 0/1
    paired_difference: str = "D_i = Y_i(C3) - Y_i(C1)"
    corpus_aggregate: str = PRIMARY_ESTIMAND  # median_paired_difference
    predicted_direction: str = PREDICTED_DIRECTION
    missing_pair_handling: str = (
        "exclude task from primary estimand; block scientific headline "
        "if primary_pair_coverage < 1.0"
    )
    failure_handling: str = (
        "null Y when terminal not SCORED; D_i undefined → task excluded from "
        "median; incomplete coverage invalidates primary claim"
    )
    replicate_handling: str = (
        f"exactly {REPLICATE_COUNT} replicate per task-condition; no retries; "
        "no independent-replication claim from identical deterministic reruns"
    )
    min_tasks_for_meaningful_statistic: int = MIN_ELIGIBLE_TASKS
    uncertainty_policy: str = (
        "descriptive only: report median D and exact task-level table; "
        "no asymptotic p-values; optional bootstrap interval only as secondary "
        "diagnostic if N>=MIN_ELIGIBLE_TASKS, never as primary decision"
    )
    justification: str = (
        "Median of paired binary/score differences is robust to single-task "
        "outliers on a small frozen corpus and matches the paired design. "
        "Mean is not interchangeable."
    )


@dataclass(frozen=True)
class DecisionRule:
    primary_metric: str = PRIMARY_METRIC
    secondary_metric: str = SECONDARY_METRIC
    estimand: str = PRIMARY_ESTIMAND
    direction: str = PREDICTED_DIRECTION
    support_continuation_if: str = (
        "median D_i > 0 AND negative-control does not reproduce the same "
        "directional gain AND primary_pair_coverage==1.0 AND no invalidation gate"
    )
    inconclusive_if: str = (
        "median D_i == 0 OR N insufficient OR secondary metrics conflict without "
        "invalidation"
    )
    weaken_if: str = (
        "median D_i < 0 under full coverage and valid controls"
    )
    invalidate_if: str = (
        "leakage after freeze; gold saturation; incomplete coverage; "
        "provenance failure; scorer-contract failure; negative-control same gain"
    )


# ---------------------------------------------------------------------------
# Falsification outcomes
# ---------------------------------------------------------------------------

FALSIFICATION_TABLE: list[dict[str, str]] = [
    {
        "outcome": "C3 systematically below C1 on deciding metric",
        "classification": DecisionOutcome.WEAKEN_HYPOTHESIS.value,
        "licensed_claim": "paired structured replay underperformed flat control",
    },
    {
        "outcome": "C3 indistinguishable from C1 (median D≈0)",
        "classification": DecisionOutcome.INCONCLUSIVE.value,
        "licensed_claim": "no detectable paired advantage under frozen rule",
    },
    {
        "outcome": "Negative-control arms show same apparent gain as C3",
        "classification": DecisionOutcome.PIPELINE_ARTIFACT.value,
        "licensed_claim": "apparent C3 benefit not attributable to accepted-state mapping",
    },
    {
        "outcome": "A/A arms show unexplained directional asymmetry",
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
        "outcome": "Incomplete primary-pair coverage",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "primary estimand not estimable",
    },
    {
        "outcome": "Runtime provenance failure",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "runtime contract broken; no scientific claim",
    },
    {
        "outcome": "Gold-contract failure",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "task contract invalid",
    },
    {
        "outcome": "Scorer-contract failure",
        "classification": DecisionOutcome.INVALIDATE_EXPERIMENT.value,
        "licensed_claim": "scoring invalid",
    },
]


# ---------------------------------------------------------------------------
# Claim licensing language
# ---------------------------------------------------------------------------

CLAIM_LICENSING: dict[str, str] = {
    "positive_primary": (
        "Under the frozen M0-v2 task corpus, model snapshot, runtime contract, and "
        "paired control design, structured replay produced a larger preregistered "
        "task-level outcome than the flat control according to the frozen decision "
        "rule (median D_i > 0 on exact_relation_set_match)."
    ),
    "null_result": (
        "Under the frozen M0-v2 contract, the median paired difference was zero "
        "(or indistinguishable under the frozen descriptive rule). No paired "
        "advantage of structured replay over the flat control is claimed."
    ),
    "negative_result": (
        "Under the frozen M0-v2 contract, the median paired difference was negative: "
        "structured replay underperformed the flat control on the deciding metric. "
        "This materially weakens the M0 hypothesis for this corpus and model snapshot."
    ),
    "negative_control_failure": (
        "A preregistered negative control reproduced the same directional pattern as "
        "C3; the intended substrate interpretation is not licensed."
    ),
    "incomplete_coverage": (
        "Primary-pair coverage was incomplete; no corpus-level scientific claim is "
        "licensed."
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
    "AUTHORIZATION_DOES_NOT_BIND_MANIFEST",
)


def validate_scientific_contract_package(
    *,
    primary_metric: str | None,
    secondary_metrics: Sequence[str] | None = None,
    estimand: str | None = None,
    predicted_direction: str | None = None,
    falsification_statement: str | None = None,
    min_task_count: int | None = None,
    negative_controls_defined: bool = False,
    model_digest: str | None = None,
    runtime_policy_present: bool = False,
    c1_definition_conflicts: bool = False,
    post_performance_task_selection: bool = False,
) -> list[str]:
    """Return reason codes if the package fails static scientific contract gates."""
    reasons: list[str] = []
    if not primary_metric:
        reasons.append("MISSING_PRIMARY_METRIC")
    if primary_metric and primary_metric != PRIMARY_METRIC:
        # Only the frozen primary is allowed for M0-v2 v2 freeze
        if primary_metric not in (PRIMARY_METRIC, SECONDARY_METRIC):
            reasons.append("UNKNOWN_PRIMARY_METRIC")
        elif primary_metric != PRIMARY_METRIC:
            reasons.append("PRIMARY_METRIC_NOT_FROZEN_CHOICE")
    secs = list(secondary_metrics or [])
    if primary_metric and primary_metric in secs:
        reasons.append("MULTIPLE_PRIMARY_METRICS")
    if len([m for m in [primary_metric] + secs if m == PRIMARY_METRIC]) > 1:
        reasons.append("MULTIPLE_PRIMARY_METRICS")
    # Reject if two primaries claimed
    if secs and PRIMARY_METRIC in secs and primary_metric == PRIMARY_METRIC:
        pass  # secondary listing of other metrics ok
    if primary_metric == PRIMARY_METRIC and SECONDARY_METRIC in secs and PRIMARY_METRIC in secs:
        reasons.append("MULTIPLE_PRIMARY_METRICS")

    if not estimand:
        reasons.append("MISSING_ESTIMAND")
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
    if not negative_controls_defined:
        reasons.append("MISSING_NEGATIVE_CONTROL")
    if not model_digest:
        reasons.append("MISSING_MODEL_DIGEST")
    if not runtime_policy_present:
        reasons.append("MISSING_RUNTIME_POLICY")
    if c1_definition_conflicts:
        reasons.append("CONFLICTING_C1_DEFINITION")
    if post_performance_task_selection:
        reasons.append("POST_PERFORMANCE_TASK_SELECTION")
    return reasons


def licensed_claim_for_outcome(outcome_key: str) -> str:
    return CLAIM_LICENSING.get(outcome_key, "")


def max_claim_level() -> str:
    return ClaimLevel.D_CORPUS_M0.value


def scientific_contract_freeze_dict() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "retired_candidate_id": RETIRED_CANDIDATE_ID,
        "retired_candidate_sha256": RETIRED_CANDIDATE_SHA256,
        "claim_ladder": CLAIM_LADDER,
        "max_claim_level": max_claim_level(),
        "primary_metric": PRIMARY_METRIC,
        "secondary_metric": SECONDARY_METRIC,
        "estimand": EstimandContract().__dict__,
        "decision_rule": DecisionRule().__dict__,
        "predicted_direction": PREDICTED_DIRECTION,
        "falsification_table": FALSIFICATION_TABLE,
        "condition_definitions_v2": CONDITION_DEFINITIONS_V2,
        "primary_contrast": PRIMARY_CONTRAST,
        "claim_licensing": CLAIM_LICENSING,
        "invalidation_gates": list(INVALIDATION_GATES),
        "min_eligible_tasks": MIN_ELIGIBLE_TASKS,
        "min_distractors": MIN_DISTRACTORS,
        "min_permitted_over_expected_ratio": MIN_PERMITTED_OVER_EXPECTED_RATIO,
        "replicate_count": REPLICATE_COUNT,
        "retries": RETRIES,
        "scientific_completion": False,
        "m0_authorized": False,
        "headline_eligible": False,
    }
