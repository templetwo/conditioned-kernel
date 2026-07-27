# RUN 00.9A / 00.9A.1 — M0-v2 Scientific Contract Spec

**Starting commit (00.9A.1 base):** `862429c4e181fed2c31fb2aa57bc8010a4b28265`  
**Branch (00.9A.1):** `grok/ck-run-00-9a-1-contract-closure`  
**Contract version:** `ck.m0_scientific_contract.v2.1`  
**M0:** NO-GO · No model execution · No corpus authorship · No authorization

## Scientific objective

Test whether a verified structured continuity packet improves recovery of
previously accepted relational state relative to a mechanically matched control
that receives equivalent instructions and comparable non-answer informational
mass **without** receiving the accepted relation set in output-ready form.

The design must be able to **weaken** the hypothesis. If no frozen result can
count against it, the design fails review.

## Modules

| Module | Role |
|---|---|
| `m0_scientific_contract.py` | claim ladder, mean estimand, δ_m0, conditions, decision |
| `m0_task_eligibility_v2.py` | gold non-saturation, state/gold, corpus minima |
| `m0_leakage_analysis.py` | **fail-closed** anti-copy / control leakage analysis |
| `m0_preregistration_v2.py` | `ck.m0_preregistration.v2` template (unratified) |

## Frozen primary choices (00.9A.1)

| Axis | Frozen value |
|---|---|
| Primary metric | `exact_relation_set_match` |
| Secondary metric | `primary_score` |
| Estimand | `mean_paired_difference` of \(D_i=Y_i(C3)-Y_i(C1)\) |
| δ_m0 | **0.25** |
| Direction | `C3_greater_than_C1` with threshold, not any positive |
| N_candidate | **24** |
| N_min_eligible | **12** |
| Primary NC | `scrambled_state` |
| Secondary integrity | `aa_serialization` |
| C3 representation | `structured_state_v1` (hard non-output-ready) |
| Max claim level | D (continuation only) |
| Replicates | 1 (no independent-replication claim) |
| Retries | 0 |

## Fail-closed leakage (00.9A.1)

`permitted_combinations` is **required**. None/empty/omitted:

- hard failure (`PERMITTED_COMBINATIONS_REQUIRED` / `EMPTY`)
- or incomplete analysis with `leakage_detected=True` and
  `LEAKAGE_ANALYSIS_INCOMPLETE` / `CONTROL_DERIVABILITY_UNRESOLVED`
- **never** a clean `leakage_detected=false`

## State and packet freeze (two-stage)

Stage 1: freeze Episode A hashes. Stage 2: compile Episode B packets and hashes.
No Episode-B model execution before Stage 2 is complete.
One `cell_id` may not admit two Episode-A states.

## Replicate / order policy

- Replicates: 1; retries: 0; distinct cell IDs; failures terminalized  
- Counterbalanced condition order: ≥ half C1-before-C3, remainder C3-before-C1  
- Seed-pinned; scrambled_state + A/A in every task block  
- Unqualified runtime/load → `RUNTIME_CONTRACT_UNQUALIFIED` blocks authorization  

## Retired candidate

`ck.m0.candidate.v1` / `9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922`  
Disposition: RETIRED · NEVER RATIFY · NEVER OVERWRITE.

## Not in this round

Corpus construction, Ollama, final execution manifest, Adaptive Riverbed,
authorization receipt, scorer arithmetic changes, commissioning evidence edits.
