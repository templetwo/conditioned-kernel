# RUN 00.6F — Dry Plan

**Artifact:** `experiments/manifests/m0_candidate_v1_plan.json`  
**Generator:** `build_dry_plan(manifest)` — does not import or call model clients.

## Summary (at 00.6F.1 freeze)

| Field | Value |
|---|---|
| manifest_id | `ck.m0.candidate.v1` |
| manifest_sha256 | `9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922` |
| repository_commit | `a5d8ed03b40373d3c84954da03f942066ed1eaf4` |
| model_tag | `qwen2.5:0.5b` |
| generation_parameters | temperature=0.0, seed=0, num_ctx=2048 |
| eligible_tasks | `live_plumbing_01_m0_v1` |
| excluded_tasks | 17 (16 free-text corpus + original `live_plumbing_01`) |
| planned_cell_count | **4** |
| planned_primary_pairs_n | **1** |
| by condition | C0:1, C1:1, C2:1, C3:1 |
| authorization_status | `unratified` |
| scientific_completion | `false` |
| headline_eligible | `false` |
| no_model_execution | `true` |

## Exclusion pattern

- 16 continuity corpus tasks: free-text `answer_key` → `TASK_REQUIRES_REDESIGN` (no invented gold)  
- Original `live_plumbing_01`: instruction/gold mismatch → excluded; historical smoke unchanged  
- Successor Path A: `live_plumbing_01_m0_v1` included under `all_required`  

See `RUN_00_6F_1_CORPUS_ELIGIBILITY_TABLE.md`.

## Proof of no model invocation

- Dry-plan / manifest modules do not import `conditioned_kernel.generate`
- No Ollama / httpx client calls in 00.6F path
- Tests: `test_dry_plan_and_manifest_modules_do_not_import_generate`
