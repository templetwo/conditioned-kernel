# RUN 00.6E.1 — Symmetric Relation Canonicalization Amendment

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6e-relational-scorer`  
**Starting commit:** `ce9ab1b5dd9733cda838ea49ac8126600d95d0fc`  
**Amends:** RUN 00.6E (closed-set relational scorer)  
**M0:** remains `NO-GO`  
**Adaptive Riverbed:** remains `HOLD`  
**Scientific experiment scope:** `NOT AUTHORIZED`

## 1. Exact original defect reproduction

At `ce9ab1b`, for a relation declared in `symmetric_relations`:

```text
expected:  A / related_to / B
proposed:  A / related_to / B
           B / related_to / A
```

Scorer returned:

| Field | Defect value |
|---|---|
| `true_positive_n` | 1 |
| `duplicate_assertion_n` | 0 |
| `unsupported_assertion_n` | **1** |
| `false_negative_n` | 0 |
| `primary_score` | **0.5** |
| `exact_relation_set_match` | false |

Classifications: `TRUE_POSITIVE`, then `UNSUPPORTED_ASSERTION`.

Root cause: uniqueness and matching used raw directed triples. The reverse of a
symmetric true fact was not recognized as the same canonical assertion once the
forward direction had been consumed as TP, so it fell through to
`UNSUPPORTED_ASSERTION` and entered the primary-score penalty denominator.

## 2. Canonical symmetric-fact definition

For a relation **explicitly** listed in `symmetric_relations`:

```text
canonical_subject = min(subject_id, object_id)
canonical_object  = max(subject_id, object_id)
canonical fact    = canonical_subject / relation / canonical_object
```

Thus `A / related_to / B` and `B / related_to / A` are the **same** fact.

For relations **not** in `symmetric_relations`, subject/object order is preserved
exactly (no min/max).

Implemented by `canonicalize_triple(t, symmetric_relations)`.

Applied consistently to:

- expected relation validation (load-time canonicalization + uniqueness)
- proposal matching (TP against remaining expected)
- duplicate detection (`seen_unique` stores canonical forms)
- expected relation hashing
- proposed unique-set hashing
- property testing (universe remains asymmetric; non-regression)

Raw proposal order and raw multiset emissions are preserved for audit.

## 3. Classification behavior

### Case 1 — reverse direction only

```text
expected: A / related_to / B
proposed: B / related_to / A
```

| Field | Value |
|---|---|
| TP | 1 |
| FN | 0 |
| DUP | 0 |
| UNSUP | 0 |
| primary_score | 1.0 |
| exact_relation_set_match | **true** |

### Case 2 — both directions emitted

```text
expected: A / related_to / B
proposed: A / related_to / B
          B / related_to / A
```

| Field | Value |
|---|---|
| TP | 1 |
| DUP | 1 |
| UNSUP | **0** |
| FN | 0 |
| primary_score | **1.0** |
| exact_relation_set_match | **false** (duplicate emitted) |

Three alternating restatements → TP=1, DUP=2, score=1.0, exact=false.

### Case 3 — asymmetric (non-regression)

```text
expected: A / remains_open / B
proposed: B / remains_open / A
```

`remains_open` not in `symmetric_relations`:

| Field | Value |
|---|---|
| RD | 1 |
| FN | 1 |
| TP | 0 |

No behavior change from 00.6E for asymmetric relations.

### Precedence (unchanged order; symmetric-aware uniqueness)

1. `DUPLICATE_ASSERTION` — canonical form already in `seen_unique`
2. `OUT_OF_UNIVERSE_ASSERTION` — raw endpoints/relation
3. `TRUE_POSITIVE` — canonical form in remaining expected
4. `WRONG_RELATION` — same ordered subject+object, different relation
5. `REVERSED_DIRECTION` — asymmetric only
6. `UNSUPPORTED_ASSERTION`

## 4. Duplicate accounting

- Symmetric reverse of an already-accepted TP is `DUPLICATE_ASSERTION`.
- Duplicates never increase TP, never enter the primary-score denominator, and
  never clear false negatives.
- `exact_relation_set_match` requires `duplicate_assertion_n == 0`.
- Expected gold that lists both directions of a symmetric fact fails closed as
  `DUPLICATE_EXPECTED_RELATION`.

## 5. Hashing semantics

| Field | Meaning |
|---|---|
| `proposed_assertion_hash` | **Raw multiset** hash: sorted list of raw directed triples as emitted. Both directions and duplicate cardinality change this hash. |
| `proposed_unique_set_hash` | **Unique canonical set** hash: sorted unique canonical facts after symmetric collapse. Both directions of one symmetric fact yield the same unique-set hash as either direction alone. |
| `expected_relation_hash` | Hash of load-time canonical expected set. Opposite source orientation of a symmetric expected fact yields the same hash. |

Primary score formula **unchanged**.

## 6. Asymmetric non-regression proof

- Fixture case `asymmetric_relation_incorrectly_reversed` still yields RD=1, TP=0, FN=1.
- Relation not declared symmetric is never reordered by `canonicalize_triple`.
- Tests: `test_6e1_12_*`, `test_6e1_13_*`, `test_asymmetric_reverse_is_not_tp`.

## 7. Shared subject/object multi-relation fixture

Task with:

```text
A / relation_one / B
A / relation_two / B
```

- Proposing either expected relation alone → TP=1, WR=0, FN=1.
- Proposing both → TP=2, exact=true, score=1.0.
- Proposing `A / relation_three / B` (permitted, not expected) → WR=1.

Test: `test_6e1_18_multi_relation_same_pair_not_wrong_relation`.

## 8. Field contract

- Sole scorer predicate field: **`relation`**.
- `predicate_id` is **not** accepted as a runtime alias.
- Missing `relation` → `MALFORMED_ASSERTIONS`.

## 9. Property-test result

`test_property_shotgun_monotonicity_over_frozen_universe` — still **0 violations**
(asymmetric 8-triple universe, 256 subsets).

## 10. Commands and results

```text
# Pre-fix defect (at ce9ab1b logic):
# unsupported_assertion_n=1, primary_score=0.5  (documented above)

python -m pytest -q tests/test_run_00_6e_relational_scorer.py
73 passed in 0.14s

python -m pytest -q
324 passed in 3.92s
# prior 00.6E suite was 302; +22 from 00.6E.1

python -m ruff check src/conditioned_kernel/relational_scorer.py \
  tests/test_run_00_6e_relational_scorer.py
All checks passed!

python -m mypy --follow-imports=skip src/conditioned_kernel/relational_scorer.py
Success: no issues found in 1 source file
```

## 11. Exact files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/relational_scorer.py` | amended (canonicalize + unique hash + relation-only field) |
| `tests/test_run_00_6e_relational_scorer.py` | +00.6E.1 tests |
| `docs/adaptive/RUN_00_6E_1_SYMMETRIC_CANONICALIZATION_AMENDMENT.md` | created |
| `docs/adaptive/RUN_00_6E_RELATIONAL_SCORER_SPEC.md` | updated |
| `docs/adaptive/RUN_00_6E_SCORING_SCHEMA.md` | updated |
| `docs/adaptive/RUN_00_6E_ADVERSARIAL_FIXTURES.md` | updated |
| `docs/adaptive/RUN_00_6E_IMPLEMENTATION_RECEIPT.md` | updated |
| `docs/adaptive/RUN_00_6E_CHANGE_MAP.md` | updated |

## 12. Negative-action confirmation

- primary score formula **unchanged**
- no models / Ollama / remote inference
- no M0 / matrix
- no control or packet compilation edits
- no continuity persistence / replay edits
- no TerminalLedger broad wiring
- no thresholds / adaptive / embeddings / LLM judge
- no scientific experiment scope activation
- no push until independent review verifies the raw symmetric-duplicate case

## 13. Ready for focused re-review?

**Yes.** RUN 00.6E (with 00.6E.1) is ready for focused re-review of the
symmetric both-directions case.

M0 remains NO-GO. Stop after RUN 00.6E.1.
