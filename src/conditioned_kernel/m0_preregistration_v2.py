"""RUN 00.9A.1 — ck.m0_preregistration.v2 schema and template (unratified)."""

from __future__ import annotations

from typing import Any, Mapping

from conditioned_kernel.m0_scientific_contract import (
    CLAIM_LICENSING,
    DELTA_M0,
    FALSIFICATION_TABLE,
    MIN_ELIGIBLE_TASKS,
    N_CANDIDATE,
    PRIMARY_ESTIMAND,
    PRIMARY_METRIC,
    PRIMARY_NEGATIVE_CONTROL,
    PREDICTED_DIRECTION,
    REPLICATE_COUNT,
    RETRIES,
    SECONDARY_INTEGRITY_CONTROL,
    SECONDARY_METRIC,
    ClaimLevel,
)
from conditioned_kernel.relational_scorer import canonical_json_bytes, sha256_hex

PREREGISTRATION_SCHEMA = "ck.m0_preregistration.v2"


def preregistration_template() -> dict[str, Any]:
    """Empty/unratified template. No authorization. No final manifest hash."""
    return {
        "schema": PREREGISTRATION_SCHEMA,
        "preregistration_id": "ck.m0.prereg.v2.template",
        "claim_level": ClaimLevel.D_CORPUS_M0.value,
        "hypothesis": (
            "Structured replay of verified accepted Episode-A relations improves "
            "Episode-B recovery of that accepted state relative to a flat "
            "state-mass control under the frozen M0-v2 contract."
        ),
        "falsification_statement": (
            "If mean_i(D_i) with D_i=Y_i(C3)-Y_i(C1) on exact_relation_set_match "
            f"is <= -{DELTA_M0} under full coverage, the M0-v2 hypothesis is "
            "materially weakened for this corpus/model/runtime. If "
            f"-{DELTA_M0} < mean_D < +{DELTA_M0}, the result is inconclusive. "
            f"If mean_D_NC >= +{DELTA_M0} or mean_D_NC >= mean_D_C3, or any A/A "
            "discrepancy occurs, interpretation fails as pipeline artifact."
        ),
        "primary_estimand": PRIMARY_ESTIMAND,
        "primary_metric": PRIMARY_METRIC,
        "secondary_metrics": [SECONDARY_METRIC],
        "delta_m0": DELTA_M0,
        "predicted_direction": PREDICTED_DIRECTION,
        "decision_rule": {
            "support_continuation": (
                f"mean_D_C3 >= +{DELTA_M0} AND mean_D_NC < +{DELTA_M0} AND "
                "mean_D_C3 > mean_D_NC AND aa_discrepancy_count==0 AND "
                "primary_pair_coverage==1.0 AND negative_control_coverage==1.0"
            ),
            "inconclusive": f"-{DELTA_M0} < mean_D_C3 < +{DELTA_M0}",
            "weaken": f"mean_D_C3 <= -{DELTA_M0} under valid full coverage",
            "invalidate": list(
                {
                    r["classification"]
                    for r in FALSIFICATION_TABLE
                    if r["classification"]
                    in ("invalidate_experiment", "pipeline_artifact")
                }
            ),
        },
        "negative_control_rule": {
            "primary": PRIMARY_NEGATIVE_CONTROL,
            "secondary_integrity": SECONDARY_INTEGRITY_CONTROL,
            "fail_if_mean_d_nc_ge_delta": DELTA_M0,
            "fail_if_mean_d_nc_ge_mean_d_c3": True,
            "fail_if_aa_discrepancy": True,
        },
        "n_candidate": N_CANDIDATE,
        "minimum_task_count": MIN_ELIGIBLE_TASKS,
        "task_family_quotas": {
            "asymmetric_relation": 4,
            "symmetric_relation": 2,
            "multi_expected": 3,
            "mixed_accept_reject": 3,
        },
        "pairing_policy": "exactly one C1 per C3 per task replicate",
        "failure_policy": "null Y when not SCORED; incomplete coverage blocks claim",
        "coverage_policy": (
            "primary_pair_coverage must equal 1.0; "
            "negative_control_coverage must equal 1.0"
        ),
        "replicate_policy": {
            "replicates": REPLICATE_COUNT,
            "retries": RETRIES,
            "distinct_cell_ids_per_replicate": True,
            "no_independent_replication_claim_from_identical_reruns": True,
        },
        "execution_order_policy": {
            "blocking": "by_task then conditions including scrambled_state and A/A",
            "counterbalance": "half C1-before-C3, half C3-before-C1",
            "randomization": "task order seed-pinned before execution",
            "not_commissioning_fixed_order_as_science": True,
        },
        "model_identity_policy": {
            "model_tag_required": True,
            "resolved_digest_required": True,
            "single_snapshot": True,
        },
        "runtime_provenance_policy": {
            "required_fields": [
                "model_tag",
                "resolved_model_digest",
                "runtime_version",
                "request_sha256",
                "response_sha256",
            ],
            "option_confirmation": "record requested_but_not_confirmable when unknown",
            "unqualified_blocks_authorization": True,
            "unqualified_reason_code": "RUNTIME_CONTRACT_UNQUALIFIED",
        },
        "leakage_policy": (
            "ck.m0_leakage_analysis.v1 fail-closed: permitted_combinations required; "
            "None/empty never returns leakage_detected=false"
        ),
        "claim_licensing": CLAIM_LICENSING,
        "invalidating_conditions": [
            "GOLD_VISIBLE_IN_CONTROL",
            "GOLD_DERIVABLE_FROM_CONTROL",
            "GOLD_SATURATES_PERMITTED_UNIVERSE",
            "GOLD_OUTPUT_READY_IN_TREATMENT",
            "LEAKAGE_AFTER_FREEZE",
            "LEAKAGE_ANALYSIS_INCOMPLETE",
            "PERMITTED_COMBINATIONS_REQUIRED",
            "INCOMPLETE_PRIMARY_PAIR_COVERAGE",
            "NEGATIVE_CONTROL_GAIN_AT_THRESHOLD",
            "NEGATIVE_CONTROL_GAIN_MATCHES_OR_EXCEEDS_C3",
            "AA_DISCREPANCY",
            "MODEL_DIGEST_MISSING",
            "RUNTIME_PROVENANCE_FAILURE",
            "RUNTIME_CONTRACT_UNQUALIFIED",
        ],
        "authorizing_principal": None,
        "ratification_timestamp": None,
        "candidate_manifest_sha256": None,
        "preregistration_sha256": None,
        "binding_procedure": (
            "Two-way bind: (1) freeze preregistration body without "
            "candidate_manifest_sha256; (2) build candidate manifest citing "
            "preregistration_id; (3) set candidate_manifest_sha256 on "
            "preregistration and re-hash; (4) authorization receipt cites both "
            "hashes. No ratification in RUN 00.9A.1."
        ),
        "scientific_completion": False,
        "m0_authorized": False,
        "headline_eligible": False,
        "ratified": False,
    }


def hash_preregistration(body: Mapping[str, Any]) -> str:
    payload = {
        k: v
        for k, v in body.items()
        if k not in ("preregistration_sha256",)
    }
    return sha256_hex(canonical_json_bytes(payload))


def seal_template_hash(template: Mapping[str, Any] | None = None) -> dict[str, Any]:
    t = dict(template or preregistration_template())
    t["preregistration_sha256"] = hash_preregistration(t)
    return t
