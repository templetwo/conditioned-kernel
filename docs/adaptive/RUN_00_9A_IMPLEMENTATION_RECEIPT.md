# RUN 00.9A — Implementation Receipt

**Starting commit:** `9fbfe48b93a19d10b0a00575f59f368a3f3ec3b7`  
**Branch:** `grok/ck-run-00-9a-scientific-contract-freeze`  
**M0:** NO-GO · No models · No corpus · No authorization

## Delivered

- Claim ladder A–E; max claim **D**  
- Falsification table with weaken/invalidate/artifact classes  
- Estimand: **median_paired_difference** of C3−C1 on **exact_relation_set_match**  
- Condition supersession C0–C3  
- Gold non-saturation + anti-leak static analysis  
- Negative-control design (scrambled / irrelevant / A/A)  
- Task-selection independence freeze  
- N_min_eligible = **12**  
- State/packet two-stage freeze requirements (documented)  
- Replicate/order policy (1 rep; no false independence claim)  
- Claim-licensing language  
- Invalidation gates  
- `ck.m0_preregistration.v2` template (unratified)  
- Static fixtures + tests  

## Commands / verification

```text
PYTHONPATH=src python -m pytest -q tests/test_run_00_9a_scientific_contract.py
# 35 passed

PYTHONPATH=src python -m pytest -q
# 500 passed

python -m ruff check src/conditioned_kernel/m0_scientific_contract.py \
  src/conditioned_kernel/m0_task_eligibility_v2.py \
  src/conditioned_kernel/m0_leakage_analysis.py \
  src/conditioned_kernel/m0_preregistration_v2.py \
  tests/test_run_00_9a_scientific_contract.py
# All checks passed
```

No Ollama. No corpus. No execution manifest. No authorization.

## Files

| Path | Action |
|---|---|
| `src/conditioned_kernel/m0_scientific_contract.py` | created |
| `src/conditioned_kernel/m0_task_eligibility_v2.py` | created |
| `src/conditioned_kernel/m0_leakage_analysis.py` | created |
| `src/conditioned_kernel/m0_preregistration_v2.py` | created |
| `tests/test_run_00_9a_scientific_contract.py` | created |
| `tests/fixtures/m0_v2_static_cases.json` | created |
| `tests/test_run_00_8b_1_artifact_publication.py` | brittle count fix |
| `docs/adaptive/RUN_00_9A_*.md` | created (10) |

## Untouched

Retired candidate, 00.8B evidence, scorer arithmetic, no Ollama, no M0-v2 corpus.

## Ready for independent scientific review?

**Yes** — design freeze only; not execution authorization.
