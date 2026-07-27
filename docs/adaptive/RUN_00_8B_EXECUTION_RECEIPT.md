# RUN 00.8B — Execution Receipt

**Result class:** `COMMISSIONING_COMPLETE_WITH_PROVENANCE_LIMITATIONS`

## Plan identity

| Field | Value |
|---|---|
| commissioning_plan_id | `ck.run.00.8b.ollama.v1` |
| commissioning_plan_sha256 | `c0d2b3975dd1647ac6685491ce4e2ea5eae84d447962f1592b222fe175373ec1` |
| source_candidate | `ck.m0.candidate.v1` |
| source hash | `9ec3d37a177b6d403048d8d6441b70a7fcdc6b89a4336c29bcf9ac610d88e922` (unchanged) |

## Execution order

C0 → C1 → C2 → C3 (operational fixed order; not scientifically randomized)

## Per-cell outcomes (descriptive only)

| Condition | Classification | Parse | Score | Exact match | Duration (s) |
|---|---|---|---|---|---|
| C0_bare | MALFORMED_ASSERTIONS | WRONG_SCHEMA_KEY | null | null | ~0.64 |
| C1_budget_matched_bare | SCORED | STRUCTURED_ASSERTIONS | 0.0 | false | ~0.92 |
| C2_instruction_identical | SCORED | STRUCTURED_ASSERTIONS | 0.0 | false | ~0.85 |
| C3_static_ck | SCORED | STRUCTURED_ASSERTIONS | 1.0 | true | ~1.22 |

**NON-SCIENTIFIC PIPELINE DIAGNOSTIC only:** C3 score 1.0 on this gold-leaked
task is expected instrument behavior, **not** a substrate continuity effect.
No causal interpretation. No efficacy claim.

## Evidence chain

Every cell retained:

- packet complete bytes + packet receipt  
- control receipt  
- invocation intent  
- outbound Ollama request JSON + SHA-256  
- raw response + SHA-256  
- parse result  
- score adapter / score record where applicable  
- runtime provenance  
- terminal record  

## Ledger / process boundary

- Persistent ledger reopened in-process simulation: integrity ok  
- Duplicate terminalization: **rejected** (`DUPLICATE_TERMINALIZATION`)  
- Admission: ran; scientific labels remain false  

## Narrative (permitted)

One non-scientific commissioning run completed all four planned execution
cells through the real local Ollama path. This validates the instrument path
and evidence-retention behavior only. The task and contrast are known to be
scientifically invalid and no efficacy interpretation is permitted.

The requested generation options were recorded, but the runtime did not expose
sufficient evidence to confirm that every option was honored. Provenance is
therefore incomplete regarding option confirmation; no determinism claim is
permitted.
