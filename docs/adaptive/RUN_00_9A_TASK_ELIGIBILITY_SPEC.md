# RUN 00.9A — Task Eligibility Spec (v2)

## Required fields (each task)

`task_id`, `task_family`, `contract_version=ck.m0_task_contract.v2`,
`entity_universe`, `relation_universe`, `permitted` (derived),  
`expected_relations`, `accepted_relation_set`, `rejected_relation_set`,  
`in_universe_distractors`, `expected_relation_semantics=all_required`,  
`output_schema_id=continuity_assertions_v1`, `episode_b_query` (state-referential),  
`state_hash` / `episode_a_state_hash`, hashes for freeze stages.

## Gold relation

```text
expected_relations ⊆ accepted_relation_set
expected_relations == accepted relations relevant to Episode-B query
NOT expected_relations == full permitted universe
```

## Non-saturation (frozen)

```text
0 < expected_n < permitted_triple_n
permitted_triple_n >= 2 * expected_n
in_universe_distractor_n >= 2   (explicit or implicit non-gold permitted)
```

Exclusion: `GOLD_SATURATES_PERMITTED_UNIVERSE`

## Corpus policy (frozen before authorship)

| Parameter | Value |
|---|---|
| N_min_eligible | **12** |
| One-task corpus | **prohibited** |
| Task selection | independent of model performance |
| Model probing during construction | **forbidden** |
| Ordering | lexicographic task_id |
| Families | asymmetric/symmetric, multi-expected, mixed accept/reject quotas (prereg) |

## Selection independence

See `TASK_SELECTION_POLICY` in `m0_task_eligibility_v2.py`: fixed family template,
eligibility rule id, distractor policy, difficulty bands, blinded IDs if manual.
