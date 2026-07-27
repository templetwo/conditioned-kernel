# RUN 00.6E — Scoring Schema (`ck.relational_score.v1`)

## Identity

| Field | Value |
|---|---|
| Schema version | `ck.relational_score.v1` |
| Module | `conditioned_kernel.relational_scorer` |
| Scientific status | `scorer_validation_only` |
| Headline eligible | always `false` |
| Scientific completion | always `false` |

## Terminal record fields

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `ck.relational_score.v1` |
| `scorer_schema_version` | string | same |
| `task_id` | string | required |
| `condition_id` | string | required |
| `inference_status` | string | passed through from inference |
| `scoring_status` | enum string | see terminal classifications |
| `primary_score` | float \| null | `[0,1]` or null |
| `primary_score_undefined_reason` | string \| null | set when score is null |
| `exact_relation_set_match` | bool | strict set equality + no extras/dups |
| `expected_n` | int | |
| `proposed_raw_n` | int | includes duplicates |
| `proposed_unique_n` | int | unique triples |
| `true_positive_n` | int | |
| `false_negative_n` | int | |
| `wrong_relation_n` | int | |
| `reversed_direction_n` | int | |
| `unsupported_assertion_n` | int | |
| `out_of_universe_assertion_n` | int | |
| `duplicate_assertion_n` | int | |
| `precision` | float \| null | |
| `precision_undefined_reason` | string \| null | |
| `recall` | float \| null | |
| `recall_undefined_reason` | string \| null | |
| `f1` | float \| null | |
| `f1_undefined_reason` | string \| null | |
| `invalid_reason` | string \| null | terminal failure code |
| `expected_relation_hash` | string \| null | SHA-256 of sorted **canonical** expected set |
| `proposed_assertion_hash` | string \| null | SHA-256 of sorted **raw multiset** (cardinality retained) |
| `proposed_unique_set_hash` | string \| null | SHA-256 of sorted **unique canonical** facts |
| `false_negatives` | list[triple] | sorted |
| `proposal_classifications` | list | each `{triple, classification}` in proposal order |
| `task_contract_version` | string \| null | |
| `repo_commit` | string \| null | |
| `model_runtime_provenance` | object | pass-through |
| `scientific_status` | string | `scorer_validation_only` |
| `scientific_completion` | bool | always `false` |
| `headline_eligible` | bool | always `false` |
| `headline_ineligible_reason` | string | fixed M0 admission reason |

## Terminal scoring statuses

```text
SCORED
TIMEOUT
TRANSPORT_ERROR
INVALID_RESPONSE
NO_FINAL_RESPONSE
MALFORMED_ASSERTIONS
TASK_CONTRACT_ERROR
SCORER_INTERNAL_ERROR
```

Inference status strings accepted for non-scored terminals:

```text
timeout | TIMEOUT
transport_error | TRANSPORT_ERROR
invalid_response | INVALID_RESPONSE
no_final_response | NO_FINAL_RESPONSE
```

## Relation-level classifications

```text
TRUE_POSITIVE
WRONG_RELATION
REVERSED_DIRECTION
UNSUPPORTED_ASSERTION
DUPLICATE_ASSERTION
OUT_OF_UNIVERSE_ASSERTION
FALSE_NEGATIVE
```

## Primary score formula

```text
primary_score = TP / (
  expected_n
  + wrong_relation_n
  + reversed_direction_n
  + unsupported_assertion_n
  + out_of_universe_assertion_n
)
```

If denominator ≤ 0 → `primary_score = null`, reason `ZERO_DENOMINATOR`.

Clamped to `[0, 1]` if defined (formula cannot exceed 1 under correct TP accounting).

## Zero-denominator rules

| Metric | Condition | Value | Reason |
|---|---|---|---|
| primary_score | denom ≤ 0 | null | `ZERO_DENOMINATOR` |
| precision | unique_scored_proposals ≤ 0 | null | `ZERO_DENOMINATOR_PRECISION` |
| recall | expected_n ≤ 0 | null | `ZERO_DENOMINATOR_RECALL` |
| f1 | P or R undefined | null | `UNDEFINED_COMPONENT` |
| f1 | P = R = 0.0 | 0.0 | — |
| non-SCORED terminal | any | primary_score null | status / invalid_reason |

## Canonicalization and hashing

### Symmetric fact canonicalization (RUN 00.6E.1)

If `relation ∈ symmetric_relations`:

```text
canonical_subject = min(subject_id, object_id)
canonical_object  = max(subject_id, object_id)
```

Otherwise endpoints are left as proposed/expected.

### Hash surfaces

1. Triple key order for sort: `subject_id`, `relation`, `object_id` (lexicographic).
2. `proposed_assertion_hash`: sorted **raw multiset** of directed proposals
   (both directions and duplicate cardinality change the hash).
3. `proposed_unique_set_hash`: sorted **unique canonical** facts after
   symmetric collapse (both directions of one symmetric fact → one set member).
4. `expected_relation_hash`: sorted load-time canonical expected set.
5. Canonical JSON: `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`.
6. Hash: SHA-256 hex of UTF-8 bytes.

`score_record_canonical_bytes` / `score_record_hash` produce deterministic
record digests for repeated scoring.

Sole scorer predicate field: `relation` (no `predicate_id` alias).

## Gold / task contract fields

| Field | Required |
|---|---|
| `task_id` | yes |
| `contract_version` | yes |
| `subject_universe` | yes |
| `object_universe` | yes |
| `relation_universe` | yes |
| `expected_relations` | yes (non-empty unless `allow_empty_expected`) |
| `symmetric_relations` | optional; each must be in relation universe |
| `allow_empty_expected` | optional bool, default false |

## Policy stamps (immutable on this run)

```json
{
  "scientific_status": "scorer_validation_only",
  "scientific_completion": false,
  "headline_eligible": false,
  "headline_ineligible_reason": "m0_manifest_and_admission_contract_not_yet_ratified"
}
```

No scoring fixture or scorer test enters a scientific denominator.
