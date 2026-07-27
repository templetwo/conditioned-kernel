# RUN 00.6E — Closed-Set Relational Scorer Spec

**Status:** implemented offline (scorer validation only)  
**Branch:** `grok/ck-run-00-6e-relational-scorer`  
**Base commit:** `02a0027`  
**Schema:** `ck.relational_score.v1`  
**M0:** `NO-GO`  
**Adaptive Riverbed:** `HOLD`  
**Scientific experiment scope:** `NOT AUTHORIZED`

## Founding principle

Mentioning correct identifiers is **not** sufficient.

Credit requires the structured relation:

```text
subject_id + relation + object_id
```

A model that mentions every permitted identifier must not receive more credit
than a model that returns one correct relation.

## Scope

- Offline, fixture-driven, test-first.
- No model invocation.
- No M0, no matrix execution, no threshold tuning.
- No changes to prompts, control construction, continuity persistence, replay,
  receipt schemas, execution scopes, or adaptive behavior.
- No embeddings, fuzzy similarity, LLM judge, or semantic paraphrase grading.

## Inputs

For each planned task-condition cell:

1. Closed expected relation set (task contract / gold).
2. Permitted continuity universe (subjects, objects, relations).
3. Parsed continuity assertions (already typed; scorer does not re-parse prose).
4. Typed inference outcome / status.
5. `task_id`, `condition_id`.
6. Contract and scorer schema versions; repo commit; model/runtime provenance
   passed through from the inference record when available.

Canonical triple shape:

```json
{
  "subject_id": "...",
  "relation": "...",
  "object_id": "..."
}
```

Sole scorer predicate field: `relation` (no `predicate_id` alias — RUN 00.6E.1).

### Symmetric canonicalization (RUN 00.6E.1)

For relations explicitly listed in `symmetric_relations`:

```text
canonical_subject = min(subject_id, object_id)
canonical_object  = max(subject_id, object_id)
```

Both directions of a symmetric fact are one unique assertion. A second emission
is `DUPLICATE_ASSERTION`, never `UNSUPPORTED_ASSERTION`. Asymmetric relations
preserve subject/object order exactly.

## Output

Exactly one terminal scoring record per planned cell.

Schema version: `ck.relational_score.v1`.

Every record carries:

- `scientific_status = scorer_validation_only`
- `scientific_completion = false`
- `headline_eligible = false`
- `headline_ineligible_reason = m0_manifest_and_admission_contract_not_yet_ratified`

## Terminal scoring statuses

| Status | Meaning |
|---|---|
| `SCORED` | Completed, parseable assertions scored |
| `TIMEOUT` | Inference timeout |
| `TRANSPORT_ERROR` | Transport failure |
| `INVALID_RESPONSE` | Invalid response |
| `NO_FINAL_RESPONSE` | Empty / missing final response |
| `MALFORMED_ASSERTIONS` | Structured assertions unusable |
| `TASK_CONTRACT_ERROR` | Gold / contract validation failed closed |
| `SCORER_INTERNAL_ERROR` | Unexpected scorer exception |

Non-observed outcomes keep `primary_score = null`. They remain in coverage and
denominators; they are **not** collapsed into ordinary zero scores.

## Relation-level classifications

For unique proposed triples (when scored):

| Class | Meaning |
|---|---|
| `TRUE_POSITIVE` | Canonical form matches remaining expected |
| `WRONG_RELATION` | Same ordered subject+object, different relation |
| `REVERSED_DIRECTION` | Same relation, swapped ends (**asymmetric only**) |
| `UNSUPPORTED_ASSERTION` | In-universe, not expected, not WR/RD |
| `DUPLICATE_ASSERTION` | Canonical form already seen (includes symmetric reverse) |
| `OUT_OF_UNIVERSE_ASSERTION` | Identifier or relation outside closed universe |

Expected triples not recovered: `FALSE_NEGATIVE`.

Exactly one primary class per proposed triple occurrence.

## Classification precedence

1. `DUPLICATE_ASSERTION` (canonical form already in seen unique set)
2. `OUT_OF_UNIVERSE_ASSERTION`
3. `TRUE_POSITIVE` (canonical form in remaining expected)
4. `WRONG_RELATION`
5. `REVERSED_DIRECTION` (asymmetric only)
6. `UNSUPPORTED_ASSERTION`

## Canonical matching

Exact TP requires equality of the **canonical** triple
(`subject_id`, `relation`, `object_id`) after:

- strip on proposal parse
- min/max endpoint reordering **only** for relations in `symmetric_relations`

No embeddings, fuzzy match, LLM judge, paraphrase, substring, or identifier-only
overlap.

## Order and duplicates

- Scoring independent of proposal and expected order.
- Duplicates count once for set comparison.
- Duplicates recorded separately; never earn extra credit; cannot clear FNs.
- Duplicate-heavy output cannot outperform the same unique set without duplicates.

## Primary score

```text
primary_score = TP / (
  expected_n
  + wrong_relation_n
  + reversed_direction_n
  + unsupported_assertion_n
  + out_of_universe_assertion_n
)
```

Properties:

- Range `[0, 1]` when defined.
- Duplicates excluded from denominator (unique non-true classes only).
- False negatives represented via `expected_n`.
- Every additional non-true unique assertion weakly decreases the score.
- Malformed / non-observed: `primary_score = null` with machine-readable reason.

Zero denominator → `null` + `ZERO_DENOMINATOR` (no favorable substitute).

## Derived metrics

```text
precision = TP / unique_scored_proposals
recall    = TP / expected_n
f1        = 2PR / (P + R)
```

Zero-denominator cases use `null` + explicit reason codes
(`ZERO_DENOMINATOR_PRECISION`, `ZERO_DENOMINATOR_RECALL`, `UNDEFINED_COMPONENT`).
When both P and R are 0.0, f1 = 0.0.

## Exact match flag

`exact_relation_set_match = true` only when:

- every expected triple recovered
- no wrong relations, reversed directions, unsupported, out-of-universe, or duplicates
- inference completed and parseable
- `TP == expected_n` and `expected_n > 0`

Verbose correct set + extras is **not** an exact match.

## Shotgun resistance

Monotonicity invariant:

```text
∀ proposal sets P, ∀ non-true assertion x ∉ P:
  primary_score(P ∪ {x}) ≤ primary_score(P)
```

Proved offline over a frozen 2×2×2 relation universe (256 subsets) in
`test_property_shotgun_monotonicity_over_frozen_universe`.

## Task-contract fail-closed

- empty expected where not explicitly allowed
- unknown expected identifier or relation
- duplicate expected triples
- malformed symmetry metadata
- missing `task_id` or contract version
- proposed structured data violating assertion schema → `MALFORMED_ASSERTIONS`

Task-contract errors are not model failures.

## Integration boundary

`score_cell` / `score_planned_cells` consume typed inference status + parsed
assertions and emit one terminal score record per cell.

No model execution, matrix activation, or condition-level scientific headlines.

## Module

`src/conditioned_kernel/relational_scorer.py`
