# RUN 00.9A — Preregistration Schema `ck.m0_preregistration.v2`

Template only. **Not ratified.** No candidate manifest hash. No authorization.

Amended by **RUN 00.9A.1**: mean estimand, δ_m0=0.25, scrambled_state NC,
fail-closed leakage policy, N_candidate=24.

## Fields (required shape)

See `preregistration_template()` in `m0_preregistration_v2.py`:

preregistration_id, schema, claim_level, hypothesis, falsification_statement,  
primary_estimand=`mean_paired_difference`, primary_metric, secondary_metrics,  
delta_m0, predicted_direction, decision_rule, negative_control_rule,  
n_candidate, minimum_task_count, task_family_quotas, pairing_policy,  
failure_policy, coverage_policy, replicate_policy, execution_order_policy,  
model_identity_policy, runtime_provenance_policy, leakage_policy,  
claim_licensing, invalidating_conditions, authorizing_principal,  
ratification_timestamp, candidate_manifest_sha256, preregistration_sha256,  
binding_procedure.

## Two-way binding (future)

1. Freeze preregistration body without `candidate_manifest_sha256`.  
2. Build candidate manifest citing `preregistration_id`.  
3. Set `candidate_manifest_sha256` on preregistration; re-hash.  
4. Authorization receipt cites **both** hashes.

RUN 00.9A.1 still stops before step 2.
