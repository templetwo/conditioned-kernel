"""RUN 00.9A — ck.m0_preregistration.v2 schema and template (unratified)."""

from __future__ import annotations

from typing import Any, Mapping

from conditioned_kernel.m0_scientific_contract import (
    CLAIM_LICENSING,
    FALSIFICATION_TABLE,
    MIN_ELIGIBLE_TASKS,
    PRIMARY_ESTIMAND,
    PRIMARY_METRIC,
    PREDICTED_DIRECTION,
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
            "If median paired D_i = Y_i(C3)-Y_i(C1) on exact_relation_set_match is "
            "≤ 0 under full coverage, or if negative controls reproduce the C3 "
            "gain, the M0 hypothesis is not supported for this corpus/model."
        ),
        "primary_estimand": PRIMARY_ESTIMAND,
        "primary_metric": PRIMARY_METRIC,
        "secondary_metrics": [SECONDARY_METRIC],
        "predicted_direction": PREDICTED_DIRECTION,
        "decision_rule": {
            "support_continuation": "median D_i > 0 AND negative-control ok AND coverage==1",
            "inconclusive": "median D_i == 0 OR secondary conflict without invalidation",
            "weaken": "median D_i < 0 under valid full coverage",
            "invalidate": list(
                {
                    r["classification"]
                    for r in FALSIFICATION_TABLE
                    if r["classification"]
                    in ("invalidate_experiment", "pipeline_artifact")
                }
            ),
        },
        "negative_control_rule": (
            "At least one scrambled-state or irrelevant-state control; if its "
            "paired gain matches C3, interpretation fails."
        ),
        "minimum_task_count": MIN_ELIGIBLE_TASKS,
        "task_family_quotas": {
            "asymmetric_relation": 4,
            "symmetric_relation": 2,
            "multi_expected": 3,
            "mixed_accept_reject": 3,
        },
        "pairing_policy": "exactly one C1 per C3 per task replicate",
        "failure_policy": "null Y when not SCORED; incomplete coverage blocks claim",
        "coverage_policy": "primary_pair_coverage must equal 1.0",
        "replicate_policy": {
            "replicates": 1,
            "retries": 0,
            "distinct_cell_ids_per_replicate": True,
            "no_independent_replication_claim_from_identical_reruns": True,
        },
        "execution_order_policy": {
            "blocking": "by_task then conditions C0,C1,C2,C3,NC",
            "randomization": "task order seeded and frozen before execution",
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
        },
        "leakage_policy": "ck.m0_leakage_analysis.v1 static pre-auth gates",
        "claim_licensing": CLAIM_LICENSING,
        "invalidating_conditions": [
            "GOLD_VISIBLE_IN_CONTROL",
            "GOLD_SATURATES_PERMITTED_UNIVERSE",
            "LEAKAGE_AFTER_FREEZE",
            "INCOMPLETE_PRIMARY_PAIR_COVERAGE",
            "NEGATIVE_CONTROL_SAME_GAIN",
            "MODEL_DIGEST_MISSING",
            "RUNTIME_PROVENANCE_FAILURE",
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
            "hashes. No ratification in RUN 00.9A."
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
