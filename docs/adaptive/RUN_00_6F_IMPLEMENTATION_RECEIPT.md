# RUN 00.6F — Implementation Receipt

**Date:** 2026-07-27  
**Branch:** `grok/ck-run-00-6f-ledger-manifest`  
**Starting commit:** `5826b334a1fcc56e859e4fef79e8ce1e140abf20`  
**Disposition:** M0 candidate manifest frozen (unratified); ledger integration +
admission accounting offline. No models. No M0 execution.

## 1. Task discovery and eligibility rule

**Sources (enumerated, no new tasks):**

- `experiments/probes/continuity_tasks.json` (16 tasks)
- `experiments/probes/live_plumbing_task.json` (1 task)

**Annotations:** `tests/fixtures/*.json` with `version=ck.task_dep.v1`

**Rule:** `ck.m0.eligibility.static_v1` — see `RUN_00_6F_M0_MANIFEST_SPEC.md`.

## 2. Included tasks (after 00.6F.1)

| task_id | source | annotation |
|---|---|---|
| `live_plumbing_01_m0_v1` | `experiments/probes/m0_task_contracts/live_plumbing_01_m0_v1.json` | `tests/fixtures/m0_task_dep/live_plumbing_01_m0_v1.json` |

Expected relations (conjunctive `all_required`): both closed-universe supported
relations; instructions require every supported assertion.

## 3. Excluded tasks (complete after 00.6F.1)

- 16 free-text continuity corpus tasks → `TASK_REQUIRES_REDESIGN` (+ missing universe/annotation/schema)  
- Original `live_plumbing_01` → `INSTRUCTION_GOLD_SEMANTICS_MISMATCH` / ambiguous expected  

Ledger: `experiments/manifests/m0_candidate_v1_exclusions.json`  
Table: `RUN_00_6F_1_CORPUS_ELIGIBILITY_TABLE.md`

## 4. Model / replicate / retry freeze

- model: `qwen2.5:0.5b`
- temperature 0.0, seed 0, num_ctx 2048
- one replicate (`0`) per task-condition
- zero retries; no replacement runs

## 5. Conditions and contrasts

C0 / C1 / C2 / C3 as in control contract enum values.  
Primary C3↔C1; secondary C3↔C2; descriptive C3↔C0.

## 6. Manifest schema and SHA-256

- schema: `ck.m0_manifest.v1`
- id: `ck.m0.candidate.v1`
- **manifest_sha256 (00.6F.1):** `9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922`

## 7. Planned-cell schema and count

- schema: `ck.planned_cell.v1`
- **planned_cell_count = 4**
- **planned_primary_pairs_n = 1**
- cell_id = SHA-256(canonical identity payload)

## 8. TerminalLedger integration path

```text
M0LedgerSession(manifest)
  → TerminalLedger(ManifestCell with cell_id_override)
  → terminalize(IntegrationInputs) → ck.terminal_cell.v1 + ledger row
```

Reason codes: `UNPLANNED_CELL`, `DUPLICATE_TERMINALIZATION`.

## 9. Terminal classification mapping

See `RUN_00_6F_LEDGER_INTEGRATION_SPEC.md`. Null scores preserved for all
non-SCORED classifications.

## 10. Admission formulas and headline gate

See `RUN_00_6F_ADMISSION_CONTRACT.md`. Structural 100% primary-pair gate; no
efficacy threshold.

## 11. Test-first failures (pre-implementation)

At `5826b33` before this run, the repository lacked:

1. M0 planned-cell → timeout terminal null-score path through a dedicated adapter  
2. Stable `DUPLICATE_TERMINALIZATION` / `UNPLANNED_CELL` reason codes on ledger  
3. SHA-256 planned-cell IDs for M0  
4. primary-pair coverage + headline blocking admission evaluator  
5. unratified manifest authorization gate  

These are now covered by `tests/test_run_00_6f_*.py` (50 tests).

## 12. Adversarial fixture results

Covered offline:

- all cells scored  
- C1 timeout / C3 control fail / packet fail / scorer-internal  
- missing provenance  
- duplicate / unplanned terminals  
- wrong auth hash  
- missing primary partner  
- full failure matrix retains denominator  

## 13. Commands and results

```text
python -m pytest -q tests/test_run_00_6f_manifest.py \
  tests/test_run_00_6f_ledger_integration.py \
  tests/test_run_00_6f_admission.py
50 passed

python -m pytest -q
374 passed in 4.02s
# baseline 324 at 5826b33; +50 from 00.6F

python -m ruff check src/conditioned_kernel/m0_*.py \
  src/conditioned_kernel/outcomes.py tests/test_run_00_6f_*.py
All checks passed!

python -m mypy --follow-imports=skip \
  src/conditioned_kernel/m0_manifest.py \
  src/conditioned_kernel/m0_ledger_integration.py \
  src/conditioned_kernel/m0_admission.py
Success: no issues found in 3 source files
```

## 14. Proof no models invoked

- No generate/ollama imports in m0 modules  
- Synthetic score_cell fixtures only  
- Dry plan `no_model_execution=true`  
- execution_scope=`dry_planning_only`

## 15. Exact files changed

| Path | Action |
|---|---|
| `src/conditioned_kernel/m0_manifest.py` | created |
| `src/conditioned_kernel/m0_ledger_integration.py` | created |
| `src/conditioned_kernel/m0_admission.py` | created |
| `src/conditioned_kernel/outcomes.py` | narrow: cell_id_override; UNPLANNED/DUPLICATE reason prefixes |
| `tests/test_run_00_6f_manifest.py` | created |
| `tests/test_run_00_6f_ledger_integration.py` | created |
| `tests/test_run_00_6f_admission.py` | created |
| `experiments/manifests/m0_candidate_v1.json` | created |
| `experiments/manifests/m0_candidate_v1_exclusions.json` | created |
| `experiments/manifests/m0_candidate_v1_plan.json` | created |
| `docs/adaptive/RUN_00_6F_*.md` | created (6 files) |

## 16. Negative-action confirmation

Untouched semantics:

- relational scorer formula / classifications  
- C0–C3 control construction and byte-matching  
- continuity persistence / replay / events  
- prompts  
- no SCIENTIFIC_EXPERIMENT  
- no experiment_contract_id  
- no M0 model execution  
- no adaptive riverbed  
- no thresholds / stats / UI  

## 17. Unresolved decisions for Anthony

1. **Expand eligibility:** annotate more continuity tasks (universe + task_dep + expected relations) before M0, or run M0 on `live_plumbing_01` only?  
2. **Expected set for live_plumbing:** both valid_combinations as expected (current) vs single gold triple.  
3. **experiment_contract_id** string to mint at authorization time.  
4. **Model generality:** confirm `qwen2.5:0.5b` remains the only authorized model for first M0.  
5. Whether structurally admitted headlines may ever set report-level `headline_eligible=true` while `scientific_completion` stays false.  

## 18. Ready for independent adversarial review?

**Yes — RUN 00.6F is ready for independent adversarial review.**

Reviewers should:

- inspect exact manifest bytes and recalculate SHA-256  
- check planned-cell cardinality (4) and pair count (1)  
- reproduce timeout / control-failure retention  
- reproduce duplicate-terminalization rejection  
- reproduce headline blocking from one incomplete primary pair  
- confirm no model invocation  

Do not push until that review completes.

M0 remains NO-GO. Adaptive Riverbed remains HOLD. Stop after RUN 00.6F.
