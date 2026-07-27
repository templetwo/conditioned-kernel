# RUN 00.6D — Control Matrix (C0–C3)

## Condition definitions

| ID | Name | Description |
|---|---|---|
| **C0** | Bare | Minimal ordinary task prompt + required facts. Natural baseline. **Not** structure-isolating. |
| **C1** | Budget-matched bare | Same task facts, same instructions, same output schema, same runtime, **exact UTF-8 complete-request byte count** as C3; flat serialization; inert space padding; **no** persistent-state organization. |
| **C2** | Instruction-identical static | Same operative instructions, facts, schema as C3; **no** reconstructed continuity state; byte budget **measured and disclosed**, not forced equal. |
| **C3** | Static Conditioned Kernel | Verified-replayable accepted relations + deterministic packet compilation; no adaptive recompilation in this lane. |

## What each contrast isolates

| Contrast | Isolates | Does **not** isolate |
|---|---|---|
| **C3 vs C0** | Substrate-organized packet vs bare prompt | Pure structure — confounded by volume, instructions, schema |
| **C3 vs C1** | Structure of persistent-state organization under exact byte budget + shared facts/instructions/schema/runtime | Instruction wording (held fixed) |
| **C3 vs C2** | Presence of reconstructed continuity state under shared instructions/facts/schema | Exact byte budget (may differ; disclosed) |

## Governing causal question (C3 vs C1)

> When the same model receives the same task facts, instructions, output
> requirements, runtime settings, and exact UTF-8 byte budget, does organizing
> those materials through the Conditioned Kernel substrate change performance?

## Non-claims

- C0 is not a clean causal control for substrate structure.  
- Byte equality does not imply token equality.  
- No M0 headline is authorized by this documentation run.  
