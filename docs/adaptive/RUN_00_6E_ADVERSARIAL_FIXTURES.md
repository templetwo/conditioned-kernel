# RUN 00.6E — Adversarial Fixtures

**Fixture file:** `tests/fixtures/relational_scorer_cases.json`  
**Runner:** `tests/test_run_00_6e_relational_scorer.py`  
**Policy:** `scientific_status=scorer_validation_only`, `headline_eligible=false`

## Universe summaries

### base_gold (`rel_task_01`)

- Subjects: `ent_A`, `ent_B`, `ent_C`
- Objects: `ent_A`, `ent_B`, `ent_C`, `ent_D`
- Relations: `remains_open`, `depends_on`, `blocks`
- Expected: `ent_A / remains_open / ent_B`
- Symmetric: none

### multi_gold (`rel_task_multi`)

- Same universe
- Expected: three triples (open, depends_on, blocks chain)

### symmetric_gold (`rel_task_sym`)

- Expected: `ent_A / linked_to / ent_B`
- `linked_to` marked symmetric

### property_universe (`rel_prop_01`)

- 2 subjects × 2 objects × 2 relations = 8 triples
- Expected: `s1 / r1 / o1`
- Used for exhaustive monotonicity proof

## Case catalog (30)

| # | Name | Intent | Expected outcome |
|---|---|---|---|
| 1 | perfect_one_relation | clean single TP | SCORED, score=1, exact=true |
| 2 | perfect_multi_relation | clean multi TP | SCORED, score=1, exact=true |
| 3 | empty_assertion_list | no proposals | SCORED, score=0, FN=1 |
| 4 | one_correct_one_missing | partial multi | TP=1, FN=2 |
| 5 | wrong_relation_correct_subject_object | WR not TP | WR=1, FN=1, score=0 |
| 6 | reversed_subject_object | RD not TP | RD=1, FN=1 |
| 7 | unsupported_in_universe | UNSUP | UNSUP=1 |
| 8 | out_of_universe_subject | OOU subject | OOU=1 |
| 9 | out_of_universe_object | OOU object | OOU=1 |
| 10 | out_of_universe_relation | OOU relation | OOU=1 |
| 11 | exact_plus_unsupported | extras hurt | score < 1, exact=false |
| 12 | exact_plus_duplicate | dups no credit | TP=1, dup≥1, exact=false |
| 13 | shotgun_all_identifiers_false_triples | identifier shotgun | TP=0, score=0 |
| 14 | every_relation_on_one_pair | WR + TP | TP=1, WR=2, score=1/3 |
| 15 | prose_identifiers_no_structured | no prose parse | empty structured → score=0 |
| 16 | duplicate_only_correct | dups of TP | TP=1, no extra credit |
| 17 | duplicate_only_incorrect | dups of WR | WR=1, dups counted |
| 18 | same_proposal_order_a | order A | matches order B |
| 19 | same_proposal_order_b | order B | matches order A |
| 20 | malformed_json_proxy | malformed | MALFORMED, score=null |
| 21 | wrong_output_schema_key | schema key | MALFORMED, score=null |
| 22 | empty_final_response | no final | NO_FINAL_RESPONSE, null |
| 23 | timeout | timeout | TIMEOUT, null |
| 24 | transport_error | transport | TRANSPORT_ERROR, null |
| 25 | invalid_response | invalid | INVALID_RESPONSE, null |
| 26 | no_final_response | no final | NO_FINAL_RESPONSE, null |
| 27 | task_contract_duplicate_expected | gold dups | TASK_CONTRACT_ERROR |
| 28 | task_contract_unknown_identifier | gold unknown id | TASK_CONTRACT_ERROR |
| 29 | symmetric_relation_reverse_is_tp | symmetry | TP=1, exact=true |
| 30 | asymmetric_relation_incorrectly_reversed | asymmetric RD | RD=1, not TP |

## RUN 00.6E.1 symmetric both-directions cases (tests)

| Case | Expected outcome after amendment |
|---|---|
| reverse only of symmetric expected | TP=1, score=1.0, exact=true |
| both directions of symmetric expected | TP=1, DUP=1, UNSUP=0, score=1.0, exact=false |
| three alternating restatements | TP=1, DUP=2, score=1.0, exact=false |
| asymmetric reverse (undeclared) | RD=1, TP=0 (unchanged) |
| multi-relation same ordered pair | either expected is TP not WR; third relation is WR |
| opposite expected source order | identical `expected_relation_hash` |
| raw vs unique hashes | raw multiset differs on both-dir; unique set collapses |

## Property-test universe

```text
subjects = {s1, s2}
objects  = {o1, o2}
relations = {r1, r2}
universe size = 8 triples
subsets = 256
expected = (s1, r1, o1)
non_true = universe \ {expected}
```

For every proposal set `P` and every non-true `x ∉ P`:

```text
primary_score(P ∪ {x}) ≤ primary_score(P)
```

Result: zero monotonicity violations (see implementation receipt).

## What these fixtures deliberately refuse

- Semantic / paraphrase credit for “same idea, different wording”
- Identifier bag-of-words credit
- Embedding similarity
- LLM-as-judge grading
- Promoting timeout / transport / malformed into zero scores that look “scored”
- Letting shotgun extras improve primary_score
- Letting duplicates clear false negatives

## Scientific policy on fixtures

Fixture JSON header and every emitted record:

```text
scientific_status = scorer_validation_only
scientific_completion = false
headline_eligible = false
headline_ineligible_reason = m0_manifest_and_admission_contract_not_yet_ratified
```

No fixture enters a scientific denominator. M0 remains NO-GO.
