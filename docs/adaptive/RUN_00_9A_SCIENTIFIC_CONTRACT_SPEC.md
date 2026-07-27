# RUN 00.9A — M0-v2 Scientific Contract Spec

**Starting commit:** `9fbfe48b93a19d10b0a00575f59f368a3f3ec3b7`  
**Branch:** `grok/ck-run-00-9a-scientific-contract-freeze`  
**Contract version:** `ck.m0_scientific_contract.v2`  
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
| `m0_scientific_contract.py` | claim ladder, estimand, conditions, falsification |
| `m0_task_eligibility_v2.py` | gold non-saturation, state/gold, corpus minima |
| `m0_leakage_analysis.py` | anti-copy / control leakage static analysis |
| `m0_preregistration_v2.py` | `ck.m0_preregistration.v2` template (unratified) |

## Frozen primary choices

| Axis | Frozen value |
|---|---|
| Primary metric | `exact_relation_set_match` |
| Secondary metric | `primary_score` |
| Estimand | `median_paired_difference` of \(D_i = Y_i(C3)-Y_i(C1)\) |
| Direction | `C3_greater_than_C1` |
| N_min_eligible | 12 |
| Max claim level | D (corpus M0) |
| Replicates | 1 (no independent-replication claim from identical reruns) |
| Retries | 0 |

## State and packet freeze (two-stage)

For every planned C3 cell require:

- `episode_a_state_hash`
- `accepted_relation_set_hash`
- `replay_receipt_hash`
- `compiled_packet_hash`
- `finalized_request_byte_length`
- `paired_control_packet_hash`
- `pair_byte_target`

**Stage 1:** execute and freeze Episode A.  
**Stage 2:** compile and freeze Episode B cells from accepted state.  
No Episode-B model execution before Stage 2 is complete and hashed.  
One `cell_id` may not admit two Episode-A states.

## Replicate / order policy

- Replicate count: 1 until load-state/determinism limitations are separately closed  
- No retries; failures terminalized per existing commissioning discipline  
- Task order: seeded and frozen before execution (not silent fixed C0–C3 commissioning order as science)  
- Blocking: by task, then conditions including NC  
- Cache / warm-cold: record; do not claim independence from identical condition reruns  
- Each planned cell gets a distinct cell ID; replicates (if later raised) get distinct IDs  

## Invalidation gates (pre-authorization)

See `INVALIDATION_GATES` in `m0_scientific_contract.py`. Gates run **before**
scientific authorization. Leakage after freeze invalidates the run.

## Retired candidate

`ck.m0.candidate.v1` / `9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922`  
Disposition: RETIRED · NEVER RATIFY · NEVER OVERWRITE.

## Not in this round

Corpus construction, Ollama, final execution manifest, Adaptive Riverbed,
authorization receipt, scorer arithmetic changes, commissioning evidence edits.
