# RUN 00.6F — M0 Candidate Manifest Spec

**Status:** candidate freeze (unratified)  
**Branch:** `grok/ck-run-00-6f-ledger-manifest`  
**Base:** `5826b33`  
**Manifest ID:** `ck.m0.candidate.v1`  
**Schema:** `ck.m0_manifest.v1`  
**M0:** `NO-GO`  
**ExecutionScope.SCIENTIFIC_EXPERIMENT:** not activated  
**experiment_contract_id:** not minted

## Purpose

Byte-freeze the first M0 **candidate** planned-cell set and prove offline that
every planned cell remains visible through terminal scoring and admission
accounting. This run does **not** execute the experiment.

## Founding invariant

```text
∀ cell in frozen manifest: planned_terminal_count(cell_id) == 1
```

A planned cell may succeed or fail; it may never disappear.

## Inclusion rule (`ck.m0.eligibility.static_v1`)

A task is eligible **only if** all hold before any model output:

- stable `task_id`
- closed subject / object / relation universe (`continuity_universe`)
- one or more frozen expected relations (from `valid_combinations`)
- `ck.task_dep.v1` annotation with:
  - ≥1 `REQUIRED_TASK_FACT`
  - ≥1 `REQUIRED_OPERATIONAL_STATE`
  - ≥1 `FORBIDDEN_ANSWER_LEAKAGE`
- valid relational scorer gold contract (`ck.task_rel.v1`)
- no unresolved schema ambiguity

No cherry-picking by difficulty or prior model behavior.

Excluded tasks remain in the exclusion ledger with reasons, source path, and
source SHA-256.

## Frozen model and parameters

| Field | Value |
|---|---|
| model_tag | `qwen2.5:0.5b` |
| temperature | `0.0` |
| seed | `0` |
| num_ctx | `2048` |
| replicates per cell | `1` (`replicate_id=0`) |
| retries in manifest | `0` |
| replacement runs | forbidden |

Unhonored frozen options → machine-readable runtime/provenance failure (future
execution). Future retries require a **new** planned cell ID.

## Conditions (per included task)

| ID | Role |
|---|---|
| `C0_bare` | bare natural baseline (descriptive only vs C3) |
| `C1_budget_matched_bare` | primary control (exact complete-request byte length) |
| `C2_instruction_identical` | secondary diagnostic control |
| `C3_static_ck` | static Conditioned Kernel treatment |

### Contrasts

- **Primary:** C3 vs C1 — structured substrate continuity under equal finalized request-byte length  
- **Secondary:** C3 vs C2 — shared instructions; byte difference disclosed  
- **Descriptive only:** C3 vs C0 — confounded; never primary causal estimate  

## Planned-cell identity

```text
cell_id = SHA256(canonical_json({
  condition_id, manifest_id, model_tag,
  packet_contract_version, replicate_id,
  scorer_schema_version, seed, task_id
}))
```

Key order and source mapping order do not affect `cell_id`. Changing any
identity field changes `cell_id`.

## Pairing

Every C3 cell pairs with exactly one C1 cell (same task, replicate). No orphan
primary cells. Pair agreement requirements are documented for execution-time
verification (task facts, schema, byte length, provenance).

## Authorization

`authorization_status = unratified`. Future receipt must include:

- manifest_id, exact manifest SHA-256  
- authorizing principal, timestamp  
- experiment_contract_id  
- authorized model, authorized planned-cell count  

RUN 00.6F does **not** create that receipt.

## Module

`src/conditioned_kernel/m0_manifest.py`  
Artifacts: `experiments/manifests/m0_candidate_v1{,_exclusions,_plan}.json`
