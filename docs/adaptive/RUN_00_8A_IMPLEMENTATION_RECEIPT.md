# RUN 00.8A — Implementation Receipt

**Starting commit:** `36e889e789d2868da56d4abbb3ea27709ffb8b43`  
**Branch:** `grok/ck-run-00-8a-commissioning-safety`  
**M0:** NO-GO · Adaptive: HOLD · No models

## Reproduced RUN 00.7 / pre-fix defects

1. Tampered manifest passed integrity (truthy hash only)  
2. C1 could accept C3 score record  
3. SCORED with null score_record possible  
4. Caller `"pass"` overrode failed control  
5. In-memory ledger lost across processes  
6. `temperature=0` → 0.3; `seed=0` → 42  
7. Scientific scope not forced at executor entry  
8. Empty response 0-vs-null ambiguity  
9. Frozen artifact overwrite silent  

## Trust-boundary changes

| Fix | Module |
|---|---|
| Independent manifest hash | `m0_admission.py` |
| Auth receipt binding | `m0_admission.py` |
| Persistent ledger | `persistent_terminal_ledger.py` |
| Score-to-cell binding | `m0_ledger_integration.py` |
| Receipt-derived status | `evidence_verification.py` |
| Provenance compute | `runtime_provenance.py` |
| Falsy options | `edge.py` |
| Response adapter | `response_scoring_adapter.py` |
| Scope gate | `commissioning_executor.py` |
| Pad/condition identity | `control_contract.py` |
| Artifact supersession | `m0_manifest.py` |
| Control headline lie | `control_contract.py` to_dict |

## Commands

```text
pytest -q tests/test_run_00_8a_commissioning_safety.py
32 passed

pytest -q
424 passed

ruff check (00.8A modules) → clean after import fixes
```

## Proof no models

Synthetic responders only; no generate/httpx/ollama client calls in executor path.

## Untouched

Scorer arithmetic, scientific task corpus design, M0 live execution, adaptive riverbed.

## Remaining for Anthony

1. Successor scientific task corpus design (outside 00.8A).  
2. Real runtime option confirmation channel for live Ollama.  
3. Two-stage freeze commit field policy for production releases.  
4. Whether commissioning may ever run a single real model smoke after 00.8A review.

## Ready for independent adversarial review?

**Yes.**
