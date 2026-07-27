# RUN 00.6F — Dry Plan

**Artifact:** `experiments/manifests/m0_candidate_v1_plan.json`  
**Generator:** `build_dry_plan(manifest)` — does not import or call model clients.

## Summary (at freeze)

| Field | Value |
|---|---|
| manifest_id | `ck.m0.candidate.v1` |
| manifest_sha256 | `92c9b2431fc0edd2947c38fe43c06bdec793c4e9254701cd08549a223453bb6b` |
| repository_commit | `5826b334a1fcc56e859e4fef79e8ce1e140abf20` |
| model_tag | `qwen2.5:0.5b` |
| generation_parameters | temperature=0.0, seed=0, num_ctx=2048 |
| eligible_tasks | `live_plumbing_01` |
| excluded_tasks | 16 continuity corpus tasks |
| planned_cell_count | **4** |
| planned_primary_pairs_n | **1** |
| by condition | C0:1, C1:1, C2:1, C3:1 |
| authorization_status | `unratified` |
| scientific_completion | `false` |
| headline_eligible | `false` |
| no_model_execution | `true` |

## Exclusion pattern

All 16 tasks in `experiments/probes/continuity_tasks.json` lack both:

- `continuity_universe`
- `ck.task_dep.v1` annotation

Reasons recorded: `MISSING_CONTINUITY_UNIVERSE`, `MISSING_TASK_DEP_ANNOTATION`.

## Proof of no model invocation

- Dry-plan / manifest modules do not import `conditioned_kernel.generate`
- No Ollama / httpx client calls in 00.6F path
- Tests: `test_dry_plan_and_manifest_modules_do_not_import_generate`
