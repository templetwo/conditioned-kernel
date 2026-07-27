# RUN 00.6F.1 — Gold-Contract Alignment and Full Corpus Manifest Freeze

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6f-ledger-manifest`  
**Starting commit:** `a5d8ed03b40373d3c84954da03f942066ed1eaf4`  
**Amends:** RUN 00.6F  
**M0:** remains `NO-GO`  
**Adaptive:** remains `HOLD`

## 1. Original 0.5 ceiling reproduction

Under 00.6F, `live_plumbing_01` gold treated both `valid_combinations` as conjunctive expected:

```text
expected_n = 2
proposed one valid relation (instruction-following) → TP=1, FN=1
primary_score = 1 / (2 + 0 penalties) = 0.5
```

The only way to score 1.0 was to emit **both** alternatives, contrary to the
smoke task instruction (“Select a valid closed-set continuity relation”).

Recorded by `test_6f1_defect_original_one_relation_scores_half_against_dual_conjunctive_gold`.

## 2. Exact instruction / gold mismatch

| Side | Content |
|---|---|
| Instruction (original) | choose **one** valid relation |
| Gold (00.6F) | **two** relations required conjunctively |
| Scorer | unchanged conjunctive `all_required` set match |

## 3. Corrected `all_required` contract

M0 v1 eligible gold:

```text
expected_relation_semantics = all_required
```

Only value accepted. Rejected: `one_of`, `choose_any`, `alternatives`,
`unspecified`, unknown → `UNSUPPORTED_GOLD_SEMANTICS`.

Rules:

- Explicit `expected_relations` required (never silently promote `valid_combinations`)
- When `expected_n > 1`, instructions must require every supported assertion
- Choose-one instructions + multi gold → `INSTRUCTION_GOLD_SEMANTICS_MISMATCH`
- Scorer unchanged (`ck.relational_score.v1` conjunctive)

## 4. live_plumbing_01 disposition (Path A)

| Artifact | Status |
|---|---|
| `experiments/probes/live_plumbing_task.json` | **unchanged** historical smoke |
| Eligibility of `live_plumbing_01` | **EXCLUDED** (`INSTRUCTION_GOLD_SEMANTICS_MISMATCH`, `AMBIGUOUS_EXPECTED_RELATIONS`, `MISSING_EXPECTED_RELATIONS`, `UNSUPPORTED_GOLD_SEMANTICS`) |
| Successor | `live_plumbing_01_m0_v1` |

Successor contract:

- path: `experiments/probes/m0_task_contracts/live_plumbing_01_m0_v1.json`
- annotation: `tests/fixtures/m0_task_dep/live_plumbing_01_m0_v1.json`
- instructions: return **every** supported continuity assertion
- gold: both `remains_open` and `references` (conjunctive)
- semantics: `all_required`
- output_schema_id: `continuity_assertions_v1`

Following the successor instructions yields `primary_score=1.0`.

## 5. output_schema_id eligibility correction

Fail-open path removed. Eligible tasks require nonempty known
`output_schema_id` (annotation and/or task field).

| Condition | Reason |
|---|---|
| missing / empty | `MISSING_OUTPUT_SCHEMA_ID` |
| not in known set | `UNKNOWN_OUTPUT_SCHEMA_ID` |

Known: `continuity_assertions_v1`.

## 6. Corpus discovery and annotation results

| Metric | Count |
|---|---|
| Discovered | **18** |
| Annotated (ck.task_dep.v1 present) | 2 (`live_plumbing_01`, `live_plumbing_01_m0_v1`) |
| Included | **1** (`live_plumbing_01_m0_v1`) |
| Excluded | **17** |

Sources:

- `experiments/probes/continuity_tasks.json` (16 free-text tasks)
- `experiments/probes/live_plumbing_task.json` (original smoke)
- `experiments/probes/m0_task_contracts/*.json` (versioned M0 contracts)

The 16 continuity corpus tasks use free-text `answer_key` / `must_mention_any`.
No closed relation gold exists without inventing structure → excluded with
`TASK_REQUIRES_REDESIGN` (honest; no guessed triples).

Full table: `RUN_00_6F_1_CORPUS_ELIGIBILITY_TABLE.md`.

## 7. Regenerated manifest

```text
manifest_id     = ck.m0.candidate.v1
authorization   = unratified
execution_scope = dry_planning_only
experiment_contract_id = null
scientific_completion  = false
headline_eligible      = false
model_tag       = qwen2.5:0.5b
temperature     = 0
seed            = 0
num_ctx         = 2048
planned_cells   = 4   (= 4 × 1)
primary_pairs   = 1
manifest_sha256 = 9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922
```

## 8. Report-policy invariant

```text
headline_eligible == true  ⇒  scientific_completion == true
```

`evaluate_admission` never sets report `headline_eligible` true while
`scientific_completion` is false. Structural pair readiness is reported
separately as `primary_headline_structurally_ready`.

## 9. Test-first failures (pre-amendment at a5d8ed0)

1. Dual-conjunctive gold + one-relation proposal → score 0.5 (reproduced)  
2. Missing `output_schema_id` could pass (fail-open)  
3. Unspecified / one_of semantics not gated  

Now covered by `tests/test_run_00_6f_1_gold_corpus.py`.

## 10. Commands and results

```text
pytest -q tests/test_run_00_6f_1_gold_corpus.py \
  tests/test_run_00_6f_manifest.py \
  tests/test_run_00_6f_ledger_integration.py \
  tests/test_run_00_6f_admission.py
68 passed

pytest -q
392 passed
# 374 at a5d8ed0 + 18 from 00.6F.1

ruff / mypy on amended modules → clean
```

## 11. Proof no models

- Offline eligibility + scorer fixtures only  
- No generate/ollama invocation  
- Dry planning scope only  

## 12. Files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/m0_manifest.py` | gold semantics, schema gate, discovery |
| `src/conditioned_kernel/m0_admission.py` | report-policy invariant |
| `experiments/probes/m0_task_contracts/live_plumbing_01_m0_v1.json` | created |
| `tests/fixtures/m0_task_dep/live_plumbing_01_m0_v1.json` | created |
| `experiments/manifests/m0_candidate_v1*.json` | regenerated |
| `tests/test_run_00_6f_1_gold_corpus.py` | created |
| `tests/test_run_00_6f_manifest.py` | updated |
| `tests/test_run_00_6f_admission.py` | updated |
| `docs/adaptive/RUN_00_6F_1_*.md` | created |
| `docs/adaptive/RUN_00_6F_*.md` | updated |

## 13. Untouched

Frozen scorer, controls, continuity, ledger architecture, generation parameters,
experiment scope, M0 execution, adaptive work — **not modified**.

## 14. Anthony decisions remaining

1. Accept single-task (`live_plumbing_01_m0_v1`) M0 candidate after redesign of free-text corpus, or redesign N continuity tasks into closed-set contracts before authorization.  
2. Whether dual-relation conjunctive gold is the desired scientific claim for the plumbing successor.  
3. experiment_contract_id string at authorization.  

## 15. Ready for final independent review of 00.6F?

**Yes, for focused re-review of 00.6F + 00.6F.1** (gold alignment, schema gate,
corpus honesty, regenerated hash, cardinality, no models).

Do not push until independent review completes the checklist in the mission.

M0 remains NO-GO. Stop after RUN 00.6F.1.
