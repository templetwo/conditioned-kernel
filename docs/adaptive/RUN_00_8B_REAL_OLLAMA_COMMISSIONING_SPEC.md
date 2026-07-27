# RUN 00.8B — Real Ollama End-to-End Commissioning Spec

**Base:** `117c211`  
**Branch:** `grok/ck-run-00-8b-real-ollama-commissioning`  
**Scope:** instrument validation only  

## Labels (mandatory on all artifacts)

```text
execution_scope = commissioning_validation
scientific_status = commissioning_instrument_test_only
scientific_completion = false
headline_eligible = false
m0_authorized = false
efficacy_claim_permitted = false
```

## Path

```text
commissioning plan
  → packet compile + packet/control receipts
  → Ollama /api/chat (exactly one request per cell max)
  → raw response evidence
  → ck.response_scoring_adapter.v1
  → relational scorer (when structure permits)
  → score-to-cell binding
  → persistent ledger
  → fresh-process reopen + DUPLICATE_TERMINALIZATION
  → commissioning admission
```

## Non-goals

- No thesis test  
- No M0 authorization  
- No C3-vs-C1 efficacy interpretation (gold-leaked task)  
- No retries / repair / second model  

## Modules

- `commissioning_plan.py` — `ck.commissioning_plan.v1`  
- `ollama_commissioning.py` — preflight + real run  

## Source candidate

`ck.m0.candidate.v1` / `9ec3d37a…` — retired, never mutated.
