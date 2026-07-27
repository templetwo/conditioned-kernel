# RUN 00.6E — Implementation Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6e-relational-scorer`  
**Starting commit:** `02a002773fb17e4939abca8612a4038c74a1d163`  
**Disposition:** closed-set relational scorer implemented offline; fixture-driven;
shotgun-resistant; scientifically incomplete by construction.  
**M0:** remains `NO-GO`  
**Adaptive Riverbed:** remains `HOLD`

## 1. Mission

Build the deterministic closed-set scorer required to evaluate whether a model
preserved the correct continuity relations.

- Offline only
- No model invocation
- No M0 / matrix / threshold tuning
- No changes to prompts, controls, continuity persistence, replay, receipt
  schemas, execution scopes, or adaptive behavior

## 2. Scorer schema version

`ck.relational_score.v1`

## 3. Exact primary score formula

```text
primary_score = TP / (
  expected_n
  + wrong_relation_n
  + reversed_direction_n
  + unsupported_assertion_n
  + out_of_universe_assertion_n
)
```

Mathematical review of the recommended formula:

- Perfect answer: `TP = expected_n`, penalties 0 → score 1.0.
- Empty proposals: `TP = 0`, denom = `expected_n` → 0.0 (when expected_n > 0).
- Shotgun extras increase unique non-true counts in the denominator only → score
  weakly decreases.
- Duplicates are **not** in the denominator and do not increase TP beyond one
  unique match → no extra credit.
- FNs are represented through `expected_n` (unrecovered expected remain in
  denom even when not listed as separate penalty terms).
- No defect identified that required substituting a different formula.

## 4. Zero-denominator rules

| Situation | Result |
|---|---|
| primary denom ≤ 0 | `primary_score=null`, reason `ZERO_DENOMINATOR` |
| unique_scored_proposals ≤ 0 | `precision=null`, `ZERO_DENOMINATOR_PRECISION` |
| expected_n ≤ 0 | `recall=null`, `ZERO_DENOMINATOR_RECALL` |
| P or R undefined | `f1=null`, `UNDEFINED_COMPONENT` |
| P=R=0.0 | `f1=0.0` |
| TIMEOUT / TRANSPORT / INVALID / NO_FINAL / MALFORMED / TASK_CONTRACT / INTERNAL | `primary_score=null` (not zero) |

## 5. Terminal status mapping

| Inference / parse state | Scoring status |
|---|---|
| completed + parseable | `SCORED` |
| timeout / TIMEOUT | `TIMEOUT` |
| transport_error / TRANSPORT_ERROR | `TRANSPORT_ERROR` |
| invalid_response / INVALID_RESPONSE | `INVALID_RESPONSE` |
| no_final_response / NO_FINAL_RESPONSE | `NO_FINAL_RESPONSE` |
| malformed assertions / null structured | `MALFORMED_ASSERTIONS` |
| gold/contract validation failure | `TASK_CONTRACT_ERROR` |
| unexpected exception | `SCORER_INTERNAL_ERROR` |

## 6. Relation-level classification precedence

1. `DUPLICATE_ASSERTION`
2. `OUT_OF_UNIVERSE_ASSERTION`
3. `TRUE_POSITIVE` (exact remaining expected, or reverse if relation ∈ symmetric)
4. `WRONG_RELATION` (same subject+object, different relation vs any expected)
5. `REVERSED_DIRECTION` (same relation, swapped ends; relation not symmetric)
6. `UNSUPPORTED_ASSERTION`

Unrecovered expected triples → `FALSE_NEGATIVE` list (not a proposal class).

## 7. Canonicalization and hashing

- Sort triples by `(subject_id, relation, object_id)`
- Canonical JSON: `sort_keys=True`, compact separators, UTF-8
- SHA-256 hex for expected set, proposed multiset-as-sorted-list, full records
- Proposal order and expected order do not affect hashes of sets / primary metrics

## 8. Shotgun-resistance proof

Bounded exhaustive property test over frozen 8-triple universe:

- subjects `{s1,s2}`, objects `{o1,o2}`, relations `{r1,r2}`
- 256 proposal subsets
- every non-true `x` not already in `P`
- invariant: `primary_score(P ∪ {x}) ≤ primary_score(P)`

**Result:** 0 violations.

Additional unit proofs:

- identifier shotgun (case 13) → TP=0, score=0, below minimal correct
- exact + unsupported (case 11) → score strictly below clean exact
- duplicate correct / incorrect → no extra credit
- exact match requires no extras or duplicates

## 9. Property-test universe and result

| Item | Value |
|---|---|
| Universe size | 8 triples |
| Subsets checked | 256 |
| Expected | `(s1, r1, o1)` |
| Monotonicity violations | **0** |
| Test | `test_property_shotgun_monotonicity_over_frozen_universe` |

## 10. Adversarial fixture results

All 30 frozen cases emit exactly one terminal record via
`test_all_fixture_cases_emit_terminal_record` and
`test_22_every_planned_cell_one_terminal_record`.

Spot checks:

| Case | scoring_status | primary_score |
|---|---|---|
| perfect_one_relation | SCORED | 1.0 |
| shotgun_all_identifiers_false_triples | SCORED | 0.0 |
| wrong_relation_correct_subject_object | SCORED | 0.0 |
| reversed_subject_object | SCORED | 0.0 |
| timeout | TIMEOUT | null |
| task_contract_duplicate_expected | TASK_CONTRACT_ERROR | null |
| symmetric_relation_reverse_is_tp | SCORED | 1.0 |

## 11. Test-first critical cases

Mission required failing tests before production code for:

1. Identifier shotgunning
2. Correct identifiers, wrong relation
3. Reversed direction
4. Unsupported extra reduces primary score
5. Timeout visible terminal with `primary_score=null`

**Session note:** `relational_scorer.py` was authored in the same working session
prior to fixture/test finalization (continuation after context compaction). The
five critical cases are encoded as tests 02–04, 12, and 18 and pass against the
frozen scorer. No post-hoc formula change was required after tests landed.

If the scorer module is deleted and only tests remain, those five fail for
`ImportError` / missing symbols — i.e. they are real requirements, not
tautologies over soft stubs.

## 12. Commands and results

```text
python -m pytest -q tests/test_run_00_6e_relational_scorer.py
51 passed in 0.10s

python -m pytest -q
302 passed in 3.93s
# baseline at 02a0027 was 251; +51 from 00.6E

python -m ruff check src/conditioned_kernel/relational_scorer.py \
  tests/test_run_00_6e_relational_scorer.py
All checks passed!

python -m mypy --follow-imports=skip src/conditioned_kernel/relational_scorer.py
Success: no issues found in 1 source file
```

## 13. Proof no models were invoked

- Scorer module source contains no `ollama`, `httpx`, or remote client usage
  (`test_no_model_invocation_marker`).
- All tests offline fixtures; no live plumbing smoke; no matrix; no M0.
- No `ExecutionScope.SCIENTIFIC_EXPERIMENT` activation.

## 14. Exact files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/relational_scorer.py` | created |
| `tests/fixtures/relational_scorer_cases.json` | created |
| `tests/test_run_00_6e_relational_scorer.py` | created |
| `docs/adaptive/RUN_00_6E_RELATIONAL_SCORER_SPEC.md` | created |
| `docs/adaptive/RUN_00_6E_SCORING_SCHEMA.md` | created |
| `docs/adaptive/RUN_00_6E_ADVERSARIAL_FIXTURES.md` | created |
| `docs/adaptive/RUN_00_6E_IMPLEMENTATION_RECEIPT.md` | created |
| `docs/adaptive/RUN_00_6E_CHANGE_MAP.md` | created |

## 15. Negative-action confirmation

Controls, persistence, replay, prompts, thresholds, scientific scope, M0, and
adaptation remained untouched:

- no edits to `control_contract.py`
- no edits to `continuity_*.py` / store / replay / gate / live
- no edits to `generate.py` / prompts
- no edits to receipt schemas or `ExecutionScope` activation
- no score.py mutation of prior continuity lexical scorer (new module only)
- no Ollama / remote model calls
- no push (await independent adversarial review)

## 16. Ambiguities requiring Anthony’s ruling

1. **Symmetric reverse as exact match:** implemented — if relation is in
   `symmetric_relations` and the reverse is proposed, it is TP and can yield
   `exact_relation_set_match=true`. Confirm whether exact match should require
   the expected *orientation* even for symmetric relations.
2. **Proposal hash includes duplicates vs unique only:** currently hashes the
   full raw proposal multiset after sort (duplicates affect hash, not primary
   score). Confirm preferred audit hash surface.
3. **WRONG_RELATION vs multiple expected with same subject/object:** if two
   expected triples share subject+object with different relations, a single
   wrong-relation proposal is still classified WRONG_RELATION once; both
   expected remain FN until exact TP recovered. Confirm acceptable.
4. **Predicate alias:** `predicate_id` accepted as alias for `relation`. Confirm
   freeze or remove.
5. **Integration depth:** only `score_cell` / `score_planned_cells` — no ledger
   auto-wire. Confirm next run should attach scores into TerminalLedger rows.

## 17. Ready for independent adversarial review?

**Yes — RUN 00.6E is ready for independent adversarial review.**

Do not push until that review examines the implementation.

M0 remains NO-GO. Stop after RUN 00.6E.
