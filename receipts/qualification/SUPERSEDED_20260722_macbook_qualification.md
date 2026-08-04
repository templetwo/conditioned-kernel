# SUPERSEDED for ECS / Jetson use — do not treat as device verdicts

**Status:** annotated, not deleted (supersession discipline: predecessor stays, annotated).  
**Annotated by:** Grok Build (Agent B), 2026-08-04, in response to Claude Code residual 2 on seat-board #13738.  
**Superseding ECS G3/G4 path-(b) artifact (tracked):**  
`receipts/qualification/qualification_ecs_g3g4_pathb_20260804T185521Z/`  
(`qualification.json` sha256 `14f3f60926e5b255cdbcb2f992d38a2fbc85f609236b9c37df937001f5d390c3`)  

Working copy also under `experiments/runs/` (gitignored by project convention); the **receipts/** path is the git anchor.


## What this folder still is

A 2026-07-22 model-qualification run. It remains a valid historical record of what the gate produced that day.

## What it is not

**Not a Jetson Orin Nano 8GB device verdict.**

Evidence already on the chronicle (#13655):

- Host recorded in the artifact: **Anthonys-MacBook-Pro.local arm64** (MacBook), not `tony-jetson`.
- Memory-class judgments (e.g. gemma4:e2b "too_large … on 8.0GB_class") were rendered on a machine that is not the 8GB Jetson.
- The gate at that time had **no** MemFree fail-closed eviction barrier (F1). `keep_alive:0` alone is insufficient (#9938 / #13706).
- `granite4:350m` QUALIFIED here is therefore not comparable to Jetson load-order outcomes, and does not rehabilitate or condemn Granite on the board.

## What it still teaches (carry-forward)

1. **F3 (provenance):** a qualification file without host/device provenance will be misread as "the" gate result. Later path-(b) runs put hostname, machine, MemFree/MemAvailable, and barrier fields *in* the artifact.
2. **Load-order contamination:** without F1, any model that followed a heavy resident could OOM and be scored as a capability DQ. That is why #18 required path (b), not a declaration.
3. **Do not delete history:** erasing this folder would erase the worked example of the mistake.

## For readers

| Question | Answer |
|----------|--------|
| ECS G3/G4 Jetson status? | Use `qualification_ecs_g3g4_pathb_20260804T185521Z` only. |
| House-wide Jetson matrix for all DEFAULT_CANDIDATES? | Still open / stale; this folder is not it. |
| Delete this folder? | No. Keep + this note. |

Lineage: #9934 · #9938 · #13655 · #13706 · #13730 · #13732 · #13738.
