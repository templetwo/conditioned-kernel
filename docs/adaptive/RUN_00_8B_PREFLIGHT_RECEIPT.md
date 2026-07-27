# RUN 00.8B — Preflight Receipt

**Verdict:** `COMMISSIONING_PREFLIGHT_PASS`  
**Timestamp:** recorded in `experiments/runs/commissioning_00_8b/preflight.json`

| Check | Result |
|---|---|
| Base commit | `117c211` |
| Retired manifest hash | `9ec3d37a…` match |
| Ollama reachable | yes `http://127.0.0.1:11434` |
| Ollama version | `0.20.7` |
| Model installed | `qwen2.5:0.5b` |
| Resolved digest | `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67` |
| Quantization | Q4_K_M |
| Parameter size | 494.03M |
| Family | qwen2 |
| temperature=0.0 / seed=0 / num_ctx=2048 | survive CK serialization |
| Plan hash verifies | yes |
| Ledger empty at start | yes |
| 4 planned cells | yes |
| Scientific scope | not selected |
| Authorization receipt | none |

Preflight failure codes used if blocked: `RUNTIME_UNAVAILABLE`, `MODEL_DIGEST_MISSING` — not triggered.
