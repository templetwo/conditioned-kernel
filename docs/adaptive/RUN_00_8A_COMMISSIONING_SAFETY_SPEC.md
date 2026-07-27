# RUN 00.8A — Commissioning Safety Spec

**Base:** `36e889e`  
**Branch:** `grok/ck-run-00-8a-commissioning-safety`  
**M0:** NO-GO · Adaptive: HOLD · No model execution

## Labels (all 00.8A artifacts)

```text
execution_scope = commissioning_validation
scientific_status = commissioning_safety_only
scientific_completion = false
headline_eligible = false
m0_authorized = false
```

## Trust-boundary architecture

```text
manifest cell
  → packet receipt (evidence-derived)
  → control receipt (evidence-derived)
  → synthetic model adapter (no Ollama)
  → response_scoring_adapter.v1
  → score-to-cell binding
  → persistent terminal ledger (manifest_sha256 + cell_id)
  → admission (independent hash + auth binding)
```

## Required closures

1. Independent manifest SHA-256 verification  
2. Authorization receipt binding  
3. Persistent append-only ledger across processes  
4. Score-to-cell binding  
5. Receipt-derived packet/control status  
6. Model digest + runtime provenance (computed completeness)  
7. temperature=0 / seed=0 preservation  
8. Runtime option enforcement / RUNTIME_PROVENANCE_FAILURE  
9. Scientific scope gate at execution entry  
10. Frozen response→score mapping  
11. Raw response evidence retention  
12. Control receipts never headline-eligible  
13. Condition-neutral pad; no model-visible condition_id  
14. Frozen artifact overwrite refusal  
15. Repository commit semantics documented  
16. Provenance completeness derived  
17. Per-condition terminal classification counts  

## Explicit non-goals

No M0-v2 corpus, no scorer arithmetic change, no scientific authorization,
no adaptive behavior, no real model invocation.
